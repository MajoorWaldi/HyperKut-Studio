import copy
import json
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.config import ROOT, Settings
from backend.jobs import Job
from backend.models import JobRequest, Shot
from backend.server import create_app
from backend.storage import write_json
from backend import manual_timeline as timeline
from test_ai_edits import clip


@pytest.fixture
def editorial_project(tmp_path):
    models, _, _ = timeline.core()
    project = tmp_path / 'out' / 'MajoorVideoTools' / 'p_0123456789ab'
    (project / 'generated').mkdir(parents=True)
    for color in ('red', 'blue'):
        clip(project / 'generated' / f'{color}.mp4', color, frames=72)
    (project / 'sources').mkdir()
    shutil.copy2(project / 'generated' / 'red.mp4', project / 'sources' / 'source.mp4')
    (project / 'music').mkdir()
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=660:sample_rate=8000:duration=5',
                    str(project / 'music' / 'retained.wav')], check=True)
    source = models.Source(uri='sources/source.mp4', fingerprint='sha256:fixture', width=64, height=64,
                           fps_num=24, fps_den=1, timing_mode='CFR', frame_count=48, duration_seconds=2.,
                           has_audio=True, template=True)
    shots = []
    for i, color in enumerate(('red', 'blue')):
        revisions = (
            models.Revision('original', 'sources/source.mp4', 1., 'original', media_range={'start_frame': i * 24}),
            models.Revision('take_001', f'generated/{color}.mp4', 3., 'generated', fingerprint=f'sha256:{color}'),
            models.Revision('take_002', f'generated/{color}.mp4', 3., 'generated', fingerprint=f'sha256:{color}'),
        )
        shots.append(models.Shot(f'SHOT_{i + 1:03d}', i, i * 24, (i + 1) * 24, None, None, 1.,
                                'sources/source.mp4', 'take_002', revisions, plan={'prompt': color, 'fx': {'speed': 1.2}}))
    sl = models.ShotList(project.name, source, models.Detection('fixture', 0., 1, 'test'), tuple(shots))
    write_json(project / 'manifest.json', sl.to_dict())
    return project


def montage(project):
    payload = timeline.editor_payload(project, 3600)
    document = copy.deepcopy(payload['document'])
    document['clips'].reverse()
    document['clips'][0].update(in_frame=24, out_frame=36, revision_id='take_001')
    document['clips'].append({**document['clips'][0], 'id': 'duplicate'})
    return document


def test_payload_reuses_the_node_frame_contract_and_real_music_waveform(editorial_project):
    project = editorial_project
    before = (project / 'manifest.json').read_bytes()
    payload = timeline.editor_payload(project, 3600)
    assert payload['initial'] == timeline.core()[1].initial_document(timeline.shot_list(json.loads(before)))
    assert len(payload['library']) == 2 and len(payload['library'][0]['takes']) == 2
    assert payload['library'][0]['takes'][0]['frames'] == 72
    assert payload['music']['duration'] == 5 and max(payload['music']['peaks']) == 1
    assert payload['music']['source_audio'] is False
    assert len(payload['music']['peaks']) == 1024
    assert payload['etag'] is None and not payload['enabled'] and not payload['stale']
    assert (project / 'manifest.json').read_bytes() == before


def test_save_is_separate_atomic_versioned_and_compiles_the_exact_occurrences(editorial_project):
    project = editorial_project
    before = (project / 'manifest.json').read_bytes()
    document = montage(project)
    saved = timeline.save_document(project, document, None)
    assert saved['enabled'] and saved['etag']
    with pytest.raises(ValueError, match='Another editor'):
        timeline.save_document(project, document, None)
    payload = timeline.editor_payload(project, 3600)
    assert payload['document'] == document
    compiled = timeline.core()[1].compile_edit(timeline.shot_list(json.loads(before)), document)
    assert [s.shot_id for s in compiled.shots] == ['EDIT_clip_2', 'EDIT_clip_1', 'EDIT_duplicate']
    assert [s.frame_count for s in compiled.shots] == [12, 24, 12]
    assert compiled.shots[0].active.source_start_seconds == 1.
    assert all(s.plan.get('fx') is None for s in compiled.shots)
    assert (project / 'manifest.json').read_bytes() == before
    disabled = timeline.save_document(project, document, saved['etag'], enabled=False)
    assert not disabled['enabled']
    assert timeline.editor_payload(project, 3600)['document'] == document


