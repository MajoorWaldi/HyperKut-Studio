"""Run a job: the plan, then one prompt per shot, then the edit, each through the Comfy SDK; or, for the development of the interface, a simulation."""
import asyncio
import contextlib
import json
import os
import logging
import tempfile
import math
import uuid
import re
from pathlib import Path
from typing import Protocol

from comfy_sdk import AsyncComfy, CancelRefused, ComfyError, JobFailed, Preview, Progress

from .config import Settings
from .jobs import Job
from .models import EditStyle, Shot
from .templates import TemplateError, applied_style, load_templates
from .direction import resolved_brief, use_prepared_brief, normalize_media_roles, apply_plan_contract
from .creative_controls import level as _level, direction as creative_direction
from .media import validate_video
from .storage import edit_manifest

logger = logging.getLogger(__name__)

# the part of the whole progress that each stage owns
SHARE = {"analyze": (0.0, 0.15), "shots": (0.15, 0.9), "edit": (0.9, 1.0)}
QUALITY_MEGAPIXELS = {"draft": 0.35, "standard": 0.6, "max": 0.98, "xhigh": 1.5}
RATIOS = {"9:16": "9:16 (Portrait Widescreen)", "16:9": "16:9 (Widescreen)", "1:1": "1:1 (Square)", "3:4": "3:4 (Portrait Standard)"}


class Runner(Protocol):
    async def run(self, job: Job) -> None: ...

    async def regenerate(self, job: Job, shots: list[str], prompts: dict[str, str]) -> None: ...

    async def re_edit(self, job: Job, style: EditStyle) -> None: ...


def _overall(stage: str, inside: float) -> float:
    start, end = SHARE[stage]
    return start + (end - start) * max(0.0, min(inside, 1.0))


