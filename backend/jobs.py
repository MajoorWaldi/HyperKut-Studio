"""The jobs of the app: their state, and the stream of that state for the interface (server-sent events)."""
import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from .models import EditStyle, JobRequest, JobState
from .storage import write_json

logger = logging.getLogger(__name__)


class Job:
    def __init__(self, request: JobRequest, state: JobState | None = None):
        self.id = state.id if state else uuid.uuid4().hex[:12]
        self.request = request
        self.state = state or JobState(id=self.id,mode=request.mode,created_at=time.time(),style=EditStyle(sub_cuts=request.settings.sub_cuts,effects=request.settings.effects,text=request.settings.text,auto_sfx=request.settings.sound_effects,motion_layers=request.settings.motion_layers,music_volume=request.settings.music_volume,motion_design=request.settings.motion_design,motion_direction=request.settings.motion_direction,motion_title=request.settings.motion_title,motion_cues=request.settings.motion_cues))
        if state is not None:
            # Older saved jobs did not copy layer JSON into their displayed style.
            # Restore only missing values; explicit edits remain authoritative.
            fields = ('motion_layers', 'motion_cues', 'motion_design', 'motion_direction', 'motion_title', 'music_volume')
            missing = {key: getattr(request.settings, key) for key in fields if getattr(state.style, key) is None}
            if missing:
                self.state = state.model_copy(update={'style': state.style.model_copy(update=missing)})
        self.store: JobStore | None = None
        self.preview: tuple[str, bytes] | None = None  # the last preview picture of the prompt that runs: not kept on the disk
        self.task: asyncio.Task | None = None
        self.edits = 0  # how many times the edit was made: the address of the video changes with it
        self.pending_handle: str | None = None
        self.submission_key: str | None = None
        self.deleting = False
        self.updating_project = False
        self._listeners: list[asyncio.Queue[JobState]] = []
        self._last_progress_write = 0.0
        self._progress_deferred = False

    def begin(self, stage: str) -> None:
        self.preview = None
        self.state = self.state.model_copy(update={'progress': 0.0, 'step': None, 'steps': None, 'node': None, 'preview': 0, 'operation': self.state.operation + 1})
        self.update(status='running', stage=stage, error=None)

    def record_handle(self, handle_id: str | None) -> None:
        self.pending_handle = handle_id
        self.submission_key = None
        if self.store:
            self.store.save(self)

    def record_submission(self, key: str) -> None:
        self.submission_key = key
        if self.store:
            self.store.save(self)

    def sync_shots(self, manifest: dict) -> None:
        by_id = {s['shot_id']: s for s in manifest.get('shots', [])}
        # Experimental raw-shot replacements can change playback duration without
        # rewriting the generation's source coordinates or target durations.
        editorial = {}
        if any(r.get('label', '').startswith('ai-edit:') for row in by_id.values() for r in row.get('revisions', [])):
            cursor = 0.
            for row in sorted(by_id.values(), key=lambda s: s.get('timeline_index', 0)):
                active = next((r for r in row.get('revisions', []) if r['revision_id'] == row.get('active_revision_id')), {})
                duration = (float(active['actual_duration_seconds']) - float(active.get('source_start_seconds', 0))
                            if active.get('duration_policy') == 'keep_generated' else float(row['target_duration_seconds']))
                editorial[row['shot_id']] = {'start': cursor, 'duration': duration}
                cursor += duration
        shots = []
        for shot in self.state.shots:
            row = by_id.get(shot.id)
            if row is None:
                shots.append(shot)
                continue
            takes = [r for r in row.get('revisions', []) if r.get('media_range') is None]
            active = row.get('active_revision_id') or ''
            version = int(active.removeprefix('take_')) if active.startswith('take_') and active.removeprefix('take_').isdigit() else 0
            prompt = (row.get('plan') or {}).get('prompt', shot.prompt)
            active_take = next((r for r in row.get('revisions', []) if r['revision_id'] == active), {})
            shots.append(shot.model_copy(update={'takes': len(takes), 'version': version,
                'done': any(r['revision_id'] == active for r in takes),
                'generation_prompt': active_take.get('generation_prompt', ''),
                'prompt': prompt if isinstance(prompt, str) else shot.prompt, **editorial.get(shot.id, {})}))
        if shots != self.state.shots:
            self.update(shots=shots)

    def update(self, **changes) -> None:
        """Change the state and tell everyone who follows the job. The progress never goes back (the nodes of one prompt count from zero again for the next one)."""
        if "progress" in changes:
            changes["progress"] = max(changes["progress"], self.state.progress)
        self.state = self.state.model_copy(update=changes)
        if self.store:
            critical = bool(set(changes) - {'progress', 'node', 'step', 'steps', 'preview'})
            now = time.monotonic()
            if critical or now - self._last_progress_write >= 1:
                self._last_progress_write = now
                try:
                    self.store.save(self)
                    self._progress_deferred = False
                except PermissionError:
                    if critical:
                        raise
                    # Handles and stage/result transitions are persisted separately.
                    # A cosmetic progress sample must not cancel a valid GPU request.
                    if not self._progress_deferred:
                        logger.warning('Progress persistence deferred by a file lock for job %s', self.id)
                    self._progress_deferred = True
        for queue in self._listeners:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(self.state)

    async def events(self) -> AsyncIterator[JobState]:
        queue: asyncio.Queue[JobState] = asyncio.Queue(maxsize=1)
        self._listeners.append(queue)
        try:
            yield self.state
            while self.state.status in ("queued", "running"):
                state = await queue.get()
                yield state
        finally:
            self._listeners.remove(queue)


class JobStore:
    """The jobs, in memory and in `directory`: a job that was not over when the server stopped comes back as cancelled, the others can be opened and worked on again."""

    def __init__(self, directory: Path | None = None):
        self.jobs: dict[str, Job] = {}
        self.directory = directory
        self.load_errors: list[str] = []
        for path in sorted(directory.glob("*.json")) if directory else []:
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
                state = JobState.model_validate(saved["state"])
                request = JobRequest.model_validate(saved['request'])
                if path.stem != state.id or not state.id.isalnum():
                    raise ValueError('Invalid saved job id')
            except (ValueError, KeyError, TypeError, OSError) as error:
                self.load_errors.append(f'{path.name}: {error}')
                continue
            if state.status in ("queued", "running"):
                state = state.model_copy(update={"status": "cancelled", "error": "The server stopped while this job was running"})
            if not state.created_at:  # a job kept before the date was recorded
                state = state.model_copy(update={"created_at": path.stat().st_mtime})
            job = Job(request, state)
            job.store = self
            job.edits = saved.get("edits", 0)
            job.pending_handle = saved.get('pending_handle')
            job.submission_key = saved.get('submission_key')
            self.jobs[job.id] = job

    def save(self, job: Job) -> None:
        if self.directory:
            self.directory.mkdir(parents=True, exist_ok=True)
            write_json(self.directory / f'{job.id}.json', {'request': job.request.model_dump(), 'state': job.state.model_dump(), 'edits': job.edits, 'pending_handle': job.pending_handle, 'submission_key': job.submission_key})

    def create(self, request: JobRequest) -> Job:
        job = Job(request)
        job.store = self
        self.jobs[job.id] = job
        self.save(job)
        return job

    def delete(self, job: Job) -> None:
        self.jobs.pop(job.id, None)
        if self.directory:
            (self.directory / f"{job.id}.json").unlink(missing_ok=True)

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)