@pytest.mark.parametrize('bad', [
    lambda d: d['clips'][0].update(out_frame=9999),
    lambda d: d['clips'][0].update(in_frame=.5),
    lambda d: d.update(project_id='p_bad'),
    lambda d: d['clips'][0].update(revision_id='unknown'),
    lambda d: d['clips'].append(d['clips'][0]),
    lambda d: d.update(clips=[]),
])
def test_invalid_edits_never_overwrite_a_saved_montage(editorial_project, bad):
    document = montage(editorial_project)
    saved = timeline.save_document(editorial_project, document, None)
    invalid = copy.deepcopy(document)
    bad(invalid)
    with pytest.raises(ValueError):
        timeline.save_document(editorial_project, invalid, saved['etag'])
    assert timeline.read_record(editorial_project)['document'] == document


def test_rebase_preserves_every_cut_and_selected_take_and_refuses_changed_referenced_media(editorial_project):
    project = editorial_project
    document = montage(project)
    saved = timeline.save_document(project, document, None)
    manifest = json.loads((project / 'manifest.json').read_text())
    new = {**manifest['shots'][0]['revisions'][-1], 'revision_id': 'take_003'}
    manifest['shots'][0]['revisions'].append(new)
    manifest['shots'][0]['active_revision_id'] = 'take_003'
    write_json(project / 'manifest.json', manifest)
    assert timeline.editor_payload(project, 3600)['stale']
    with pytest.raises(ValueError, match='changed'):
        timeline.save_document(project, document, saved['etag'])
    updated = timeline.rebase_document(project, saved['etag'])
    assert updated['document']['clips'] == document['clips']
    assert not timeline.editor_payload(project, 3600)['stale']
    manifest['shots'][1]['revisions'][1]['source_start_seconds'] = .5
    write_json(project / 'manifest.json', manifest)
    with pytest.raises(ValueError, match='changed'):
        timeline.rebase_document(project, updated['etag'])
    # Disabling remains possible even when the montage is stale.
    assert not timeline.save_document(project, updated['document'], updated['etag'], False)['enabled']


def test_render_graph_uses_actual_edit_node_and_never_activates_or_saves_source_takes(editorial_project):
    document = montage(editorial_project)
    template, values = timeline.render_template(editorial_project, document, 'test')
    graph = template.fill({})
    assert graph['timeline_edit']['inputs']['edit_json'] == json.dumps(document)
    assert graph['timeline_assemble']['inputs']['shot_list'] == ['timeline_edit', 0]
    assert graph['timeline_assemble']['inputs']['music'] == ['timeline_edit', 1]
    assert not graph['timeline_assemble']['inputs']['effects']
    assert 'timeline_music' in values
    assert not any(n['class_type'] in ('MajoorSaveProjectInfo', 'MajoorApplyShotMetadata') for n in graph.values())


def test_dialogue_only_references_survive_save_rebase_and_cleanup(editorial_project):
    project = editorial_project
    document = montage(project)
    voice = {**document['clips'][1], 'id': 'voice_only', 'revision_id': 'take_001',
             'in_frame': 0, 'out_frame': 36, 'at_frame': 6, 'gain': .7}
    document['clips'] = [document['clips'][0]]
    document['dialogue'] = [voice]
    document['music_gain'] = .3
    saved = timeline.save_document(project, document, None)
    assert (voice['shot_id'], voice['revision_id']) in timeline.referenced_takes(project)
    assert timeline.editor_payload(project, 3600)['document'] == document
    template, _ = timeline.render_template(project, document, 'dialogue')
    assert template.prompt['timeline_assemble']['inputs']['music_volume'] == .3
    compiled = timeline.core()[1].compile_edit(timeline.shot_list(json.loads((project / 'manifest.json').read_text())), document)
    assert compiled.shots[0].plan['dialogue_track'][0]['gain'] == .7
    manifest = json.loads((project / 'manifest.json').read_text())
    manifest['shots'][0]['revisions'].append({**manifest['shots'][0]['revisions'][-1], 'revision_id': 'take_003'})
    write_json(project / 'manifest.json', manifest)
    updated = timeline.rebase_document(project, saved['etag'])
    assert updated['document']['dialogue'] == [voice]
    manifest['shots'][0]['revisions'][1]['source_start_seconds'] = .25
    write_json(project / 'manifest.json', manifest)
    with pytest.raises(ValueError, match='changed'):
        timeline.rebase_document(project, updated['etag'])


