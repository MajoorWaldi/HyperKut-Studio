"""Opt-in raw-shot AI candidates. Generation never activates or overwrites a take."""
import asyncio
import copy
import hashlib
import json
import logging
import math
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from .media import media_info, validate_video
from .storage import edit_manifest, write_json
from .templates import Template, TemplateError, load_templates

logger = logging.getLogger(__name__)


def digest_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return 'sha256:' + digest.hexdigest()


def safe_media(project: Path, relative: str) -> Path:
    path = (project / relative).resolve()
    if not path.is_relative_to(project.resolve()) or not path.is_file():
        raise ValueError('The take media is missing or outside its project')
    return path


def candidate_file(project, candidate_id):
    if not re.fullmatch(r'[0-9a-f]{24}', candidate_id):
        raise ValueError('Invalid candidate id')
    return project / 'experiments' / 'ai_edit' / candidate_id / 'candidate.json'


def read_candidate(project, candidate_id):
    path = candidate_file(project, candidate_id)
    if not path.is_file():
        raise ValueError('Unknown AI candidate')
    return json.loads(path.read_text(encoding='utf-8'))


def source_stamp(shot):
    selected = next((r for r in shot['revisions'] if r['revision_id'] == shot['active_revision_id']), None)
    return hashlib.sha256(json.dumps([shot['shot_id'], shot.get('start_frame'), shot.get('end_frame_exclusive'),
        shot.get('target_duration_seconds'), (shot.get('plan') or {}).get('render_source'), selected], sort_keys=True).encode()).hexdigest()


def prepare_candidate(project, manifest, shot_id, request):
    shot = next(s for s in manifest['shots'] if s['shot_id'] == shot_id)
    if ((shot.get('plan') or {}).get('render_source') or {'kind': 'generated'}).get('kind') != 'generated':
        raise ValueError('This experiment cannot replace a local or provided shot source')
    if shot['active_revision_id'] != request.take:
        raise ValueError('Choose this take before requesting an AI candidate')
    revision = next(r for r in shot['revisions'] if r['revision_id'] == request.take)
    if revision.get('media_range') is not None:
        raise ValueError('This experiment requires a generated take, not source footage or a placeholder')
    media = safe_media(project, revision['media_ref'])
    info = media_info(media)
    start = float(revision.get('source_start_seconds', 0))
    duration = info['video_duration']
    window = duration - start if revision.get('duration_policy') == 'keep_generated' else float(shot['target_duration_seconds'])
    frames = round(window * 24)
    if not math.isfinite(start) or start < 0 or frames < 1 or frames > 24 * 60 or start + frames / 24 > duration + .001:
        raise ValueError('The raw take window must fit its media and be at most 60 seconds')
    if info['width'] < 2 or info['height'] < 2 or info['width'] % 2 or info['height'] % 2:
        raise ValueError('This H264 experiment requires even source video dimensions')
    added = round(request.seconds * 24)
    needed = frames if request.operation == 'regenerate' else added + 1
    generation_frames = max(124, 5 + 17 * math.ceil(max(0, needed - 5) / 17))
    if generation_frames > 362:
        raise ValueError('This H3 experiment limits one generated segment to its trained range (362 frames at 24 fps)')
    cid = uuid.uuid4().hex[:24]
    return {'id': cid, 'created_at': time.time(), 'shot_id': shot_id, 'operation': request.operation, 'status': 'queued',
            'take': request.take, 'source_stamp': source_stamp(shot), 'source_digest': digest_file(media),
            'source_file': revision['media_ref'], 'source_start': start, 'source_frames': frames,
            'extension_frames': added, 'generation_frames': generation_frames,
            'generated_seconds': generation_frames / 24, 'fps': 24,
            'width': info['width'], 'height': info['height'],
            'prompt': request.prompt, 'seed': request.seed, 'error': None, 'revision_id': None}