class ComfyRunner:
    def __init__(self, settings: Settings, uploads: dict[str, Path], client_factory=None):
        self.settings = settings
        self.uploads = uploads
        os.environ["COMFY_BASE_URL"] = settings.proxy_url  # the SDK reads its address from this variable: without it, it talks to Comfy Cloud
        self.client_factory = client_factory or (lambda: AsyncComfy(api_key="local"))

    async def ai_candidate(self, job: Job, candidate: dict) -> None:
        from .ai_edits import generate_candidate
        await generate_candidate(self, job, candidate)

    async def manual_edit(self, job: Job) -> None:
        from .manual_timeline import render_saved_timeline
        import httpx
        client = None
        try:
            async with httpx.AsyncClient(timeout=10) as probe:
                response = await probe.get(f'{self.settings.comfyui_url}/object_info/MajoorTimelineEdit')
                response.raise_for_status()
                if 'MajoorTimelineEdit' not in response.json():
                    raise ValueError('ComfyUI has not loaded Timeline Edit yet. Restart ComfyUI to load the updated VideoTools pack, then retry; the saved montage is preserved.')
            client = self.client_factory()
            await render_saved_timeline(self, client, job)
        except asyncio.CancelledError:
            job.update(status='cancelled')
            raise
        except Exception as error:
            logger.exception('Manual timeline export %s failed', job.id)
            job.update(status='failed', error=str(error).strip() or type(error).__name__)
        finally:
            if client is not None:
                try:
                    await client.aclose()
                except Exception:
                    logger.exception('Could not close the manual timeline SDK client for %s', job.id)

    def _values(self, job: Job, style: EditStyle | None = None) -> dict:
        """The values of the interface under the names of the slots; a template only takes the names it has slots for (a mode has no slot for what it does not use)."""
        s, r = job.request.settings, job.request
        brief = resolved_brief(s)
        megapixels = QUALITY_MEGAPIXELS[s.quality]
        layers = s.motion_layers.strip()
        values = {"brief": brief, "idea": brief, "idea_creative": brief, "length": s.duration, "ratio": RATIOS[s.ratio], "megapixels": megapixels, "megapixels_creative": megapixels, "bpm": s.bpm,
                  "mood": s.mood, "seed": s.seed, "effects": s.effects, "text": s.text, "edit_sub_cuts": s.sub_cuts, "sound_design": s.sound_design, "sound_effects": s.sound_effects, "music_sync": s.music_sync, "retry_bad": s.retry_bad_takes,
                  "replace_sound": s.audio == "new", "voice_on": s.audio == "voice", "job_name": job.id, "dialogue": s.dialogue, "plates": s.places, "camera": s.camera,
                  "edit_music_volume": s.music_volume, "motion_design": s.motion_design, "motion_direction": s.motion_direction, "motion_title": s.motion_title, "motion_cues": s.motion_cues,
                  "motion_layers": layers or "[]", "extra_layers": layers or "[]", "motion_on": layers not in ("", "[]"), "subject_mask": s.subject_mask,
                  "redraw_text": s.redraw_text, "force_pose": s.pose_only, "quality_check": s.quality_check, "music_start": s.music_start, "music_energy": s.music_energy,
                  "pose_strength": round(0.4 + 0.6 * s.structure / 100, 2),  # structure: how firmly the pose of the template holds the positions of the shot
                  "reference_fidelity": _level(s.structure, ("loose", "balanced", "strict")), "creative_freedom": _level(s.creativity, ("faithful", "balanced", "free")),
                  "style": s.style, "cut_density": s.cut_density, "transition_intensity": s.transition_intensity, "narrative_coherence": "auto", "cut_every": s.cut_every, "music_shots": 0,  # candidate musical grid; the planner chooses takes from the brief
                   "text_allowed": s.text_allowed}
        files = {"source": r.source, "music": r.music, "ref_video": r.ref_video, "voice": r.voice, **{f"ref{i + 1}": u for i, u in enumerate(r.refs)}}
        files['energy_reference']=r.ref_video if s.reference_style=='montage' else None
        values.update(music_mood=s.mood,music_bpm=s.bpm,music_seed=s.seed,
                      music_context=json.dumps({'creative_brief':brief,'user_music_preference':s.mood,'duration_seconds':s.duration,'mode':r.mode,'editing_style':s.style},ensure_ascii=False))
        values['fork_project_id'] = f'p_{job.id}'
        directions=[f'Requested edit duration: {s.duration:g} seconds. Adapt the creative scope to this duration; do not invent exact musical timestamps.']
        if r.mode in ('text','music'):
            directions.append(creative_direction(s))
        if s.motion_design:
            directions.append('Animated design is enabled. Where useful, write a shot-local motion array adapted to this shot and its negative space; use local percentage timing and sync="onset" for selected accents, not every layer. Finishing direction: '+s.motion_direction)
        else:
            directions.append('Animated design is disabled: omit motion arrays; existing text controls remain authoritative.')
        if not s.text:
            directions.append('On-screen readable text is disabled.')
        if not s.effects:
            directions.append('Edit effects are off: leave out the zoom, focus, flip, speed, look and transition fields of the plan and the sub-cut effects; the cuts and the shot prompts stay.')
        if r.mode in ('text', 'music') and s.mood.strip():
            directions.append('Requested music and mood (adapt the editing energy to this and the creative brief): '+s.mood.strip())
        if s.efficient_sources:
            directions.append('For title cards, flat flashes or still-image holds, avoid video generation. Each shot may have render_source: {"kind":"graphic","text":"exact words","color":"#101018"}, {"kind":"still","asset":"ref1"}, or {"kind":"provided","asset":"ref_video"} when that user clip was supplied. All other shots use {"kind":"generated"}. Preserve exact durations. Never invent asset names or executable code.')
        if s.reference_style=='montage' and r.ref_video:
            directions.append('Use the reference video as an editing-style reference: infer pacing, relative shot lengths, camera vocabulary, palette, typography and transitions. Create a new edit suited to the brief. Preserve the identity and clothing of the supplied subject images. Keep the user music. Do not copy reference footage, logos or words; use only explicitly allowed text.')
        values['planning_instructions']='\n'.join(directions)
        values['sfx_library']=s.sfx_library
        style = style if style is not None else job.state.style
        for key, value in style.model_dump(exclude_none=True).items():
            if key == 'rendered_layers':
                continue
            values[key if key in ('motion_layers', 'motion_design', 'motion_direction', 'motion_title', 'motion_cues') else f'edit_{key}'] = value
        if style.motion_layers is not None:
            values['motion_on'] = style.motion_layers.strip() not in ('', '[]')
            values['extra_layers'] = style.motion_layers
        return values | {name: self.uploads[upload] for name, upload in files.items() if upload}

    @staticmethod
    def _absent(job: Job) -> tuple[str, ...]:
        """What was not given: the pictures, the reference video, the voice. Their nodes are taken out of the prompt, with the nodes that only they fed."""
        r = job.request
        return (*(f"ref{i + 1}" for i in range(len(r.refs), 5)), *(name for name, given in (("ref_video", r.ref_video), ("voice", r.voice),('energy_reference',r.ref_video if r.settings.reference_style=='montage' else None)) if not given))

    async def _run(self, client, job: Job, template, values: dict, stage: str, base: float = 0.0, span: float = 1.0):
        """Submit one prompt and follow it: the progress of the job moves with the nodes of the prompt."""
        given = {k: v for k, v in values.items() if k in template.slots}
        prompt = template.fill({k: v for k, v in given.items() if not isinstance(v, Path)}, tuple(n for n in self._absent(job) if n in template.slots))
        normalize_media_roles(prompt)
        apply_plan_contract(prompt, job.request.settings, mode=job.request.mode)
        rhythm_nodes = {node['class_type'] for node in prompt.values() if node['inputs'].get('music_edit_mode', 'legacy') != 'legacy'}
        if job.request.mode == 'remix' and job.request.settings.audio == 'new' and job.request.settings.music_edit_mode != 'legacy':
            rhythm_nodes.add('MajoorShotAssemble')
        dialogue_required = job.request.settings.audio == 'voice' or bool(job.request.settings.dialogue.strip())
        manual_dialogue = False
        for node in prompt.values():
            if node.get('class_type') == 'MajoorTimelineEdit':
                text = node['inputs'].get('edit_json', '')
                if isinstance(text, str) and text.strip():
                    document = json.loads(text)
                    manual_dialogue |= isinstance(document, dict) and 'dialogue' in document
        if rhythm_nodes or dialogue_required or manual_dialogue:
            import httpx
            async with httpx.AsyncClient(timeout=10) as probe:
                for node_type in sorted(rhythm_nodes | ({'MajoorShotAssemble'} if dialogue_required or manual_dialogue else set())):
                    response = await probe.get(f'{self.settings.comfyui_url}/object_info/{node_type}')
                    response.raise_for_status()
                    schema = response.json().get(node_type, {}).get('input', {})
                    if node_type in rhythm_nodes and 'music_edit_mode' not in schema.get('optional', {}):
                        raise ValueError('ComfyUI has not loaded the music rhythm modes yet. Restart ComfyUI to load the updated VideoTools pack, then retry. No generation has been submitted.')
                    if node_type == 'MajoorShotAssemble' and (dialogue_required or manual_dialogue) and not {'dialogue', 'preserve_dialogue'} <= schema.get('optional', {}).keys():
                        raise ValueError('ComfyUI has not loaded the independent dialogue track yet. Restart ComfyUI to load the updated VideoTools pack, then retry. No generation has been submitted.')
        use_prepared_brief(prompt, resolved_brief(job.request.settings) if job.request.settings.approved_brief else "")
        workflow = client.workflows.from_json(prompt)
        for name, path in ((k, v) for k, v in given.items() if isinstance(v, Path)):
            for node, field in template.slots[name]:
                if node in prompt:
                    workflow.set_input(node, field, client.assets.from_file(path))
        submit_options = {}
        if callable(getattr(client, 'list_jobs', None)):
            key = f'secator-{job.id}-{uuid.uuid4().hex}'
            job.record_submission(key)
            submit_options = {'idempotency_key': key}
            if self.settings.job_metadata_labels:
                submit_options['metadata'] = {'secator_submission': key}
        submitting = asyncio.ensure_future(client.submit(workflow, **submit_options))
        try:
            handle = await asyncio.shield(submitting)
        except asyncio.CancelledError:  # cancelled while the prompt was being sent: it is queued all the same, so it is the one to cancel
            handle = await asyncio.shield(submitting)
            job.record_handle(handle.id)
            with contextlib.suppress(ComfyError, TimeoutError):
                await asyncio.shield(self._cancel_handle(job, handle))
            raise
        except Exception as error:
            # The SDK stamps POST-attempt failures with their key. Local validation
            # failures have none; definite rejections did not create a request.
            status = getattr(error, 'http_status', None)
            rejected = status in (400, 401, 403, 413, 422, 429) and getattr(error, 'code', None) != 'idempotency_key_reuse'
            if submit_options and (getattr(error, 'idempotency_key', None) is None or rejected):
                job.record_handle(None)
            raise
        try:
            job.record_handle(handle.id)
            job.update(status="running", stage=stage)
            async for event in handle.events():
                if isinstance(event, Progress):
                    inside = base + span * ((event.nodes_done or 0) + (event.step / event.steps if event.step and event.steps else 0.0)) / max(event.nodes_total or 1, 1)
                    job.update(progress=_overall(stage, inside), node=event.current_node, step=event.step, steps=event.steps)
                elif isinstance(event, Preview):
                    job.preview = (event.content_type, event.data)
                    job.update(preview=job.state.preview + 1)
            await handle.result()  # raises JobFailed with the node and the message when the prompt did not succeed
        except asyncio.CancelledError:
            with contextlib.suppress(ComfyError, TimeoutError):
                await asyncio.shield(self._cancel_handle(job, handle))
            raise
        except JobFailed as failed:
            job.record_handle(None)
            raise ComfyError(self._explain(failed, stage)) from failed
        except Exception:
            # A failed progress/state write must not leave an untracked GPU calculation.
            # If cancellation cannot be confirmed, keep its persisted handle for recovery.
            try:
                await asyncio.wait_for(self._cancel_handle(job, handle), timeout=10)
            except Exception:
                logger.exception('Could not reconcile SDK request %s for job %s', handle.id, job.id)
            raise
        await handle.refresh()  # the outputs of the handle are read once the job is over: without this it has none
        job.record_handle(None)
        return handle

    async def _cancel_handle(self, job: Job, handle) -> None:
        with contextlib.suppress(CancelRefused):
            await handle.cancel()
        await handle.wait(timeout=8)
        job.record_handle(None)

    async def recover(self, job: Job) -> None:
        """Reconcile only the SDK request persisted by this Studio job."""
        client = self.client_factory()
        try:
            if not job.pending_handle and job.submission_key:
                if not self.settings.job_metadata_labels:
                    raise ComfyError('Submission outcome is uncertain. This proxy exposes no submission labels; check its job history. No automatic resubmission.')
                found = []
                async for summary in client.list_jobs(metadata={'secator_submission': job.submission_key}, limit=100):
                    found.append(summary.id)
                    if len(found) > 1:
                        break
                if len(found) != 1:
                    raise ComfyError('Submission outcome is uncertain. No automatic resubmission; check the local proxy job history.')
                job.record_handle(found[0])
            handle = await client.jobs.get(job.pending_handle)
            await self._cancel_handle(job, handle)
        finally:
            await client.aclose()

    @staticmethod
    def _explain(failed: JobFailed, stage: str) -> str:
        """What went wrong, where: the message of the node that failed."""
        error = failed.error
        if error is None or not error.message:
            return f"The prompt of the stage '{stage}' failed"
        return f"{error.message.strip()}" + (f" (node {error.node_id})" if error.node_id else "")

    async def _edit(self, client, job: Job, templates, values: dict, style: EditStyle | None = None) -> None:
        """The edit of the project as it is on the disk now, saved as the video of the job."""
        from .manual_timeline import read_record, render_saved_timeline
        if job.state.project_id:
            record = read_record(self.projects() / job.state.project_id)
            if record and record['enabled']:
                await render_saved_timeline(self, client, job)
                return
        values = dict(values)
        from .unified_motion import finishing_layers, needs_subject_mask
        requested_text = values.get('edit_text', values.get('text', True))
        path = self.projects() / job.state.project_id / 'manifest.json' if job.state.project_id else None
        manifest = json.loads(path.read_text(encoding='utf-8')) if path and path.is_file() else {}
        configured = json.loads(values.get('motion_layers','[]') or '[]')
        if isinstance(configured,dict) and configured.get('accent_from_subject') and 'accent' not in configured:
            direction_text=values.get('motion_direction','editorial')
            explicit_accent=bool(re.search(r'#[0-9a-fA-F]{6}',direction_text))
            if not explicit_accent and job.request.refs:
                reference=self.uploads.get(job.request.refs[0])
                if reference:
                    from .motion_presets import subject_accent
                    try: color=subject_accent(reference)
                    except (OSError,ValueError): color=None
                    if color:
                        configured['accent']=color
                        values['motion_layers']=json.dumps(configured)
                        from .motion_presets import with_motion_accent
                        values['motion_direction']=with_motion_accent(direction_text,color)
        if isinstance(configured,dict) and configured.get('pack') and 'accent' not in configured:
            match=re.search(r'#[0-9a-fA-F]{6}',values.get('motion_direction',''))
            if match:
                configured['accent']=match.group()
                values['motion_layers']=json.dumps(configured)
        values['unified_layers'] = finishing_layers(manifest, job.state.shots, values.get('motion_layers', '[]'), requested_text, values.get('motion_design', True))
        values['subject_mask'] = needs_subject_mask(values['unified_layers'])
        values['edit_text'] = False  # planned typography is drawn once, in HyperFrames
        direction = values.get('motion_direction', 'editorial')
        if values.get('motion_title') and requested_text:
            # Explicit title only; the visual brief never invents advertising copy.
            if direction.lstrip().startswith('{'):
                spec = json.loads(direction)
            else:
                spec = {'preset': direction} if direction in ('minimal', 'editorial', 'energetic') else None
            if spec is not None:
                direction = json.dumps({**spec, 'title': values['motion_title']})
        if not requested_text:
            values['redraw_text'] = False
            values['motion_cues'] = '[]'
            if direction.lstrip().startswith('{'):
                spec = json.loads(direction)
                spec.pop('title', None)
                direction = json.dumps(spec)
        values['hyperframes_direction'] = direction
        values['motion_timeline'] = json.dumps([{'id': s.id, 'start': s.start, 'duration': s.duration} for s in job.state.shots])
        final = await self._run(client, job, templates["final"], {**values, "project_id": job.state.project_id}, "edit")
        save = templates["final"].slots.get("save")
        outputs = final.get_outputs(save[0][0]) if save else []
        if not outputs:
            raise ComfyError('SaveVideo returned no video output')
        destination = self.video_path(job)
        fd, name = tempfile.mkstemp(dir=destination.parent, suffix='.mp4')
        os.close(fd)
        tmp = Path(name)
        try:
            await outputs[0].to_file(tmp)
            validation = asyncio.create_task(asyncio.to_thread(validate_video, tmp))
            try:
                await asyncio.shield(validation)
            except asyncio.CancelledError:
                await asyncio.gather(validation, return_exceptions=True)
                raise
            os.replace(tmp, destination)
        finally:
            tmp.unlink(missing_ok=True)
        applied = applied_style(templates["final"], {**values, "project_id": job.state.project_id})
        report_path = self.projects() / job.state.project_id / 'exports/hyperframes.json' if job.state.project_id else None
        finishing_active = values.get('motion_design', True) or bool(json.loads(values['unified_layers'])) or (job.request.mode == 'remix' and values.get('redraw_text', False))
        applied['rendered_layers'] = '[]'
        if finishing_active and report_path and report_path.is_file():
            report = json.loads(report_path.read_text(encoding='utf-8'))
            applied['rendered_layers'] = json.dumps(report.get('layers', []), ensure_ascii=False, indent=2)
        applied['text'] = requested_text
        applied.update({key: values.get(key, default) for key, default in (('motion_design', True), ('motion_direction', 'editorial'), ('motion_title', ''), ('motion_cues', '[]'), ('motion_layers', '[]'))})
        style = EditStyle(**{**applied, **{k: v for k, v in job.state.style.model_dump(exclude_none=True).items() if k == "motion_layers"}, **(style.model_dump(exclude_none=True, exclude={'rendered_layers'}) if style is not None else {})})
        job.edits += 1
        energy_path=self.projects()/job.state.project_id/'exports/energy.json'
        energy=json.loads(energy_path.read_text(encoding='utf-8')) if energy_path.is_file() else None
        job.update(status='succeeded', stage='done', progress=1.0, output_url=f'/api/jobs/{job.id}/video?v={job.edits}',energy=energy, style=style, manual_export=None)

    async def run(self, job: Job) -> None:
        client = None
        try:
            client = self.client_factory()
            if job.state.status != 'running':
                job.begin('analyze')
            templates = load_templates(self.settings.templates_dir, job.request.mode)
            values = self._values(job)
            job.update(status="running", stage="analyze")
            await self._run(client, job, templates["stage1"], values, "analyze")
            info = json.loads((self.projects() / "_jobs" / f"{job.id}.json").read_text(encoding="utf-8"))
            shots = [Shot(id=s['id'], start=s['start'], duration=s['duration'], prompt=s.get('prompt',''), generation_prompt=s.get('generation_prompt',''), generation_frames=s.get('generation_frames',0),render_source=s.get('render_source','generated'), thumb=f'/api/jobs/{job.id}/shots/{s["id"]}/thumb') for s in info['shots']]
            if not shots:
                raise ValueError('The plan contains no shots')
            frames = [(s.generation_frames or max(124,5+17*math.ceil(max(s.duration*24-5,0)/17))) if s.render_source=='generated' else 0 for s in shots]
            seconds = sum(frames)/24
            retry = job.request.settings.quality_check if job.request.mode=='remix' else job.request.settings.retry_bad_takes
            job.update(project_id=info['project_id'], shots=shots, generation_budget={'seconds':round(seconds,2),'with_retries':round(seconds*(2 if retry else 1),2),'final_seconds':round(sum(s.duration for s in shots),2)})
            for i, shot in enumerate(shots):
                await self._run(client, job, templates['shot' if shot.render_source=='generated' else 'local'], {**values, 'shot_id': shot.id, 'shot_start':shot.start,'shot_duration':shot.duration,'project_id':info['project_id'],'job_name':f'{job.id}_shot'}, 'shots', i/len(shots),1/len(shots))
                self._mark(job, shot.id)
            await self._edit(client, job, templates, values)
        except Exception as error:
            logger.exception('Job %s failed', job.id)
            job.update(status="failed", error=str(error).strip() or f"The local generation stopped ({type(error).__name__}). Saved takes are preserved; check the connection before retrying.")
        except asyncio.CancelledError:
            job.update(status="cancelled")
            raise
        finally:
            if client is not None:
                with contextlib.suppress(Exception):
                    await client.aclose()

    async def regenerate(self, job: Job, shots: list[str], prompts: dict[str, str]) -> None:
        """Make the given shots again, with their own prompt if it was edited and another seed, then the edit: the other shots keep the take they have."""
        client = None
        try:
            client = self.client_factory()
            if job.state.status != 'running':
                job.begin('shots')
            templates = load_templates(self.settings.templates_dir, job.request.mode)
            values = self._values(job)
            job.update(status="running", stage="shots", progress=0.0, error=None)
            for i, shot_id in enumerate(shots):
                shot = next(s for s in job.state.shots if s.id == shot_id)
                previous = await asyncio.to_thread(self._set_prompt, job.state.project_id, shot_id, prompts[shot_id]) if shot_id in prompts else None
                try:
                    await self._run(client, job, templates['shot' if shot.render_source=='generated' else 'local'], {**values, "shot_id": shot_id, 'shot_start':shot.start,'shot_duration':shot.duration, "project_id": job.state.project_id, "job_name": f"{job.id}_shot", "seed": (job.request.settings.seed + 1000 * job.state.operation + i) % (2**63)},
                                    "shots", i / len(shots), 1 / len(shots))
                except BaseException:
                    if previous is not None:
                        restore = asyncio.create_task(asyncio.to_thread(self._restore_prompt, job.state.project_id, shot_id, prompts[shot_id], previous))
                        await asyncio.shield(restore)
                    self._sync_shots(job)
                    raise
                self._mark(job, shot_id, prompts.get(shot_id))
            await self._edit(client, job, templates, values)
        except Exception as error:
            logger.exception('Regeneration %s failed', job.id)
            job.update(status="failed", error=str(error).strip() or f"The local generation stopped ({type(error).__name__}). Saved takes are preserved; check the connection before retrying.")
        except asyncio.CancelledError:
            job.update(status="cancelled")
            raise
        finally:
            if client is not None:
                with contextlib.suppress(Exception):
                    await client.aclose()

    async def re_edit(self, job: Job, style: EditStyle) -> None:
        """The edit again with another style: the takes stay as they are, only the last prompt runs."""
        client = None
        previous_style = job.state.style
        try:
            client = self.client_factory()
            if job.state.status != 'running':
                job.begin('edit')
            templates = load_templates(self.settings.templates_dir, job.request.mode)
            changes = style.model_dump(exclude_none=True)
            candidate_style = previous_style.model_copy(update=changes)
            values = self._values(job, candidate_style)
            await self._edit(client, job, templates, values, candidate_style)
        except Exception as error:
            logger.exception('Re-edit %s failed', job.id)
            job.update(status='failed', error=str(error).strip() or f"The local generation stopped ({type(error).__name__}). Saved takes are preserved; check the connection before retrying.", style=previous_style)
        except asyncio.CancelledError:
            job.update(status='cancelled', style=previous_style)
            raise
        finally:
            if client is not None:
                with contextlib.suppress(Exception):
                    await client.aclose()

    def _mark(self,job: Job, shot_id: str, prompt: str | None = None) -> None:
        """The shot has one more take; its version is the one the interface shows."""
        job.update(shots=[s.model_copy(update={"done": True, "takes": s.takes + 1, "version": s.takes + 1, **({"prompt": prompt} if prompt else {})}) if s.id == shot_id else s for s in job.state.shots])
        self._sync_shots(job)
        plate=self.projects()/job.state.project_id/'logs/plate_checks'/f'{shot_id}.json'
        if plate.is_file():
            result=json.loads(plate.read_text(encoding='utf-8'))
            if result['status']!='clear':
                warning=f'{shot_id}: location image not used ({result["reason"]})'
                job.update(warnings=list(dict.fromkeys([*job.state.warnings,warning])))

    def _sync_shots(self, job: Job) -> None:
        path = self.projects() / job.state.project_id / 'manifest.json'
        if path.is_file():
            job.sync_shots(json.loads(path.read_text(encoding='utf-8')))

    def video_path(self, job: Job) -> Path:
        path = self.settings.workspace / "jobs" / f"{job.id}.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def projects(self) -> Path:
        """The folder of the projects of the pack: ComfyUI writes there, the app reads it from the disk they share."""
        if self.settings.output_dir is None:
            raise OSError("The output folder of ComfyUI is unknown: set SECATOR_OUTPUT_DIR")
        return self.settings.output_dir / "MajoorVideoTools"

    def _set_prompt(self, project_id: str, shot_id: str, text: str):
        """The prompt of a shot is in the plan of the manifest of its project, and the prompt of a shot reads the project from the disk: an edit there is what the next take follows."""
        with edit_manifest(self.projects(), project_id) as manifest:
            shot = next((s for s in manifest['shots'] if s['shot_id'] == shot_id), None)
            if shot is None:
                raise ValueError(f'Unknown shot {shot_id}')
            previous = (dict(shot.get('plan') or {}), shot.get('active_revision_id'))
            shot['plan'] = {**previous[0], 'prompt': text}
        return previous

    def _restore_prompt(self, project_id: str, shot_id: str, text: str, previous) -> None:
        with edit_manifest(self.projects(), project_id) as manifest:
            shot = next(s for s in manifest['shots'] if s['shot_id'] == shot_id)
            if shot.get('active_revision_id') == previous[1] and (shot.get('plan') or {}).get('prompt') == text:
                shot['plan'] = previous[0]