def test_take_audio_waveform_is_real_and_media_is_project_scoped(editorial_project):
    project = editorial_project
    source = project / 'generated' / 'red.mp4'
    audio = project / 'generated' / 'with_audio.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(source), '-f', 'lavfi',
                    '-i', 'sine=frequency=440:sample_rate=16000:duration=3',
                    '-c:v', 'copy', '-c:a', 'aac', '-shortest', str(audio)], check=True)
    audio.replace(source)
    payload = timeline.editor_payload(project, 3600)
    take = payload['library'][0]['takes'][0]
    assert take['audio']['file'] == take['file']
    assert len(take['audio']['peaks']) == 512 and max(take['audio']['peaks']) == 1
    assert 2.95 < take['audio']['duration'] < 3.05


def test_source_soundtrack_is_not_replayed_under_its_own_dialogue(editorial_project):
    project = editorial_project
    (project / 'music' / 'retained.wav').unlink()
    source = project / 'sources' / 'source.mp4'
    audio = project / 'sources' / 'with_audio.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(source), '-f', 'lavfi',
                    '-i', 'sine=frequency=440:sample_rate=16000:duration=3',
                    '-c:v', 'copy', '-c:a', 'aac', '-shortest', str(audio)], check=True)
    audio.replace(source)
    manifest = json.loads((project / 'manifest.json').read_text())
    manifest['source']['template'] = False
    write_json(project / 'manifest.json', manifest)
    payload = timeline.editor_payload(project, 3600)
    assert payload['music']['source_audio'] is True
    legacy, _ = timeline.render_template(project, payload['document'], 'legacy')
    assert 'timeline_music' in legacy.prompt
    document = {**payload['document'], 'dialogue': []}
    explicit, values = timeline.render_template(project, document, 'dialogue')
    assert 'timeline_music' not in explicit.prompt and not values
    assert timeline.music_file(project) == source.resolve()
    assert timeline.music_file(project, suppress_source_audio=True) is None


def app_for(project, tmp_path):
    settings = Settings('http://127.0.0.1:1', 'http://127.0.0.1:1', tmp_path / 'out', tmp_path / 'workspace',
                        ROOT / 'workflows', True)
    class Runner:
        async def run(self, job):
            manifest = json.loads((project / 'manifest.json').read_text())
            job.update(project_id=project.name, status='succeeded', stage='done', output_url='/previous.mp4',
                       shots=[Shot(id=s['shot_id'], start=i, duration=1., prompt='source') for i, s in enumerate(manifest['shots'])])
            job.sync_shots(manifest)
    return create_app(settings, Runner()), settings


def job_url(client):
    created = client.post('/api/jobs', json={'mode': 'text', 'settings': {'duration': 2}}).json()
    jid = created['id']
    client.get(f'/api/jobs/{jid}/events')
    return jid, f'/api/jobs/{jid}/manual-timeline'


def test_api_serves_shared_modules_safe_media_and_persists_without_changing_generation(editorial_project, tmp_path):
    app, settings = app_for(editorial_project, tmp_path)
    before = (editorial_project / 'manifest.json').read_bytes()
    with TestClient(app) as client:
        jid, url = job_url(client)
        payload = client.get(url).json()
        document = montage(editorial_project)
        response = client.put(url, json={'document': document, 'expected': None})
        assert response.status_code == 200, response.text
        token = response.json()['etag']
        assert client.put(url, json={'document': document, 'expected': None}).status_code == 409
        assert client.get(url).json()['document'] == document
        assert client.post(f'/api/jobs/{jid}/re-edit', json={'effects': True}).status_code == 409
        assert client.get(url + '/media', params={'file': payload['library'][0]['takes'][0]['file']}).status_code == 200
        assert client.get(url + '/media', params={'file': '@music'}).status_code == 200
        for path in ('manifest.json', '../secret', 'sources/source.mp4', r'C:\Windows\win.ini'):
            assert client.get(url + '/media', params={'file': path}).status_code == 404
        assert client.get('/api/timeline-editor/timeline_edit_panel.js').status_code == 200
        assert client.get('/api/timeline-editor/timeline_edit_logic.js').status_code == 200
        assert client.get('/api/timeline-editor/majoor_timeline_edit.js').status_code == 404
        state = client.get(f'/api/jobs/{jid}').json()
        assert state['output_url'] == '/previous.mp4'
        assert [s['id'] for s in state['shots']] == ['SHOT_001', 'SHOT_002']
        assert client.post(url + '/render', json={'expected': 'stale'}).status_code == 409
        assert client.post(url + '/render', json={'expected': token}).status_code == 409  # simulated runner cannot fake an export
    with TestClient(create_app(settings, None)) as client:
        assert client.get(url).json()['document'] == document
    assert (editorial_project / 'manifest.json').read_bytes() == before