def candidate_template(template, candidate, reference_count):
    """Keep only one configured H3 chain; no planner, plate, judge or Apply node."""
    graph = copy.deepcopy(template.prompt)
    if not 0 <= reference_count <= 5:
        raise TemplateError('AI Edit supports at most five identity reference images')
    videos = [(key, node) for key, node in graph.items() if node['class_type'] == 'CreateVideo'
              and isinstance(node['inputs'].get('images'), list)]
    if not videos:
        raise TemplateError('The configured template has no H3 video output')
    video_id, video = videos[0]
    decode = graph[str(video['inputs']['images'][0])]
    sampler_id = str(decode['inputs']['samples'][0])
    sampler = graph[sampler_id]
    if sampler['class_type'] != 'SamplerCustomAdvanced':
        raise TemplateError('AI Edit expects the configured H3 advanced sampler')
    guider = graph[str(sampler['inputs']['guider'][0])]
    conditioning_link = guider['inputs']['conditioning']
    condition_id = str(conditioning_link[0])
    condition = graph[condition_id]
    if condition['class_type'] != 'MiniMaxH3ReferenceToVideo':
        raise TemplateError('AI Edit requires a direct MiniMaxH3ReferenceToVideo conditioning chain')
    inputs = condition['inputs']
    inputs.update(prompt=candidate['prompt'], width=max(32, round(candidate['width'] / 32) * 32),
                  height=max(32, round(candidate['height'] / 32) * 32), length=candidate['generation_frames'])
    allowed_refs = {f'ref_images.ref_image_{i}' for i in range(reference_count)}
    for field in list(inputs):
        if field.startswith(('ref_images.', 'ref_videos.', 'ref_audios.', 'ref_video_audios.')) and field not in allowed_refs:
            del inputs[field]
    # Pose control belongs to remix replacement, not temporal continuation.
    for node in graph.values():
        for field, value in list(node['inputs'].items()):
            if isinstance(value, list) and str(value[0]) in graph and graph[str(value[0])]['class_type'] == 'MiniMaxH3FunControlNetApply':
                node['inputs'][field] = copy.deepcopy(graph[str(value[0])]['inputs']['model'])
    noise = graph[str(sampler['inputs']['noise'][0])]
    noise['inputs']['noise_seed'] = candidate['seed']
    # Both chains use the same latent; the guide modifies conditioning only.
    if candidate['operation'] != 'regenerate':
        graph['ai_boundary'] = {'class_type': 'LoadImage', 'inputs': {'image': ''}}
        graph['ai_guide'] = {'class_type': 'MiniMaxH3AddGuide', 'inputs': {
            'positive': conditioning_link, 'latent': sampler['inputs']['latent_image'],
            'vae': inputs['vae'], 'image': ['ai_boundary', 0],
            'frame_idx': 0 if candidate['operation'] == 'extend_after' else -1}}
        guider['inputs']['conditioning'] = ['ai_guide', 0]
    graph['ai_save'] = {'class_type': 'SaveVideo', 'inputs': {
        'video': [video_id, 0], 'filename_prefix': f'MajoorVideoTools/_ai_candidates/{candidate["id"]}',
        'format': 'mp4', 'codec': 'h264'}}
    needed = set()

    def visit(key):
        if key in needed:
            return
        if key not in graph:
            raise TemplateError(f'AI candidate has a missing dependency: {key}')
        needed.add(key)
        for value in graph[key]['inputs'].values():
            if isinstance(value, list):
                visit(str(value[0]))
    visit('ai_save')
    graph = {key: value for key, value in graph.items() if key in needed}
    forbidden = {'MajoorApplyShotMetadata', 'MajoorSaveProjectInfo', 'MajoorShotAssemble', 'MajoorHyperFrames', 'MajoorLoadShotList'}
    if any(n['class_type'] in forbidden for n in graph.values()):
        raise TemplateError('The candidate graph still depends on project mutation or assembly')
    slots = {name: tuple((node, field) for node, field in targets if node in needed)
             for name, targets in template.slots.items() if name.startswith('ref') and name[3:].isdigit()}
    slots = {name: targets for name, targets in slots.items() if targets}
    if any(f'ref{i + 1}' not in slots for i in range(reference_count)):
        raise TemplateError('The configured template is missing an identity reference slot')
    if 'ai_boundary' in needed:
        slots['boundary'] = (('ai_boundary', 'image'),)
    return Template(graph, slots)


