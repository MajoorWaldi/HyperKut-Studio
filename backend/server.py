"""The HTTP side of the app: uploads, jobs and their progress (server-sent events), the result video, and the web interface itself."""
import asyncio
import array
import hashlib
import json
import logging
import re as _re
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import anyio
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.datastructures import Headers
from filelock import FileLock
from PIL import Image

from .config import ROOT, Settings
from .brand import NAME as APP_NAME, EXPORT_PREFIX
from .jobs import JobStore
from .models import AICandidateRequest, ActiveTake, EditStyle, JobInputs, JobPatch, JobRequest, JobState, PresetIn, Regenerate, ShotPatch, Take, TimelineInfo, TimelineShot, TrimTake, Upload
from .ai_edits import accept_candidate, candidate_file, prepare_candidate, read_candidate
from .models import TimelineSave, TimelineVersion
from . import manual_timeline
from .take_trim import trim_bounds
from .runner import ComfyRunner, MockRunner, Runner, _failure_message
from .media import validate_media
from .review import build_review_frames
from .storage import SharedProjectRepository, project_path, write_json
from .templates import TemplateError, load_templates
from .direction import catalog, validate_prepared, brief_context
from . import restart as studio_restart
from .brief_preview import prepare_brief
from .unified_motion import validate_finishing
from .access import AccessMiddleware, acquire_upload_quota, validate_access

