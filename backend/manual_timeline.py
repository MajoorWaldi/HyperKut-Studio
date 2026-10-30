"""Studio adapter for the node pack's shared, frame-based editorial contract."""
import copy
import hashlib
import importlib
import importlib.util
import json
import sys
from functools import lru_cache
from pathlib import Path

from filelock import FileLock

from .config import ROOT
from .media import audio_waveform, media_info
from .storage import write_json
from .templates import Template

PACK = ROOT.parent
EDIT_FILE = 'editor/timeline.json'
EDITOR_MODULES = {'timeline_edit_panel.js', 'timeline_edit_logic.js'}


@lru_cache(maxsize=1)
def core():
    # Load only the pure core package, never the Comfy node pack entrypoint.
    directory = PACK / 'core'
    name = 'openkatana_videotools_core'
    if not (directory / 'timeline_edit.py').is_file():
        raise ValueError('Timeline editing requires the adjacent ComfyUI-Majoor-VideoTools core package')
    spec = importlib.util.spec_from_file_location(name, directory / '__init__.py',
                                                 submodule_search_locations=[str(directory)])
    if spec is None or spec.loader is None:
        raise ValueError('Cannot load the VideoTools timeline contract')
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return (importlib.import_module(f'{name}.models'),
            importlib.import_module(f'{name}.timeline_edit'),
            importlib.import_module(f'{name}.errors'))


def shot_list(manifest):
    models, _, errors = core()
    try:
        return models.ShotList.from_dict(manifest)
    except errors.MajoorError as error:
        raise ValueError(str(error)) from error


def checked_document(manifest, document):
    _, edits, errors = core()
    try:
        return edits.parse_document(shot_list(manifest), json.dumps(document))
    except errors.MajoorError as error:
        raise ValueError(str(error)) from error


def safe_file(project, relative):
    path = (project / relative).resolve()
    if not path.is_relative_to(project.resolve()) or not path.is_file():
        raise ValueError('Timeline media is missing or outside its project')
    return path


def read_record(project):
    path = project / EDIT_FILE
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def record_token(record):
    if record is None:
        return None
    return hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()


def music_file(project, suppress_source_audio=False):
    for relative in ('music/retained.wav', 'sources/music.wav'):
        if (project / relative).is_file():
            return safe_file(project, relative)
    manifest = json.loads((project / 'manifest.json').read_text(encoding='utf-8'))
    source = manifest['source']
    if not suppress_source_audio and not source.get('template') and source.get('has_audio'):
        return safe_file(project, source['uri'])
    return None


@lru_cache(maxsize=256)
def take_audio(path, mtime_ns, size, max_seconds):
    info = media_info(path)
    if info['duration'] > max_seconds:
        raise ValueError('Timeline take exceeds the configured preview duration limit')
    return ({'duration': info['duration'], 'peaks': audio_waveform(path, max_seconds, bins=512)}
            if info['has_audio'] else None)


def editor_payload(project, max_seconds):
    with FileLock(str(project / '.lock'), timeout=120):
        manifest = json.loads((project / 'manifest.json').read_text(encoding='utf-8'))
        record = read_record(project)
    sl = shot_list(manifest)
    _, edits, errors = core()
    try:
        initial = edits.initial_document(sl)
        library = []
        for shot in sorted(sl.shots, key=lambda row: row.timeline_index):
            takes = []
            for revision in shot.revisions:
                if sl.source.template and revision.media_range is not None:
                    continue
                offset, frames = edits.take_bounds(sl, shot, revision)
                path = safe_file(project, revision.media_ref)
                stat = path.stat()
                audio = take_audio(path, stat.st_mtime_ns, stat.st_size, max_seconds)
                takes.append({'id': revision.revision_id, 'file': revision.media_ref, 'offset': float(offset),
                              'frames': frames, 'prompt': revision.generation_prompt,
                              'audio': {'file': revision.media_ref, **audio,
                                        'frames': edits.dialogue_bounds(sl, shot, revision)[1]} if audio is not None else None})
            library.append({'id': shot.shot_id, 'takes': takes})
    except errors.MajoorError as error:
        raise ValueError(str(error)) from error
    document = record['document'] if record else initial
    stale = document['source_signature'] != initial['source_signature']
    if not stale:
        checked_document(manifest, document)
    music = music_file(project)
    waveform = None
    if music:
        info = media_info(music)
        if info['duration'] > max_seconds:
            raise ValueError('Timeline music exceeds the configured preview duration limit')
        waveform = {'file': '@music', 'duration': info['duration'],
                    'source_audio': music.relative_to(project).as_posix() not in ('music/retained.wav', 'sources/music.wav'),
                    'peaks': audio_waveform(music, max_seconds, bins=1024)}
    graph = None
    if not stale:
        module = importlib.import_module(core()[0].__package__ + '.editorial_graph')
        graph = module.preview_adapter(module.compile_project(sl, document))
    return {'library': library, 'initial': initial, 'document': document, 'music': waveform,
            'etag': record_token(record), 'enabled': bool(record and record['enabled']), 'stale': stale,
            'editorial_graph': graph}