async def media_task(function, *args):
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await asyncio.gather(task, return_exceptions=True)
        raise


def ffmpeg(arguments):
    result = subprocess.run([shutil.which('ffmpeg') or 'ffmpeg', '-v', 'error', '-y', *arguments],
                            capture_output=True, timeout=180)
    if result.returncode:
        raise ValueError('AI edit media processing failed: ' + result.stderr.decode(errors='replace')[-600:])


def boundary_frame(source, candidate, destination):
    frame = candidate['source_frames'] - 1 if candidate['operation'] == 'extend_after' else 0
    at = candidate['source_start'] + frame / 24
    ffmpeg(['-ss', f'{at:.9f}', '-i', str(source), '-frames:v', '1', str(destination)])
    if not destination.is_file():
        raise ValueError('Could not extract the extension boundary image')


def video_frames(path):
    result = subprocess.run([shutil.which('ffprobe') or 'ffprobe', '-v', 'error', '-count_frames',
                             '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames,avg_frame_rate',
                             '-of', 'json', str(path)], capture_output=True, timeout=120)
    if result.returncode:
        raise ValueError('Could not count AI candidate video frames')
    streams = json.loads(result.stdout)['streams']
    if not streams or streams[0].get('avg_frame_rate') not in ('24/1', '48/2'):
        raise ValueError('AI candidate must be a constant-rate 24 fps video')
    return int(streams[0]['nb_read_frames'])