class MockRunner:
    """The same stages and the same events without a GPU: for the interface, its tests and a demo of the screens."""

    def __init__(self, pace: float = 0.4, shots: int = 7):
        self.pace, self.count = pace, shots

    async def run(self, job: Job) -> None:
        try:
            job.update(status="running", stage="analyze", project_id="p_mock")
            for step in range(5):
                await asyncio.sleep(self.pace)
                job.update(progress=_overall("analyze", (step + 1) / 5), node="plan", step=step + 1, steps=5)
            length = job.request.settings.duration / self.count
            shots = [Shot(id=f"SHOT_{i + 1:03d}", start=i * length, duration=length, prompt=f"Shot {i + 1}") for i in range(self.count)]
            job.update(shots=shots, stage="shots")
            for i in range(self.count):
                await asyncio.sleep(self.pace)
                job.update(progress=_overall("shots", (i + 1) / self.count), shots=[s.model_copy(update={"done": True, "takes": 1}) if s.id == shots[i].id else s for s in job.state.shots])
            job.update(stage="edit")
            await asyncio.sleep(self.pace)
            job.update(status="succeeded", stage="done", progress=1.0)
        except asyncio.CancelledError:
            job.update(status="cancelled")
            raise

    async def regenerate(self, job: Job, shots: list[str], prompts: dict[str, str]) -> None:
        try:
            job.update(status="running", stage="shots", progress=0.0)
            for shot_id in shots:
                await asyncio.sleep(self.pace)
                job.update(shots=[s.model_copy(update={"takes": s.takes + 1, "version": s.takes + 1, **({"prompt": prompts[shot_id]} if shot_id in prompts else {})}) if s.id == shot_id else s for s in job.state.shots])
            job.update(status="succeeded", stage="done", progress=1.0)
        except asyncio.CancelledError:
            job.update(status="cancelled")
            raise

    async def re_edit(self, job: Job, style: EditStyle) -> None:
        try:
            job.update(status="running", stage="edit", progress=SHARE["edit"][0], style=job.state.style.model_copy(update=style.model_dump(exclude_none=True)))
            await asyncio.sleep(self.pace)
            job.update(status="succeeded", stage="done", progress=1.0)
        except asyncio.CancelledError:
            job.update(status="cancelled")
            raise