def save_document(project, document, expected, enabled=True):
    with FileLock(str(project / '.lock'), timeout=120):
        previous = read_record(project)
        if record_token(previous) != expected:
            raise ValueError('Another editor changed this montage. Reload before saving; your local draft is retained.')
        manifest = json.loads((project / 'manifest.json').read_text(encoding='utf-8'))
        sources = previous['sources'] if not enabled and previous and previous['document'] == document else manifest
        checked_document(sources, document)
        record = {'version': 1, 'enabled': enabled, 'document': document, 'sources': sources}
        write_json(project / EDIT_FILE, record)
        return {'etag': record_token(record), 'enabled': enabled}


def rebase_document(project, expected):
    with FileLock(str(project / '.lock'), timeout=120):
        record = read_record(project)
        if not record or record_token(record) != expected:
            raise ValueError('The montage changed; reload before rebasing')
        current = json.loads((project / 'manifest.json').read_text(encoding='utf-8'))
        old, new = shot_list(record['sources']), shot_list(current)
        _, edits, errors = core()
        document = copy.deepcopy(record['document'])
        checked_document(record['sources'], document)
        try:
            if old.source != new.source:
                raise ValueError('The source video or timebase changed; automatic rebase is unsafe')
            for clip in [*document['clips'], *document.get('dialogue', [])]:
                before, after = old.get_shot(clip['shot_id']), new.get_shot(clip['shot_id'])
                a, b = before.revision(clip['revision_id']), after.revision(clip['revision_id'])
                if (a.media_ref, a.fingerprint, a.actual_duration_seconds, a.media_range, a.source_start_seconds) != (
                    b.media_ref, b.fingerprint, b.actual_duration_seconds, b.media_range, b.source_start_seconds
                ) or edits.take_bounds(old, before, a) != edits.take_bounds(new, after, b):
                    raise ValueError(f'{clip["id"]}: referenced media or source window changed; rebase refused')
                safe_file(project, b.media_ref)
            document['source_signature'] = edits.source_signature(new)
        except errors.MajoorError as error:
            raise ValueError(str(error)) from error
        checked_document(current, document)
        record.update(document=document, sources=current)
        write_json(project / EDIT_FILE, record)
        return {'etag': record_token(record), 'document': document}


def referenced_takes(project):
    record = read_record(project)
    return {(clip['shot_id'], clip['revision_id']) for clip in [*record['document']['clips'], *record['document'].get('dialogue', [])]} if record else set()


def render_template(project, document, job_id):
    graph = {
        'timeline_source': {'class_type': 'MajoorLoadShotList', 'inputs': {'project_id': project.name}},
        'timeline_edit': {'class_type': 'MajoorTimelineEdit',
                          'inputs': {'shot_list': ['timeline_source', 0], 'edit_json': json.dumps(document)}},
        'timeline_assemble': {'class_type': 'MajoorShotAssemble', 'inputs': {
            'shot_list': ['timeline_edit', 0], 'assembly_mode': 'original_order', 'manual_order': '',
            'missing_shot_policy': 'error', 'duration_policy': 'trim_or_error', 'fps_policy': 'source',
            'audio_policy': 'shot_audio', 'output_format': 'mp4', 'video_codec': 'h264',
            'output_name': f'manual_{job_id}', 'effects': False, 'sub_cuts': False, 'text': False,
            'auto_sfx': False, 'music_volume': 1., 'shot_volume': 1., 'music_fade': 0.}},
        'timeline_save': {'class_type': 'SaveVideo', 'inputs': {
            'video': ['timeline_assemble', 0], 'filename_prefix': f'MajoorVideoTools/{project.name}/exports/manual',
            'format': 'mp4', 'codec': 'h264'}}
    }
    music = music_file(project, suppress_source_audio='dialogue' in document)
    slots, values = {}, {'project_id':project.name}
    if music:
        graph['timeline_music'] = {'class_type': 'LoadAudio', 'inputs': {'audio': ''}}
        graph['timeline_edit']['inputs']['music'] = ['timeline_music', 0]
        graph['timeline_assemble']['inputs'].update(music=['timeline_edit', 1], shot_volume=0.)
        slots['timeline_music'] = (('timeline_music', 'audio'),)
        values['timeline_music'] = music
    graph['timeline_assemble']['inputs']['music_volume'] = document.get('music_gain', 1.)
    return Template(graph, slots), values


async def render_saved_timeline(runner, client, job):
    project = runner.projects() / job.state.project_id
    record = read_record(project)
    if not record or not record['enabled']:
        raise ValueError('Save and enable the manual montage before rendering')
    manifest_bytes=(project/'manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    document = checked_document(manifest, record['document'])
    template, values = render_template(project, document, job.id)
    values['expected_manifest']=hashlib.sha256(manifest_bytes).hexdigest()
    frames = sum(c['out_frame'] - c['in_frame'] for c in document['clips'])
    duration = frames * document['fps_den'] / document['fps_num']
    warnings=[w for w in job.state.warnings if not w.startswith('optional:')]
    warnings.append('Manual raw-take montage: automatic plan effects, overlays and sub-cuts are not reapplied. Music starts at zero. Explicit dialogue excerpts replace cut-linked take audio; without a dialogue track, take audio is muted when music is present.')
    context={'output_node':'timeline_save','manual_export':{'duration':duration,'clips':len(document['clips']),'etag':record_token(record)},
             'frame_seconds':document['fps_den']/document['fps_num'],'warnings':warnings,'edit_version':job.edits+1}
    handle = await runner._run(client, job, template, values, 'edit',result_context=context)
    await runner._finish_edit(job,handle,context)