def compose_candidate(source, generated, candidate, destination):
    """Normalize both media and omit the duplicated guided boundary image."""
    base_frames, extra = candidate['source_frames'], candidate['extension_frames']
    required = base_frames if candidate['operation'] == 'regenerate' else extra + 1
    actual_frames = video_frames(generated)
    if actual_frames < required:
        raise ValueError('The generated candidate is shorter than the requested window')
    sources = []
    if candidate['operation'] == 'regenerate':
        sources = [(generated, 0, base_frames)]
    elif candidate['operation'] == 'extend_after':
        sources = [(source, candidate['source_start'], base_frames), (generated, 1 / 24, extra)]
    else:
        sources = [(generated, (actual_frames - 1 - extra) / 24, extra),
                   (source, candidate['source_start'], base_frames)]
    args, filters = [], []
    width, height = candidate['width'], candidate['height']
    total = 0
    for i, (path, start, frames) in enumerate(sources):
        args += ['-ss', f'{start:.9f}', '-i', str(path)]
        filters.append(f'[{i}:v:0]fps=24,scale={width}:{height}:force_original_aspect_ratio=decrease,'
                       f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,trim=end_frame={frames},setpts=PTS-STARTPTS[v{i}]')
        audio = f'[{i}:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo' if media_info(path).get('has_audio') else 'anullsrc=r=48000:cl=stereo'
        filters.append(f'{audio},apad,atrim=duration={frames / 24:.9f},asetpts=PTS-STARTPTS[a{i}]')
        total += frames
    filters.append(''.join(f'[v{i}][a{i}]' for i in range(len(sources))) + f'concat=n={len(sources)}:v=1:a=1[v][a]')
    ffmpeg([*args, '-filter_complex', ';'.join(filters), '-map', '[v]', '-map', '[a]',
            '-frames:v', str(total), '-r', '24', '-fps_mode', 'cfr', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
            '-movflags', '+faststart', str(destination)])
    validate_video(destination)
    if video_frames(destination) != total:
        raise ValueError('AI candidate processing did not preserve the exact requested frame count')
    return total


async def generate_candidate(runner, job, candidate):
    client = None
    project = runner.projects() / job.state.project_id
    record = candidate_file(project, candidate['id'])
    folder = record.parent
    previous_output = job.state.output_url
    try:
        client = runner.client_factory()
        candidate['status'] = 'running'
        write_json(record, candidate)
        source = safe_media(project, candidate['source_file'])
        if await media_task(digest_file, source) != candidate['source_digest']:
            raise ValueError('Source media changed before candidate generation')
        template = load_templates(runner.settings.templates_dir, 'text')['shot']
        template = candidate_template(template, candidate, len(job.request.refs))
        values = {f'ref{i + 1}': runner.uploads[uid] for i, uid in enumerate(job.request.refs)}
        if candidate['operation'] != 'regenerate':
            boundary = folder / 'boundary.png'
            await media_task(boundary_frame, source, candidate, boundary)
            values['boundary'] = boundary
        handle = await runner._run(client, job, template, values, 'shots')
        outputs = handle.get_outputs('ai_save')
        if not outputs:
            raise ValueError('The H3 candidate returned no video output')
        raw = folder / 'generated.mp4'
        await outputs[0].to_file(raw)
        actual = await media_task(video_frames, raw)
        if actual != candidate['generation_frames']:
            raise ValueError(f'H3 returned {actual} frames; the candidate graph requested {candidate["generation_frames"]}')
        result = folder / 'preview.mp4'
        # A cancelled request must wait for this bounded CPU operation before
        # exposing a terminal state or allowing another project mutation.
        frames = await media_task(compose_candidate, source, raw, candidate, result)
        candidate.update(status='ready', duration=frames / 24, result_frames=frames,
                         result_digest=await media_task(digest_file, result))
        write_json(record, candidate)
        job.update(status='succeeded', stage='done', progress=1., output_url=previous_output)
    except asyncio.CancelledError:
        candidate.update(status='cancelled', error='Candidate generation cancelled; the active take is unchanged')
        write_json(record, candidate)
        job.update(status='cancelled', output_url=previous_output)
        raise
    except Exception as error:
        logger.exception('Experimental AI edit failed for %s', job.id)
        candidate.update(status='failed', error=str(error).strip() or type(error).__name__)
        write_json(record, candidate)
        job.update(status='failed', error=candidate['error'], output_url=previous_output)
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                logger.exception('Could not close the AI candidate SDK client for %s', job.id)


def accept_candidate(project, candidate_id):
    candidate = read_candidate(project, candidate_id)
    if candidate['status'] not in ('ready', 'accepted'):
        raise ValueError('Only a ready candidate can be accepted')
    result = candidate_file(project, candidate_id).parent / 'preview.mp4'
    if not result.is_file() or digest_file(result) != candidate['result_digest']:
        raise ValueError('The candidate preview is missing or changed')
    with edit_manifest(project.parent, project.name) as manifest:
        shot = next(s for s in manifest['shots'] if s['shot_id'] == candidate['shot_id'])
        label = f'ai-edit:{candidate_id}:{candidate["operation"]}'
        existing = next((r for r in shot['revisions'] if r.get('label') == label), None)
        if existing:
            if shot['active_revision_id'] != existing['revision_id']:
                raise ValueError('This candidate was already accepted; choose its saved take explicitly')
            rid = existing['revision_id']
        else:
            if source_stamp(shot) != candidate['source_stamp']:
                raise ValueError('The source take or shot bounds changed; generate a new candidate')
            source = safe_media(project, candidate['source_file'])
            if digest_file(source) != candidate['source_digest']:
                raise ValueError('The source file changed since candidate generation')
            number = 1 + max((int(r['revision_id'][5:]) for r in shot['revisions']
                              if re.fullmatch(r'take_[0-9]+', r['revision_id'])), default=0)
            rid = f'take_{number:03d}'
            rel = f'generated/ai_{candidate_id}.mp4'
            dest = project / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix('.partial')
            try:
                shutil.copy2(result, tmp)
                os.replace(tmp, dest)
            finally:
                tmp.unlink(missing_ok=True)
            shot['revisions'].append({
                'revision_id': rid, 'media_ref': rel, 'actual_duration_seconds': candidate['duration'],
                'status': 'generated', 'media_range': None, 'label': label, 'parent_revision_id': candidate['take'],
                'fingerprint': candidate['result_digest'], 'duration_policy': 'keep_generated',
                'has_audio': True, 'source_start_seconds': 0., 'generation_prompt': candidate['prompt']})
            shot['active_revision_id'] = rid
    candidate.update(status='accepted', revision_id=rid)
    write_json(candidate_file(project, candidate_id), candidate)
    return candidate