def test_purge_protects_inactive_takes_referenced_by_manual_clips(editorial_project, tmp_path):
    # Distinct filenames ensure this verifies protection, not shared-file deduplication.
    project = editorial_project
    manifest = json.loads((project / 'manifest.json').read_text())
    for shot in manifest['shots']:
        relative = f'generated/{shot["shot_id"]}_old.mp4'
        shutil.copy2(project / shot['revisions'][1]['media_ref'], project / relative)
        shot['revisions'][1]['media_ref'] = relative
    write_json(project / 'manifest.json', manifest)
    document = montage(project)
    timeline.save_document(project, document, None)
    app, _ = app_for(project, tmp_path)
    with TestClient(app) as client:
        jid, _ = job_url(client)
        response = client.post(f'/api/jobs/{jid}/free')
        assert response.status_code == 200, response.text
    after = json.loads((project / 'manifest.json').read_text())
    assert any(r['revision_id'] == 'take_001' for r in after['shots'][1]['revisions'])
    assert (project / 'generated' / 'SHOT_002_old.mp4').is_file()
    assert not (project / 'generated' / 'SHOT_001_old.mp4').exists()


def test_waveform_read_does_not_block_job_or_take_readers(editorial_project, tmp_path, monkeypatch):
    entered, finish = threading.Event(), threading.Event()
    def waveform(*args, **kwargs):
        entered.set()
        assert finish.wait(5)
        return [0.] * 1024
    monkeypatch.setattr(timeline, 'audio_waveform', waveform)
    app, _ = app_for(editorial_project, tmp_path)
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as pool:
        jid, url = job_url(client)
        request = pool.submit(client.get, url)
        try:
            assert entered.wait(5)
            assert client.get(f'/api/jobs/{jid}').status_code == 200
            assert client.get(f'/api/jobs/{jid}/shots/SHOT_001/takes').status_code == 200
        finally:
            finish.set()
        assert request.result().status_code == 200


@pytest.mark.asyncio
async def test_manual_export_lifecycle_checks_duration_and_keeps_old_export_on_failure(editorial_project, tmp_path):
    project = editorial_project
    document = montage(project)
    saved = timeline.save_document(project, document, None)
    output = clip(tmp_path / 'out.mp4', 'blue', frames=48)
    class Output:
        async def to_file(self, path):
            shutil.copy2(output, path)
    class Runner:
        edits = 0
        def projects(self): return project.parent
        def video_path(self, job):
            path = tmp_path / 'existing.mp4'
            return path
        async def _run(self, client, job, template, values, stage):
            assert stage == 'edit' and template.prompt['timeline_edit']
            return SimpleNamespace(get_outputs=lambda node: [Output()] if node == 'timeline_save' else [])
    request = JobRequest(mode='text', settings={'duration': 2})
    job = Job(request)
    job.update(project_id=project.name, status='running', stage='edit', output_url='/old')
    runner = Runner()
    before = (project / 'manifest.json').read_bytes()
    await timeline.render_saved_timeline(runner, None, job)
    assert job.state.status == 'succeeded' and job.state.manual_export == {'duration': 2., 'clips': 3, 'etag': saved['etag']}
    previous = (tmp_path / 'existing.mp4').read_bytes()
    clip(output, 'red', frames=12)
    with pytest.raises(ValueError, match='duration'):
        await timeline.render_saved_timeline(runner, None, job)
    assert (tmp_path / 'existing.mp4').read_bytes() == previous
    assert (project / 'manifest.json').read_bytes() == before