KINDS = {"video": "video", "image": "image", "audio": "audio"}
logger = logging.getLogger(__name__)
MEDIA_SUFFIXES = {
    'image': {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.avif'},
    'video': {'.mp4', '.mov', '.mkv', '.webm', '.avi', '.m4v', '.mpeg', '.mpg'},
    'audio': {'.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac', '.opus', '.aiff', '.aif', '.wma'},
}


class SameOriginMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http' and scope['method'] in ('POST', 'PUT', 'PATCH', 'DELETE'):
            headers = Headers(scope=scope)
            origin = headers.get('origin')
            if origin:
                try:
                    parsed = urlsplit(origin)
                    allowed = parsed.scheme in ('http', 'https') and parsed.netloc.lower() == headers.get('host', '').lower() and parsed.scheme == scope.get('scheme', 'http')
                except ValueError:
                    allowed = False
                if not allowed:
                    await Response('Cross-origin mutations are not allowed', status_code=403)(scope, receive, send)
                    return
        await self.app(scope, receive, send)


def create_app(settings: Settings | None = None, runner: Runner | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    validate_access(settings)
    recovery_lock = asyncio.Lock()
    async def recover_pending(target=None, *, all_jobs=False):
        async with recovery_lock:
            if isinstance(runner, ComfyRunner):
                for job in list(store.jobs.values()):
                    if not all_jobs and (target is None or (
                        job.id!=target.id and (not target.state.project_id or job.state.project_id!=target.state.project_id))):
                        continue
                    if (job.pending_handle or job.submission_key) and job.state.status not in ('running', 'queued'):
                        try:
                            await asyncio.wait_for(runner.recover(job), timeout=10)
                        except Exception as error:
                            logger.exception('Could not reconcile GPU result for job %s',job.id)
                            job.update(error=f'Recovery pending for this project: {_failure_message(error)}')
                            if not all_jobs:
                                raise HTTPException(503, f'This project has an unreconciled GPU result ({job.id}). Check the proxy and retry; other projects remain available.') from error

    @asynccontextmanager
    async def lifespan(app):
        try:
            await recover_pending(all_jobs=True)
        except HTTPException:
            pass  # mutations retry reconciliation once the local proxy is available
        yield

    app = FastAPI(title=APP_NAME, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
    app.add_middleware(SameOriginMiddleware)
    app.state.boot_id = uuid.uuid4().hex
    app.state.restarting = False
    app.state.mutations = 0
    app.state.artifact_gc = False

    @app.middleware('http')
    async def restart_admission(request, call_next):
        mutation = request.method in ('POST', 'PUT', 'PATCH', 'DELETE')
        if mutation and app.state.restarting:
            return Response(json.dumps({'detail': 'Studio is restarting. Retry when it is ready.'}), status_code=503, media_type='application/json')
        if mutation and app.state.artifact_gc:
            return Response(json.dumps({'detail':'Artifact collection is in progress. Retry when it finishes.'}),status_code=409,media_type='application/json')
        if mutation:
            app.state.mutations += 1
        try:
            return await call_next(request)
        finally:
            if mutation:
                app.state.mutations -= 1

    @app.get('/api/studio/status')
    async def studio_status():
        return {
            'instance_id': app.state.boot_id,
            'restarting': app.state.restarting,
            'config_identity': settings.config_identity(),
            'effective_limits': settings.effective_limits(),
        }

    @app.post('/api/studio/restart', status_code=202)
    async def restart_studio():
        def busy():
            return app.state.mutations > 1 or any(
                j.state.status in ('running', 'queued') or (j.task is not None and not j.task.done())
                or j.pending_handle or j.submission_key for j in store.jobs.values())
        if busy():
            raise HTTPException(409, 'A generation or another action is in progress. Wait before restarting the Studio.')
        try:
            studio_restart.restart_command()
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        app.state.restarting = True
        try:
            studio_restart.launch_restart(settings.workspace)
        except (OSError, ValueError) as error:
            app.state.restarting = False
            raise HTTPException(503, 'Could not start the Studio restart helper') from error
        return {'restarting': True, 'instance_id': app.state.boot_id}

    (settings.workspace / "uploads").mkdir(parents=True, exist_ok=True)
    store = JobStore(settings.workspace / "state")
    names_file = settings.workspace / "uploads.json"
    try:
        names = json.loads(names_file.read_text(encoding='utf-8')) if names_file.is_file() else {}
        if not isinstance(names, dict):
            names = {}
    except (OSError, ValueError):
        names = {}
    uploads: dict[str, Path] = {p.stem: p for p in (settings.workspace / "uploads").glob("*")}  # what was added before the server stopped is still there for the jobs that were kept

    def describe(upload_id: str | None) -> Upload | None:
        if upload_id not in uploads:
            return None
        path = uploads[upload_id]
        record = names.get(upload_id, path.name)
        kind = record.get('kind') if isinstance(record, dict) else None
        if kind not in KINDS:
            kind = (mimetypes.guess_type(path.name)[0] or '').split('/')[0]
        name = record.get('name', path.name) if isinstance(record, dict) else record
        return Upload(id=upload_id, name=name, kind=kind if kind in KINDS else 'video', url=f'/api/uploads/{upload_id}')
    runner = runner or (MockRunner() if settings.mock else ComfyRunner(settings, uploads))

    @app.get("/api/health")
    async def health(mode: str = "remix", refs: int = 0, ref_video: bool = False, voice: bool = False):
        """Readiness of the selected mode's required graph, not every exported node."""
        from .templates import PHASES, graph_readiness

        if mode not in ("remix", "text", "music"):
            raise HTTPException(422, "Unknown mode")
        if not 0 <= refs <= 5:
            raise HTTPException(422, "refs must be between 0 and 5")
        out = {"mock": settings.mock, "comfyui": False, "proxy": False, "videotools": False, "output_dir": str(settings.output_dir) if settings.output_dir else None,
               'load_errors': store.load_errors, 'missing_nodes': [], 'missing_models': [], 'preset_inputs': True, 'music_rhythm_modes': True, 'adaptive_editing_modes': True}
        out['instance_id'] = app.state.boot_id
        out['mode'] = mode
        async with httpx.AsyncClient(timeout=3) as client:
            try:
                out["comfyui"] = (await client.get(f"{settings.comfyui_url}/system_stats")).status_code == 200
                response = await client.get(f'{settings.comfyui_url}/object_info')
                response.raise_for_status()
                schemas = response.json()
                if not isinstance(schemas, dict):
                    raise ValueError("Invalid object_info response")
                templates = load_templates(settings.templates_dir, mode)
                absent = (*(f"ref{i + 1}" for i in range(refs, 5)),
                          *(name for name, given in (("ref_video", ref_video), ("voice", voice), ("energy_reference", False)) if not given))
                # Optional finishing is best-effort at execution time. Check a
                # conservative baseline without requiring its mask/model branch.
                defaults = {"subject_mask": False, "motion_design": False, "unified_layers": "[]"}
                for phase in PHASES:
                    template = templates[phase]
                    graph = template.fill({key: value for key, value in defaults.items() if key in template.slots},
                                          tuple(name for name in absent if name in template.slots))
                    missing_nodes, missing_models = graph_readiness(graph, schemas)
                    out['missing_nodes'].extend(missing_nodes)
                    out['missing_models'].extend(missing_models)
                out['missing_nodes'] = sorted(set(out['missing_nodes']))
                out['missing_models'] = sorted(set(out['missing_models']))
                out['videotools'] = not out['missing_nodes']
            except (httpx.HTTPError, ValueError, OSError, TemplateError):
                pass
            try:
                response = await client.get(f'{settings.proxy_url}/api/v2/health')
                payload=response.json()
                out['proxy'] = response.status_code == 200 and isinstance(payload,dict) and payload.get('status') == 'healthy'
            except (httpx.HTTPError, ValueError):
                pass
        return out

    @app.post("/api/uploads", response_model=Upload)
    async def upload(file: UploadFile = File(...)):
        kind = (file.content_type or mimetypes.guess_type(file.filename or "")[0] or "").split("/")[0]
        if kind not in KINDS:
            raise HTTPException(415, f"Not a video, an image or a sound: {file.content_type}")
        upload_id = uuid.uuid4().hex[:12]
        path = settings.workspace / "uploads" / f"{upload_id}{Path(file.filename or '').suffix.lower()}"
        size = 0
        quota_lock = FileLock(str(settings.workspace / ".uploads-quota.lock"), thread_local=False)
        try:
            await acquire_upload_quota(quota_lock)
            used = sum(path.stat().st_size for path in (settings.workspace / "uploads").iterdir()
                       if path.is_file() and not path.is_symlink())
            with path.open('wb') as stream:
                while chunk := await file.read(1024*1024):
                    size += len(chunk)
                    if size > settings.max_upload_bytes:
                        raise HTTPException(413,'The upload exceeds the configured size limit')
                    if used + size > settings.max_workspace_bytes:
                        raise HTTPException(507, 'The upload storage quota is exhausted. Remove unused uploads before retrying.')
                    stream.write(chunk)
            if not settings.mock:
                try:
                    await asyncio.to_thread(validate_media, path, kind, settings.max_media_seconds, settings.max_media_pixels)
                except (ValueError, OSError, subprocess.TimeoutExpired) as error:
                    raise HTTPException(422,str(error)) from error
            suffix = Path(file.filename or '').suffix.lower()
            if kind == 'image' and not settings.mock:
                with Image.open(path) as image:
                    media_type = Image.MIME.get(image.format, 'application/octet-stream')
                suffix = mimetypes.guess_extension(media_type) or '.bin'
            elif suffix not in MEDIA_SUFFIXES[kind]:
                suffix = mimetypes.guess_extension(file.content_type or '') or ('.mp4' if kind == 'video' else '.wav' if kind == 'audio' else '.png')
                if suffix not in MEDIA_SUFFIXES[kind]:
                    suffix = '.mp4' if kind == 'video' else '.wav' if kind == 'audio' else '.png'
            canonical = path.with_suffix(suffix)
            if canonical != path:
                path.replace(canonical)
                path = canonical
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        finally:
            if quota_lock.is_locked:
                quota_lock.release()
            await file.close()
        uploads[upload_id] = path
        names[upload_id] = {'name':file.filename or path.name,'kind':kind}
        write_json(names_file,names)
        return Upload(id=upload_id, name=file.filename or path.name, kind=kind, url=f"/api/uploads/{upload_id}")

    @app.get("/api/uploads/{upload_id}")
    async def upload_file(upload_id: str):
        if upload_id not in uploads:
            raise HTTPException(404, "Unknown upload")
        path = uploads[upload_id]
        kind = describe(upload_id).kind
        content_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        safe = path.suffix.lower() in MEDIA_SUFFIXES[kind] and content_type.startswith(kind + '/')
        if not safe and kind == 'image':
            try:
                with Image.open(path) as image:
                    content_type = Image.MIME.get(image.format, 'application/octet-stream')
                safe = content_type.startswith('image/')
            except (OSError, ValueError):
                pass
        return FileResponse(path, media_type=content_type if safe else 'application/octet-stream',
            headers={'X-Content-Type-Options': 'nosniff', 'Content-Disposition': 'inline' if safe else 'attachment'})

    upload_waves: dict[str, list[float]] = {}

    @app.get("/api/uploads/{upload_id}/waveform", response_model=list[float])
    async def upload_waveform(upload_id: str):
        if upload_id not in uploads:
            raise HTTPException(404, "Unknown upload")
        if describe(upload_id).kind != 'audio':
            raise HTTPException(422, "Waveform preview requires an audio upload")
        if upload_id not in upload_waves:
            from .media import audio_waveform
            try:
                peaks = await asyncio.to_thread(audio_waveform, uploads[upload_id], settings.max_media_seconds)
            except (ValueError, OSError, subprocess.TimeoutExpired) as error:
                raise HTTPException(422, "Unable to generate the audio waveform") from error
            if len(upload_waves) >= 32:
                upload_waves.pop(next(iter(upload_waves)))
            upload_waves[upload_id] = peaks
        return upload_waves[upload_id]

    def validate_request(request):
        unknown = [u for u in (request.source, request.ref_video, request.music, request.voice, *request.refs) if u and u not in uploads]
        if unknown:
            raise HTTPException(422, f"Unknown uploads: {unknown}")
        if request.mode == "remix" and not request.source:
            raise HTTPException(422, "Remix needs a source video: it is the template of the edit")
        if request.mode == 'music' and not request.music:
            raise HTTPException(422,'Music mode needs an audio track')
        if request.settings.audio == 'voice' and not (request.voice and request.settings.dialogue.strip()):
            raise HTTPException(422,'Voice mode needs a voice sample and dialogue')
        roles = [(request.source,'video'),(request.ref_video,'video'),(request.music,'audio'),(request.voice,'audio'),*((ref,'image') for ref in request.refs)]
        for upload_id, expected in roles:
            if upload_id and describe(upload_id).kind != expected:
                raise HTTPException(422,f'Expected {expected} for {upload_id}')
        try:
            validate_prepared(request)
            validate_finishing(request.settings.model_dump(), request.settings.duration)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    preview_lock = asyncio.Lock()

    @app.get('/api/art-direction')
    async def art_direction_catalog():
        return {'fields': catalog()}

    @app.post('/api/brief-preview')
    async def brief_preview(request: JobRequest, lang: str = 'en'):
        validate_request(request)
        if lang not in ('fr','en'):
            raise HTTPException(422, 'Unsupported language')
        if preview_lock.locked() or any(j.state.status in ('running','queued') for j in store.jobs.values()):
            raise HTTPException(409, 'Finish the current preparation or generation before preparing another direction.')
        try:
            async with preview_lock:
                return await prepare_brief(request, settings, uploads, lang)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except httpx.HTTPError as error:
            raise HTTPException(503, 'The local preparation service is unavailable. Check the connection and try again.') from error

    @app.post('/api/brief-approve')
    async def approve_brief(request: JobRequest):
        """Explicitly reuse/edit a retained brief with current settings, without a model call."""
        if not request.settings.approved_brief.strip():
            raise HTTPException(422,'The brief is empty')
        clean=request.model_copy(deep=True)
        clean.settings.approved_brief=''
        clean.settings.approved_brief_context=''
        validate_request(clean)
        return {'context':brief_context(clean)}

    @app.post("/api/jobs", response_model=JobState)
    async def create_job(request: JobRequest):
        validate_request(request)
        if sum(j.state.status in ('queued','running') for j in store.jobs.values()) >= settings.max_active_jobs:
            raise HTTPException(429,'The job queue is full; wait for a job to finish')
        job = store.create(request)
        job.update(title=(request.settings.prompt.strip() or request.mode)[:60])
        job.task = asyncio.create_task(runner.run(job))
        return job.state

    def _manifest(job) -> tuple[Path, dict]:
        """The folder and the manifest of the project of a job: what ComfyUI wrote there is the truth about the takes."""
        if not (settings.output_dir and job.state.project_id):
            raise HTTPException(404, "This job has no project on the disk")
        try:
            project = SharedProjectRepository(settings.output_dir/'MajoorVideoTools').path(job.state.project_id)
        except ValueError as error:
            raise HTTPException(404,'Invalid project') from error
        if not (project / "manifest.json").is_file():
            raise HTTPException(404, "This job has no project on the disk")
        return project, json.loads((project / "manifest.json").read_text(encoding="utf-8"))

    def _manifest_shot(manifest: dict, shot_id: str) -> dict:
        shot = next((s for s in manifest["shots"] if s["shot_id"] == shot_id), None)
        if shot is None:
            raise HTTPException(404, "Unknown shot")
        return shot

    def _job(job_id: str):
        job = store.get(job_id)
        if job is None:
            raise HTTPException(404, "Unknown job")
        if job.deleting:
            raise HTTPException(409, 'This job is being deleted')
        if job.updating_project:
            raise HTTPException(409, 'Project files are being updated')
        return job

    async def update_project(job, operation):
        job.updating_project = True
        task = asyncio.create_task(asyncio.to_thread(operation))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # HTTP middleware may cancel its scope again during cleanup.
            with anyio.CancelScope(shield=True):
                await asyncio.gather(task, return_exceptions=True)
            raise
        finally:
            job.updating_project = False

    def _exclusive(job):
        if job.state.project_id and any(other.id != job.id and other.state.project_id == job.state.project_id for other in store.jobs.values()):
            raise HTTPException(409,'This older project is shared by several jobs. Start a new generation before editing or deleting its files.')

    def refresh_shots(job):
        if job.state.status not in ('running', 'queued') and job.state.project_id:
            try:
                _, manifest = _manifest(job)
                job.sync_shots(manifest)
            except HTTPException as error:
                if error.status_code != 404:
                    raise
            except (OSError, ValueError, KeyError, TypeError) as error:
                warning = f'{job.state.project_id}: cannot refresh project metadata ({error})'
                if warning not in store.load_errors:
                    store.load_errors.append(warning)

    @app.get("/api/jobs", response_model=list[JobState])
    async def recent_jobs():
        for job in store.jobs.values():
            refresh_shots(job)
        return [job.state for job in sorted(store.jobs.values(), key=lambda j: j.state.created_at, reverse=True)]

    def _project_dir(job) -> Path | None:
        """The folder of the project of a job, only if its id is the one ComfyUI makes and it is where the pack puts its projects."""
        if not (settings.output_dir and job.state.project_id and _re.fullmatch(r"p_[0-9a-f]{8,32}", job.state.project_id)):
            return None
        root = (settings.output_dir / "MajoorVideoTools").resolve()
        project = (root / job.state.project_id).resolve()
        return project if project.parent == root and project.is_dir() else None

    def _size(path: Path) -> int:
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.is_dir() else (path.stat().st_size if path.is_file() else 0)

    @app.get("/api/jobs/sizes", response_model=dict[str, int])
    async def sizes():
        """What every job takes on the disk: its project and its result video."""
        def measure():
            return {job.id: (_size(_project_dir(job)) if _project_dir(job) else 0) + _size(settings.workspace / "jobs" / f"{job.id}.mp4") for job in list(store.jobs.values())}
        return await asyncio.to_thread(measure)

    def cache_idle():
        return app.state.mutations<=1 and not any(
            j.state.status in ('running','queued') or (j.task and not j.task.done())
            or j.pending_handle or j.submission_key or j.pending_remote or j.updating_project
            for j in store.jobs.values())

    @app.get('/api/storage')
    async def storage_inventory():
        remote=runner.remote if isinstance(runner,ComfyRunner) else None
        out={'mirror_bytes':await asyncio.to_thread(_size,settings.output_dir/'MajoorVideoTools') if settings.output_dir else 0,
             'cache':None,'worker_bytes':None}
        if remote:
            out['cache']=await asyncio.to_thread(remote.cache_inventory)
            out['cache']['collection_available']=cache_idle()
            out['worker_cleanup_pending']=len(list(remote.scratch.glob('*.cleanup.json')))
        return out

    @app.post('/api/storage/worker/cleanup')
    async def retry_worker_cleanup():
        if not isinstance(runner,ComfyRunner) or runner.remote is None:
            raise HTTPException(409,'Worker cleanup requires remote_artifacts storage')
        if not cache_idle():
            raise HTTPException(409,'Wait for active operations and reconcile pending results before worker cleanup')
        client=runner.client_factory()
        try:
            for path in runner.remote.scratch.glob('*.cleanup.json'):
                cleanup=json.loads(path.read_text(encoding='utf-8'))
                await runner._release_workspace(client,cleanup['token'],acknowledged=cleanup['acknowledged'])
        finally:
            await client.aclose()
        return {'worker_cleanup_pending':len(list(runner.remote.scratch.glob('*.cleanup.json')))}

    @app.post('/api/storage/cache/gc')
    async def collect_artifacts(dry_run: bool = True):
        remote=runner.remote if isinstance(runner,ComfyRunner) else None
        if remote is None:
            raise HTTPException(409,'Artifact cache collection requires remote_artifacts storage')
        if not cache_idle():
            raise HTTPException(409,'Wait for active operations and reconcile pending results before collecting artifacts')
        app.state.artifact_gc=True
        collection=asyncio.create_task(asyncio.to_thread(remote.cache_inventory,collect=True,dry_run=dry_run))
        try:
            return await asyncio.shield(collection)
        except asyncio.CancelledError:
            with anyio.CancelScope(shield=True):
                await asyncio.gather(collection,return_exceptions=True)
            raise
        finally:
            app.state.artifact_gc=False

    @app.patch("/api/jobs/{job_id}", response_model=JobState)
    async def patch_job(job_id: str, body: JobPatch):
        job = _job(job_id)
        job.update(**body.model_dump(exclude_none=True))
        return job.state

    @app.delete("/api/jobs/{job_id}")
    async def delete_job(job_id: str, project: bool = False):
        """Forget a job and its video; with `project`, also the project folder that ComfyUI wrote (the takes)."""
        job = _job(job_id)
        await recover_pending(job)
        if job.state.status in ("queued", "running"):
            raise HTTPException(409, "The job is still running")
        if project:
            _exclusive(job)
        job.deleting = True
        try:
            if project and (folder := _project_dir(job)):
                removal = asyncio.create_task(asyncio.to_thread(shutil.rmtree, folder))
                try:
                    await asyncio.shield(removal)
                except asyncio.CancelledError:
                    await asyncio.gather(removal, return_exceptions=True)
                    raise
            if project and job.state.project_id and isinstance(runner,ComfyRunner) and runner.remote:
                await asyncio.to_thread(runner.remote.forget_project,job.state.project_id)
            (settings.workspace / "jobs" / f"{job.id}.mp4").unlink(missing_ok=True)
            store.delete(job)
        finally:
            job.deleting = False
        return {"deleted": job_id}

    @app.post("/api/jobs/{job_id}/free")
    async def free_space(job_id: str):
        """Delete the takes that the edit does not use (the active take of every shot stays) and say how much room it made."""
        job = _job(job_id)
        await recover_pending(job)
        if job.state.status in ("queued", "running"):
            raise HTTPException(409, "The job is still running")
        project, manifest = _manifest(job)
        _exclusive(job)
        def discard_unused():
            freed = 0
            discarded = []
            with SharedProjectRepository(project.parent).edit(project.name) as manifest:
                used = manual_timeline.referenced_takes(project)
                protected = {r['media_ref'] for s in manifest['shots'] for r in s.get('revisions',[]) if r.get('media_range') is not None or r['revision_id']==s.get('active_revision_id')}
                protected.update(r['media_ref'] for s in manifest['shots'] for r in s.get('revisions', [])
                                 if (s['shot_id'], r['revision_id']) in used)
                for shot in manifest['shots']:
                    kept = []
                    for revision in shot.get('revisions',[]):
                        if revision.get('media_range') is not None or revision['revision_id']==shot.get('active_revision_id') or (shot['shot_id'], revision['revision_id']) in used:
                            kept.append(revision)
                        else:
                            target=(project/revision['media_ref']).resolve()
                            if project in target.parents and target.is_file() and revision['media_ref'] not in protected:
                                discarded.append(target)
                    shot['revisions']=kept
            for target in set(discarded):
                freed += target.stat().st_size
                target.unlink()
            return {"freed": freed,'mirror_freed_bytes':freed,'cache_freed_bytes':0,'worker_freed_bytes':None}
        result = await update_project(job, discard_unused)
        refresh_shots(job)
        return result

    @app.get("/api/jobs/{job_id}/cover")
    async def cover(job_id: str):
        """A picture for the card of a project: the start of its result."""
        job = _job(job_id)
        video_file = settings.workspace / "jobs" / f"{job.id}.mp4"
        if not video_file.is_file():
            raise HTTPException(404, "No picture")
        picture = settings.workspace / "thumbs" / f"cover_{job.id}_{job.edits}.jpg"
        if not picture.is_file():
            picture.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(lambda: subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-y", "-loglevel", "error", "-ss", "0.3", "-i", str(video_file), "-frames:v", "1", "-vf", "scale=360:-2", str(picture)], check=False))
        if not picture.is_file():
            raise HTTPException(404, "No picture")
        return FileResponse(picture, headers={"Cache-Control": "no-cache"})

    @app.get("/api/jobs/{job_id}/inputs", response_model=JobInputs)
    async def job_inputs(job_id: str):
        request = _job(job_id).request
        return JobInputs(mode=request.mode, settings=request.settings, source=describe(request.source), refs=[u for u in map(describe, request.refs) if u], ref_video=describe(request.ref_video),
                         music=describe(request.music), voice=describe(request.voice))

    @app.get("/api/jobs/{job_id}/preview")
    async def job_preview(job_id: str):
        picture = _job(job_id).preview
        if picture is None:
            raise HTTPException(404, "No preview yet")
        return Response(picture[1], media_type=picture[0], headers={"Cache-Control": "no-store"})

    @app.get("/api/jobs/{job_id}", response_model=JobState)
    async def job_state(job_id: str):
        job = _job(job_id)
        refresh_shots(job)
        return job.state

    @app.get("/api/jobs/{job_id}/events")
    async def job_events(job_id: str):
        job = _job(job_id)

        async def stream():
            async for state in job.events():
                yield f"data: {state.model_dump_json()}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})

    @app.post("/api/jobs/{job_id}/cancel", response_model=JobState)
    async def cancel(job_id: str):
        job = _job(job_id)
        await recover_pending(job)
        if job.task and not job.task.done():
            job.task.cancel()
            await asyncio.gather(job.task, return_exceptions=True)
        if job.state.status in ('queued', 'running'):
            job.update(status='cancelled')
        return job.state

    @app.get("/api/jobs/{job_id}/video")
    async def video(job_id: str):
        path = settings.workspace / "jobs" / f"{_job(job_id).id}.mp4"
        if not path.is_file():
            raise HTTPException(404, "This job has no video yet")
        return FileResponse(path, media_type="video/mp4", headers={"Cache-Control": "no-store"})

    @app.post("/api/jobs/{job_id}/regenerate", response_model=JobState)
    async def regenerate(job_id: str, body: Regenerate):
        job = _job(job_id)
        await recover_pending(job)
        refresh_shots(job)
        _exclusive(job)
        if job.state.status in ("queued", "running"):
            raise HTTPException(409, "The job is still running")
        known = {s.id: s for s in job.state.shots}
        if not body.shots or any(shot not in known for shot in body.shots):
            raise HTTPException(422, "Unknown shots")
        if locked := [shot for shot in body.shots if known[shot].locked]:
            raise HTTPException(409, f"Locked shots are kept as they are: {locked}")
        if any(known[shot].render_source!='generated' and shot in body.prompts and body.prompts[shot]!=known[shot].prompt for shot in body.shots):
            raise HTTPException(422,'Local sources use render_source in the plan; changing their generation prompt would not change the render')
        job.begin('shots')
        job.task = asyncio.create_task(runner.regenerate(job, body.shots, {k: v for k, v in body.prompts.items() if k in body.shots}))
        return job.state

    def public_candidate(job, candidate):
        fields = ('id', 'created_at', 'shot_id', 'operation', 'status', 'take', 'prompt', 'seed', 'duration',
                  'generated_seconds', 'error', 'revision_id')
        return {key: candidate.get(key) for key in fields} | {
            'url': f'/api/jobs/{job.id}/ai-candidates/{candidate["id"]}/video'
                   if candidate['status'] in ('ready', 'accepted') else None}

    def experimental():
        if not settings.experimental_ai_edit:
            raise HTTPException(403, 'Enable HYPERKUT_EXPERIMENTAL_AI_EDIT=1 to test AI edit candidates')
        if settings.storage_backend=='remote_artifacts':
            raise HTTPException(409,'AI edit candidates are not supported with remote_artifacts. Use shared_local; no candidate or GPU request was created.')

    def idle_experiment(job, shot_id):
        if job.deleting or job.updating_project or store.get(job.id) is not job:
            raise HTTPException(409, 'Project files are being updated or deleted')
        _exclusive(job)
        if job.state.status in ('queued', 'running') or (job.task and not job.task.done()):
            raise HTTPException(409, 'Wait for the current operation to finish')
        shot = next((s for s in job.state.shots if s.id == shot_id), None)
        if shot is None:
            raise HTTPException(404, 'Unknown shot')
        if shot.locked:
            raise HTTPException(409, 'Unlock the shot first')
        if shot.render_source != 'generated':
            raise HTTPException(422, 'AI edit candidates require a generated raw take')

    @app.get('/api/jobs/{job_id}/shots/{shot_id}/ai-candidates')
    async def ai_candidates(job_id: str, shot_id: str):
        job = _job(job_id)
        if not settings.experimental_ai_edit or settings.storage_backend=='remote_artifacts':
            return {'enabled': False, 'candidates': []}
        project, manifest = _manifest(job)
        _manifest_shot(manifest, shot_id)
        candidates = []
        for path in sorted((project / 'experiments' / 'ai_edit').glob('*/candidate.json')):
            row = json.loads(path.read_text(encoding='utf-8'))
            if row['shot_id'] == shot_id:
                # Restarted jobs retain candidates, but never silently resubmit.
                if row['status'] in ('queued', 'running') and (
                    job.state.status not in ('queued', 'running') or row.get('job_operation') != job.state.operation
                ):
                    row.update(status='cancelled', error='The Studio stopped or lost this operation; reconcile the GPU request before retrying')
                candidates.append(public_candidate(job, row))
        return {'enabled': True, 'candidates': sorted(candidates, key=lambda row: row['created_at'] or 0)}

    @app.post('/api/jobs/{job_id}/shots/{shot_id}/ai-candidates')
    async def start_ai_candidate(job_id: str, shot_id: str, body: AICandidateRequest):
        experimental()
        job = _job(job_id)
        await recover_pending(job)
        refresh_shots(job)
        idle_experiment(job, shot_id)
        candidate_runner = getattr(runner, 'ai_candidate', None)
        if not callable(candidate_runner):
            raise HTTPException(409, 'This runner does not implement AI edit candidates')
        if sum(j.state.status in ('queued', 'running') for j in store.jobs.values()) >= settings.max_active_jobs:
            raise HTTPException(429, 'The job queue is full')
        project, manifest = _manifest(job)
        def prepare():
            row = prepare_candidate(project, manifest, shot_id, body)
            row['job_operation'] = job.state.operation + 1
            write_json(candidate_file(project, row['id']), row)
            return row
        try:
            row = await update_project(job, prepare)
        except (ValueError, StopIteration) as error:
            raise HTTPException(422, str(error)) from error
        job.begin('shots')
        job.task = asyncio.create_task(candidate_runner(job, row))
        return {'job': job.state, 'candidate': public_candidate(job, row)}

    @app.get('/api/jobs/{job_id}/ai-candidates/{candidate_id}/video')
    async def ai_candidate_video(job_id: str, candidate_id: str):
        experimental()
        project, _ = _manifest(_job(job_id))
        try:
            row = read_candidate(project, candidate_id)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error
        path = candidate_file(project, candidate_id).parent / 'preview.mp4'
        if row['status'] not in ('ready', 'accepted') or not path.is_file():
            raise HTTPException(404, 'No ready preview')
        return FileResponse(path, media_type='video/mp4', headers={'Cache-Control': 'no-store'})

    @app.post('/api/jobs/{job_id}/ai-candidates/{candidate_id}/{decision}', response_model=JobState)
    async def decide_ai_candidate(job_id: str, candidate_id: str, decision: str):
        experimental()
        job = _job(job_id)
        await recover_pending(job)
        project, _ = _manifest(job)
        try:
            row = read_candidate(project, candidate_id)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error
        idle_experiment(job, row['shot_id'])
        if decision not in ('accept', 'reject'):
            raise HTTPException(404, 'Unknown candidate decision')
        def decide():
            if decision == 'accept':
                accept_candidate(project, candidate_id)
            else:
                current = read_candidate(project, candidate_id)
                if current['status'] != 'ready':
                    raise ValueError('Only a ready candidate can be rejected')
                current['status'] = 'rejected'
                write_json(candidate_file(project, candidate_id), current)
        try:
            await update_project(job, decide)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        refresh_shots(job)
        if decision == 'accept':
            warning = 'Experimental raw take accepted. The previous video is unchanged: re-edit to export. Review overlays and music timing after extension.'
            job.update(warnings=list(dict.fromkeys([*job.state.warnings, warning])))
        return job.state

    @app.post("/api/jobs/{job_id}/re-edit", response_model=JobState)
    async def re_edit(job_id: str, style: EditStyle):
        job = _job(job_id)
        await recover_pending(job)
        refresh_shots(job)
        _exclusive(job)
        if job.state.status in ("queued", "running"):
            raise HTTPException(409, "The job is still running")
        project = _project_dir(job)
        manual = manual_timeline.read_record(project) if project else None
        if manual and manual['enabled']:
            raise HTTPException(409, 'Manual montage is enabled. Use Save and export in Manual montage, or disable it there before applying automatic edit styles.')
        if not job.state.shots or not all(s.done for s in job.state.shots):
            raise HTTPException(409, "The shots are not all made: there is nothing to edit")
        try:
            values = {**job.request.settings.model_dump(), **job.state.style.model_dump(exclude_none=True), **style.model_dump(exclude_none=True)}
            validate_finishing(values, sum(s.duration for s in job.state.shots))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        job.begin('edit')
        job.task = asyncio.create_task(runner.re_edit(job, style))
        return job.state

    @app.patch("/api/jobs/{job_id}/shots/{shot_id}", response_model=JobState)
    async def patch_shot(job_id: str, shot_id: str, body: ShotPatch):
        job = _job(job_id)
        if shot_id not in {s.id for s in job.state.shots}:
            raise HTTPException(404, "Unknown shot")
        job.update(shots=[s.model_copy(update={"locked": body.locked}) if s.id == shot_id else s for s in job.state.shots])
        return job.state

    @app.get("/api/jobs/{job_id}/shots/{shot_id}/thumb")
    async def thumb(job_id: str, shot_id: str):
        """The first picture of the active take of the shot, else the picture of the template it replaces."""
        job = _job(job_id)
        project, manifest = _manifest(job)
        shot = _manifest_shot(manifest, shot_id)
        take = next((r for r in shot.get("revisions", []) if r["revision_id"] == shot.get("active_revision_id")), None)
        target = (project / (take["media_ref"] if take else shot.get("thumbnail_ref") or "")).resolve()
        if project not in target.parents or not target.is_file():
            raise HTTPException(404, "No picture")
        if target.suffix.lower() in (".jpg", ".jpeg", ".png"):
            return FileResponse(target, headers={'Cache-Control': 'no-cache'})
        media_range = take.get('media_range') if take else None
        offset = float(take.get('source_start_seconds', 0)) if take else 0.0
        if media_range:
            source = manifest.get('source', {})
            fps = source.get('fps_num', 24) / (source.get('fps_den', 1) or 1)
            offset = (media_range.get('start_frame', 0) + media_range.get('end_frame_exclusive', 1)) / (2 * fps)
        key = hashlib.sha256(json.dumps([str(target), target.stat().st_mtime_ns, target.stat().st_size, media_range]).encode()).hexdigest()[:16]
        picture = settings.workspace / "thumbs" / f"{job.state.project_id}_{shot_id}_{key}.jpg"
        if not picture.is_file():
            picture.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(lambda: subprocess.run([shutil.which('ffmpeg') or 'ffmpeg','-y','-loglevel','error','-ss',str(offset),'-i',str(target),'-frames:v','1','-vf','scale=320:-2',str(picture)],check=False,timeout=30))
        if not picture.is_file():
            raise HTTPException(404, "No picture")
        return FileResponse(picture, headers={'Cache-Control': 'no-cache'})

    @app.get("/api/jobs/{job_id}/shots/{shot_id}/takes", response_model=list[Take])
    async def takes(job_id: str, shot_id: str):
        """The takes that were made for a shot (not the template it replaces), with the one the edit uses."""
        job = _job(job_id)
        _, manifest = _manifest(job)
        shot = _manifest_shot(manifest, shot_id)
        source = manifest.get('source', {})
        fps = source.get('fps_num',24) / (source.get('fps_den',1) or 1)
        style = {**job.request.settings.model_dump(), **job.state.style.model_dump(exclude_none=True)}
        return [Take(id=r["revision_id"], active=r["revision_id"] == shot.get("active_revision_id"), url=f"/api/jobs/{job_id}/shots/{shot_id}/takes/{r['revision_id']}/video",
                     generation_prompt=r.get('generation_prompt', ''),
                     **trim_bounds(shot,r,style,fps))
                for r in shot.get("revisions", []) if r.get("media_range") is None]

    @app.post("/api/jobs/{job_id}/shots/{shot_id}/trim", response_model=list[Take])
    async def trim_take(job_id: str, shot_id: str, body: TrimTake):
        job = _job(job_id)
        await recover_pending(job)
        _exclusive(job)
        if job.state.status in ('queued','running'):
            raise HTTPException(409,'The job is still running')
        if any(s.id == shot_id and s.locked for s in job.state.shots):
            raise HTTPException(409,'Unlock the shot before moving its source window')
        project, _ = _manifest(job)
        def select():
            with SharedProjectRepository(project.parent).edit(project.name) as manifest:
                shot = _manifest_shot(manifest,shot_id)
                revision = next((r for r in shot.get('revisions',[]) if r['revision_id']==body.take and r.get('media_range') is None),None)
                if revision is None:
                    raise HTTPException(404,'Unknown generated take')
                if shot.get('active_revision_id') != body.take:
                    raise HTTPException(409,'Choose this take before moving its source window')
                source = manifest.get('source',{})
                fps = source.get('fps_num',24)/(source.get('fps_den',1) or 1)
                style = {**job.request.settings.model_dump(), **job.state.style.model_dump(exclude_none=True)}
                bounds = trim_bounds(shot,revision,style,fps)
                if bounds['duration'] <= 0 or body.start > bounds['max_start'] + 1e-6:
                    raise HTTPException(422,'The selected portion extends past the end of this take')
                revision['source_start_seconds'] = min(bounds['max_start'],round(body.start*fps)/fps)
        await update_project(job,select)
        return await takes(job_id,shot_id)

    @app.get("/api/jobs/{job_id}/shots/{shot_id}/takes/{take_id}/video")
    async def take_video(job_id: str, shot_id: str, take_id: str):
        project, manifest = _manifest(_job(job_id))
        take = next((r for r in _manifest_shot(manifest, shot_id).get("revisions", []) if r["revision_id"] == take_id and r.get("media_range") is None), None)
        target = (project / take["media_ref"]).resolve() if take else None
        if target is None or project not in target.parents or not target.is_file():
            raise HTTPException(404, "Unknown take")
        return FileResponse(target, media_type="video/mp4")

    @app.post("/api/jobs/{job_id}/shots/{shot_id}/active", response_model=list[Take])
    async def choose_take(job_id: str, shot_id: str, body: ActiveTake):
        """The take the edit uses for a shot. The edit itself is made again by re-edit."""
        job = _job(job_id)
        await recover_pending(job)
        _exclusive(job)
        if job.state.status in ("queued", "running"):
            raise HTTPException(409, "The job is still running")
        project, manifest = _manifest(job)
        shot = _manifest_shot(manifest, shot_id)
        if any(s.id==shot_id and s.locked for s in job.state.shots):
            raise HTTPException(409,'Unlock the shot before choosing a different take')
        if not any(r["revision_id"] == body.take and r.get("media_range") is None for r in shot.get("revisions", [])):
            raise HTTPException(404, "Unknown take")
        def select():
            with SharedProjectRepository(project.parent).edit(project.name) as manifest:
                _manifest_shot(manifest,shot_id)['active_revision_id'] = body.take
        await update_project(job, select)
        refresh_shots(job)
        return await takes(job_id, shot_id)

    def idle_timeline(job):
        _exclusive(job)
        if job.deleting or job.updating_project or store.get(job.id) is not job:
            raise HTTPException(409, 'Project files are being updated or deleted')
        if job.state.status in ('queued', 'running') or (job.task and not job.task.done()):
            raise HTTPException(409, 'Wait for the current operation before editing the montage')

    @app.get('/api/timeline-editor/{module}')
    async def timeline_editor_module(module: str):
        if module not in manual_timeline.EDITOR_MODULES:
            raise HTTPException(404, 'Unknown timeline editor module')
        path = manual_timeline.PACK / 'web' / module
        if not path.is_file():
            raise HTTPException(503, 'The adjacent VideoTools timeline editor is not installed')
        return FileResponse(path, media_type='text/javascript', headers={'Cache-Control': 'no-cache'})

    @app.get('/api/jobs/{job_id}/manual-timeline')
    async def get_manual_timeline(job_id: str):
        job = _job(job_id)
        idle_timeline(job)
        project, _ = _manifest(job)
        try:
            return await asyncio.to_thread(manual_timeline.editor_payload, project, settings.max_media_seconds)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.put('/api/jobs/{job_id}/manual-timeline')
    async def save_manual_timeline(job_id: str, body: TimelineSave):
        job = _job(job_id)
        await recover_pending(job)
        idle_timeline(job)
        project, _ = _manifest(job)
        try:
            return await update_project(job, lambda: manual_timeline.save_document(project, body.document, body.expected, body.enabled))
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @app.post('/api/jobs/{job_id}/manual-timeline/rebase')
    async def rebase_manual_timeline(job_id: str, body: TimelineVersion):
        job = _job(job_id)
        await recover_pending(job)
        idle_timeline(job)
        project, _ = _manifest(job)
        try:
            return await update_project(job, lambda: manual_timeline.rebase_document(project, body.expected))
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @app.post('/api/jobs/{job_id}/manual-timeline/render', response_model=JobState)
    async def render_manual_timeline(job_id: str, body: TimelineVersion):
        job = _job(job_id)
        await recover_pending(job)
        idle_timeline(job)
        project, manifest = _manifest(job)
        record = manual_timeline.read_record(project)
        if not record or not record['enabled'] or manual_timeline.record_token(record) != body.expected:
            raise HTTPException(409, 'Save and enable this version of the montage before rendering')
        try:
            manual_timeline.checked_document(manifest, record['document'])
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        render = getattr(runner, 'manual_edit', None)
        if not callable(render):
            raise HTTPException(409, 'Manual montage export requires the real Comfy SDK runner')
        if sum(j.state.status in ('queued', 'running') for j in store.jobs.values()) >= settings.max_active_jobs:
            raise HTTPException(429, 'The job queue is full')
        job.begin('edit')
        job.task = asyncio.create_task(render(job))
        return job.state

    @app.get('/api/jobs/{job_id}/manual-timeline/media')
    async def manual_timeline_media(job_id: str, file: str):
        project, manifest = _manifest(_job(job_id))
        if file == '@music':
            target = manual_timeline.music_file(project)
            if target is None:
                raise HTTPException(404, 'This project has no music')
        else:
            allowed = {r['media_ref'] for s in manifest['shots'] for r in s.get('revisions', [])
                       if not manifest['source'].get('template') or r.get('media_range') is None}
            if file not in allowed:
                raise HTTPException(404, 'Unknown timeline media')
            try:
                target = manual_timeline.safe_file(project, file)
            except ValueError as error:
                raise HTTPException(404, str(error)) from error
        return FileResponse(target, headers={'Cache-Control': 'no-cache'})

    @app.get("/api/jobs/{job_id}/timeline", response_model=TimelineInfo)
    async def timeline(job_id: str):
        """The tempo, and the cuts and effects of every shot, as the plan of the project has them."""
        _, manifest = _manifest(_job(job_id))
        tempo = next((float(m.group(1)) for w in manifest.get("detection", {}).get("warnings", []) if (m := re.search(r"Tempo ([\d.]+) BPM", w))), None)
        source = manifest.get("source", {})
        fps = source.get("fps_num", 24) / source.get("fps_den", 1) if source.get("fps_num") else 24.0
        shots = []
        for shot in sorted(manifest["shots"], key=lambda s: s.get("timeline_index", 0)):
            fx = (shot.get("plan") or {}).get("fx") or {}
            pieces = fx.get("sub_cuts") or []
            frames = [p.get("frames", 0) for p in pieces]
            scale = shot.get("target_duration_seconds", 0) * fps / sum(frames) if sum(frames) else 1.0
            cuts = [round(sum(frames[:i]) * scale / fps, 3) for i in range(1, len(frames))]
            effects = {"zoom" for p in pieces if any(z != 1 for z in p.get("zoom", [1]))} | {k for p in pieces for k in ("speed", "speed_ramp", "flip", "look") if k in p}
            effects |= {f"transition:{p['transition']['type']}" for p in pieces if "transition" in p}
            effects |= {"text"} if fx.get("text") else set()
            shots.append(TimelineShot(id=shot["shot_id"], cuts=cuts, effects=sorted(effects)))
        return TimelineInfo(bpm=tempo, shots=shots, beat_times=manifest.get('detection',{}).get('beat_times',[]))

    waveforms: dict[tuple[str, int, int], list[float]] = {}

    @app.get("/api/jobs/{job_id}/waveform", response_model=list[float])
    async def waveform(job_id: str, bins: int = 400):
        """The loudness of the result along its length, 0 to 1 per bin: the sound of the edit under the shots."""
        job = _job(job_id)
        video_file = settings.workspace / "jobs" / f"{job.id}.mp4"
        bins = max(20, min(bins, 2000))
        key = (job.id, job.edits, bins)
        if not video_file.is_file():
            raise HTTPException(404, "This job has no video yet")
        if key not in waveforms:
            raw = await asyncio.to_thread(lambda: subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-v", "error", "-i", str(video_file), '-t', str(settings.max_media_seconds), "-vn", "-ac", "1", "-ar", "8000", "-f", "f32le", "-"], capture_output=True,timeout=60).stdout)
            samples = array.array("f")
            samples.frombytes(raw[: len(raw) // 4 * 4])
            size = max(1, len(samples) // bins)
            peaks = [max((abs(x) for x in samples[i * size:(i + 1) * size]), default=0.0) for i in range(bins)]
            top = max(peaks, default=0.0) or 1.0
            if len(waveforms)>=32:
                waveforms.pop(next(iter(waveforms)))
            waveforms[key] = [round(p / top, 3) for p in peaks]
        return waveforms[key]

    @app.get('/api/jobs/{job_id}/review')
    async def review(job_id: str):
        job=_job(job_id)
        if job.state.status in ('queued','running'):
            raise HTTPException(409,'Wait for the current operation to finish')
        video=settings.workspace/'jobs'/f'{job.id}.mp4'
        if not video.is_file():raise HTTPException(404,'This job has no video')
        directory=settings.workspace/'reviews'/job.id
        frames=await update_project(job,lambda:build_review_frames(video,directory))
        return {'frames':[dict(f,url=f'/api/jobs/{job.id}/review/frames/{f["file"]}') for f in frames],
                'energy':job.state.energy,'warnings':job.state.warnings,
                'checks':{'technical':'decoded','identity':'human_review','text':'human_review','voice':'human_review'}}

    @app.get('/api/jobs/{job_id}/review/frames/{frame:path}')
    async def review_frame(job_id: str,frame: str):
        job=_job(job_id)
        root=(settings.workspace/'reviews'/job.id).resolve()
        path=(root/frame).resolve()
        if root not in path.parents or path.suffix!='.jpg' or not path.is_file():raise HTTPException(404,'Unknown review frame')
        return FileResponse(path)

    @app.get("/api/jobs/{job_id}/export")
    async def export(job_id: str):
        """The project to keep: the video, how it was asked for, and the manifest with the takes."""
        job = _job(job_id)
        await recover_pending(job)
        if job.state.status in ('running', 'queued'):
            raise HTTPException(409, 'Wait for the current operation before exporting the project')
        project, _ = _manifest(job)
        handle, name = tempfile.mkstemp(suffix=".zip", dir=settings.workspace)
        os.close(handle)
        archive = Path(name)
        def build():
            with FileLock(str(project / '.lock'), timeout=120), zipfile.ZipFile(archive,'w',zipfile.ZIP_STORED) as bundle:
                video_file=settings.workspace/'jobs'/f'{job.id}.mp4'
                if video_file.is_file():bundle.write(video_file,'result.mp4')
                bundle.writestr('request.json',job.request.model_dump_json(indent=1))
                manifest = json.loads((project/'manifest.json').read_text(encoding='utf-8'))
                refs = {manifest.get('source', {}).get('uri')}
                refs.update(s.get('source_media_ref') for s in manifest.get('shots', []))
                refs.update(s.get('thumbnail_ref') for s in manifest.get('shots', []))
                refs.update(r.get('media_ref') for s in manifest.get('shots', []) for r in s.get('revisions', []))
                retained = project/'music/retained.wav'
                if retained.is_file(): refs.add('music/retained.wav')
                bundle.write(project/'manifest.json','manifest.json')
                for ref in sorted(r for r in refs if r):
                    target = (project/ref).resolve()
                    if project not in target.parents or not target.is_file():
                        raise ValueError(f'Project media is missing or outside the project: {ref}')
                    bundle.write(target, target.relative_to(project).as_posix())
                request_files = {}
                given = job.request
                ids = {u for u in (given.source, given.ref_video, given.music, given.voice, *given.refs) if u}
                for upload_id in sorted(ids):
                    if upload_id not in uploads or not uploads[upload_id].is_file():
                        raise ValueError(f'An input file is missing: {upload_id}')
                    target = uploads[upload_id]
                    entry = f'inputs/{upload_id}{target.suffix.lower()}'
                    bundle.write(target, entry)
                    request_files[upload_id] = entry
                bundle.writestr('request_files.json', json.dumps(request_files, indent=2))
        building = asyncio.create_task(update_project(job, build))
        try:
            await asyncio.shield(building)
        except BaseException as error:
            # Keep the ZIP writer alive until it closes its file, even on disconnect.
            with anyio.CancelScope(shield=True):
                await asyncio.gather(building, return_exceptions=True)
                archive.unlink(missing_ok=True)
            if isinstance(error, ValueError):
                raise HTTPException(422, str(error)) from error
            raise
        return FileResponse(archive, media_type="application/zip", filename=f"{EXPORT_PREFIX}_{job.id}.zip", background=BackgroundTask(archive.unlink))

    mine = settings.workspace / "presets"

    def resolve_preset_media(value, *, strict=False):
        """Resolve server-owned upload IDs; never trust imported asset URLs."""
        value = dict(value)
        saved = value.get('inputs')
        if not isinstance(saved, dict):
            return value
        missing = []
        def resolve(item, slot, kind):
            if item is None:
                return None
            uid = item.get('id') if isinstance(item, dict) else None
            known = describe(uid)
            if known is None or known.kind != kind or not uploads[uid].is_file():
                missing.append(slot)
                return None
            return known.model_dump()
        restored = {key: resolve(saved.get(key), key, kind) for key, kind in
                    [('source','video'),('refVideo','video'),('music','audio'),('voice','audio')]}
        restored['refs'] = [resolve(item, f'reference {i+1}', 'image') for i,item in enumerate(saved.get('refs', [])[:5])]
        if strict and missing:
            raise HTTPException(422, 'Preset media missing or incompatible: ' + ', '.join(missing))
        value['inputs'] = restored
        value['missing_inputs'] = missing
        return value

    @app.get("/api/presets")
    async def presets():
        """The presets of the app, then the ones that were saved here."""
        return [resolve_preset_media(json.loads(p.read_text(encoding="utf-8"))) | {"id": p.stem, "user": False} for p in sorted((ROOT / "presets").glob("*.json"))] + \
               [resolve_preset_media(json.loads(p.read_text(encoding="utf-8"))) | {"id": f"user-{p.stem}", "user": True} for p in sorted(mine.glob("*.json"))]

    @app.get("/api/presets/media/{name}")
    async def preset_media(name: str):
        """The picture, gif or short video of a preset."""
        for folder in (ROOT / "presets" / "media", mine / "media"):
            target = (folder / name).resolve()
            if target.parent == folder.resolve() and target.is_file():
                return FileResponse(target)
        raise HTTPException(404, "Unknown preview")

    @app.post("/api/presets")
    async def save_preset(body: PresetIn):
        mine.mkdir(parents=True, exist_ok=True)
        slug = _re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-") or "preset"
        path = mine / f"{slug}.json"
        payload = resolve_preset_media(body.model_dump(), strict=True)
        write_json(path,payload)
        return payload | {"id": f"user-{slug}", "user": True}

    @app.delete("/api/presets/{preset_id}")
    async def delete_preset(preset_id: str):
        path = mine / f"{preset_id.removeprefix('user-')}.json"
        if not preset_id.startswith("user-") or path.resolve().parent != mine.resolve() or not path.is_file():
            raise HTTPException(404, "Only the presets saved here can be deleted")
        path.unlink()
        return {"deleted": preset_id}

    dist = ROOT / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    app.add_middleware(AccessMiddleware, settings=settings)
    return app
