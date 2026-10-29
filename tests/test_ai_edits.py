import asyncio
import json
import shutil
import threading
import time
from types import SimpleNamespace

import pytest
from comfy_sdk import Progress
from fastapi.testclient import TestClient

from backend.ai_edits import (accept_candidate, boundary_frame, candidate_file, candidate_template,
                              compose_candidate, digest_file, ffmpeg, media_task, prepare_candidate,
                              read_candidate, video_frames)
from backend.config import ROOT, Settings
from backend.models import AICandidateRequest, Shot
from backend.runner import ComfyRunner
from backend.server import create_app
from backend.storage import write_json
from backend.templates import load_templates


def clip(path, color, frames=48, audio=True):
    args = ['-f', 'lavfi', '-i', f'color=c={color}:s=64x64:r=24']
    if audio:
        args += ['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-c:a', 'aac']
    ffmpeg([*args, '-frames:v', str(frames), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)])
    return path


@pytest.fixture
def project(tmp_path):
    folder = tmp_path / 'out' / 'MajoorVideoTools' / 'p_0123456789ab'
    (folder / 'generated').mkdir(parents=True)
    clip(folder / 'generated' / 'take.mp4', 'red')
    revision = dict(revision_id='take_001', media_ref='generated/take.mp4', media_range=None,
                    actual_duration_seconds=2., source_start_seconds=.25, duration_policy='inherit_target',
                    has_audio=True, status='generated', generation_prompt='original recorded prompt')
    manifest = {'project_id': folder.name, 'project_revision': 1, 'source': {'fps_num': 24, 'fps_den': 1},
                'shots': [dict(shot_id=f'SHOT_{i + 1:03d}', timeline_index=i, start_frame=i * 24,
                               end_frame_exclusive=(i + 1) * 24, target_duration_seconds=1.,
                               plan={'prompt': 'editable correction'}, active_revision_id='take_001',
                               revisions=[dict(revision)]) for i in range(2)]}
    write_json(folder / 'manifest.json', manifest)
    return folder, manifest


def request(operation='extend_after'):
    return AICandidateRequest(operation=operation, take='take_001', prompt='A new exact prompt', seconds=.5, seed=17)


@pytest.mark.parametrize('operation,guide', [('regenerate', None), ('extend_before', -1), ('extend_after', 0)])
@pytest.mark.parametrize('references', [0, 3, 5])
def test_isolated_graph_uses_one_h3_chain_and_never_mutates_a_project(operation, guide, references):
    template = load_templates(ROOT / 'workflows', 'text')['shot']
    before = json.dumps(template.prompt, sort_keys=True)
    row = dict(id='a' * 24, operation=operation, prompt='literal prompt', width=640, height=384,
               generation_frames=124, seed=17)
    isolated = candidate_template(template, row, references)
    classes = [n['class_type'] for n in isolated.prompt.values()]
    assert classes.count('SamplerCustomAdvanced') == classes.count('MiniMaxH3ReferenceToVideo') == 1
    assert classes.count('CreateVideo') == classes.count('SaveVideo') == 1
    assert not any(name.startswith('Majoor') for name in classes)
    assert 'MiniMaxH3FunControlNetApply' not in classes
    cond = next(n['inputs'] for n in isolated.prompt.values() if n['class_type'] == 'MiniMaxH3ReferenceToVideo')
    assert (cond['prompt'], cond['length']) == ('literal prompt', 124)
    assert len([k for k in cond if k.startswith('ref_') and '.' in k]) == references
    assert set(isolated.slots) == {*(f'ref{i + 1}' for i in range(references)), *(['boundary'] if guide is not None else [])}
    if guide is not None:
        assert isolated.prompt['ai_guide']['inputs']['frame_idx'] == guide
    for node in isolated.prompt.values():
        for value in node['inputs'].values():
            if isinstance(value, list):
                assert str(value[0]) in isolated.prompt
    assert json.dumps(template.prompt, sort_keys=True) == before


@pytest.mark.parametrize('operation,first,last,count', [
    ('regenerate', 'blue', 'blue', 24), ('extend_before', 'blue', 'red', 36), ('extend_after', 'red', 'blue', 36)])
@pytest.mark.parametrize('audio', [False, True])
def test_real_media_splice_has_exact_frames_and_order_and_preserves_source(project, tmp_path, operation, first, last, count, audio):
    import subprocess
    folder, manifest = project
    candidate = prepare_candidate(folder, manifest, 'SHOT_001', request(operation))
    source = folder / 'generated' / 'take.mp4'
    original = digest_file(source)
    generated = clip(tmp_path / 'generated.mp4', 'blue', audio=audio)
    output = tmp_path / 'candidate.mp4'
    assert compose_candidate(source, generated, candidate, output) == video_frames(output) == count
    for frame, color in [(0, first), (count - 1, last)]:
        decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(output), '-vf', f'select=eq(n\\,{frame})',
                                  '-frames:v', '1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'],
                                 capture_output=True, check=True).stdout
        rgb = [sum(decoded[channel::3]) / (len(decoded) // 3) for channel in range(3)]
        assert rgb[0 if color == 'red' else 2] > 200
    assert digest_file(source) == original
    assert json.loads((folder / 'manifest.json').read_text()) == manifest
    if operation != 'regenerate':
        anchor = tmp_path / 'boundary.png'
        boundary_frame(source, candidate, anchor)
        assert anchor.is_file()


def ready(project, tmp_path, operation='extend_after'):
    folder, manifest = project
    candidate = prepare_candidate(folder, manifest, 'SHOT_001', request(operation))
    record = candidate_file(folder, candidate['id'])
    write_json(record, candidate)
    generated = clip(tmp_path / 'generated.mp4', 'blue')
    output = record.parent / 'preview.mp4'
    frames = compose_candidate(folder / candidate['source_file'], generated, candidate, output)
    candidate.update(status='ready', duration=frames / 24, result_frames=frames, result_digest=digest_file(output))
    write_json(record, candidate)
    return candidate


@pytest.mark.parametrize('operation,anchor_color', [('extend_before', 'blue'), ('extend_after', 'yellow')])
def test_source_slip_and_boundary_frame_are_exact_and_the_duplicate_guide_is_removed(project, tmp_path, operation, anchor_color):
    import subprocess
    from PIL import Image
    folder, manifest = project
    source = folder / 'generated' / 'take.mp4'
    ffmpeg(['-f', 'lavfi', '-i', 'color=c=red:s=64x64:r=24',
            '-vf', "drawbox=c=black:t=fill:enable='lt(n,6)',drawbox=c=blue:t=fill:enable='eq(n,6)',"
                   "drawbox=c=yellow:t=fill:enable='eq(n,29)',drawbox=c=green:t=fill:enable='gte(n,30)'",
            '-frames:v', '48', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(source)])
    row = prepare_candidate(folder, manifest, 'SHOT_001', request(operation))
    anchor = tmp_path / 'boundary.png'
    boundary_frame(source, row, anchor)
    pixel = Image.open(anchor).getpixel((32, 32))
    assert pixel[2] > 200 if anchor_color == 'blue' else pixel[0] > 200 and pixel[1] > 200 and pixel[2] < 30
    generated = tmp_path / 'guide.mp4'
    ffmpeg(['-f', 'lavfi', '-i', 'color=c=blue:s=64x64:r=24',
            '-vf', "drawbox=c=cyan:t=fill:enable='eq(n,0)+eq(n,47)'", '-frames:v', '48',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(generated)])
    result = tmp_path / 'result.mp4'
    compose_candidate(source, generated, row, result)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(result), '-vf', 'scale=1:1',
                          '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'], capture_output=True, check=True).stdout
    pixels = [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]
    base = pixels[:24] if operation == 'extend_after' else pixels[12:]
    extension = pixels[24:] if operation == 'extend_after' else pixels[:12]
    assert len(base) == 24 and len(extension) == 12
    assert base[0][2] > 200 and base[-1][0] > 200 and base[-1][1] > 200
    assert all(p[2] > 200 and p[0] < 30 and p[1] < 30 for p in extension)


def test_accept_is_explicit_idempotent_non_destructive_and_reversible(project, tmp_path):
    folder, old = project
    row = ready(project, tmp_path)
    assert json.loads((folder / 'manifest.json').read_text()) == old
    accepted = accept_candidate(folder, row['id'])
    after = json.loads((folder / 'manifest.json').read_text())
    shot, other = after['shots']
    assert other == old['shots'][1]
    assert shot['revisions'][0] == old['shots'][0]['revisions'][0]
    assert shot['active_revision_id'] == accepted['revision_id'] == 'take_002'
    assert len(shot['revisions']) == 2
    assert shot['start_frame'] == 0 and shot['end_frame_exclusive'] == 24 and shot['target_duration_seconds'] == 1
    new = shot['revisions'][-1]
    assert (new['duration_policy'], new['actual_duration_seconds'], new['generation_prompt']) == ('keep_generated', 1.5, 'A new exact prompt')
    assert digest_file(folder / new['media_ref']) == row['result_digest']
    assert accept_candidate(folder, row['id'])['revision_id'] == 'take_002'
    assert len(json.loads((folder / 'manifest.json').read_text())['shots'][0]['revisions']) == 2


@pytest.mark.parametrize('change', ['take', 'slip', 'window', 'kind', 'media', 'preview'])
def test_stale_candidate_is_rejected_without_changing_the_manifest(project, tmp_path, change):
    folder, manifest = project
    row = ready(project, tmp_path)
    if change == 'take':
        manifest['shots'][0]['active_revision_id'] = 'take_099'
    elif change == 'slip':
        manifest['shots'][0]['revisions'][0]['source_start_seconds'] = .5
    elif change == 'window':
        manifest['shots'][0]['target_duration_seconds'] = .75
    elif change == 'kind':
        manifest['shots'][0]['plan']['render_source'] = {'kind': 'graphic', 'text': 'new'}
    elif change == 'media':
        (folder / row['source_file']).write_bytes(b'changed')
    else:
        (candidate_file(folder, row['id']).parent / 'preview.mp4').write_bytes(b'changed')
    write_json(folder / 'manifest.json', manifest)
    before = (folder / 'manifest.json').read_bytes()
    with pytest.raises(ValueError, match='changed|bounds'):
        accept_candidate(folder, row['id'])
    assert (folder / 'manifest.json').read_bytes() == before
    assert read_candidate(folder, row['id'])['status'] == 'ready'


class CandidateClient:
    status = 'running'
    def __init__(self, path, fail=False, wait=False):
        self.path, self.fail, self.waiting = path, fail, wait
        self.closed = self.cancelled = False
        self.submitted = []
        self.workflows = SimpleNamespace(from_json=lambda prompt: SimpleNamespace(prompt=prompt, set_input=lambda *args: None))
        self.assets = SimpleNamespace(from_file=lambda path: str(path))

    async def submit(self, workflow):
        self.submitted.append(workflow)
        return self

    id = 'sdk-ai-test'

    async def events(self):
        yield Progress(value=.5, nodes_done=1, nodes_total=2, current_node='ai_sampler')
        if self.waiting:
            await asyncio.sleep(600)
        if self.fail:
            raise RuntimeError('Test GPU generation failure')

    async def result(self):
        return self

    async def refresh(self):
        pass

    async def cancel(self):
        self.cancelled = True
        self.status = 'canceled'

    async def wait(self, timeout=None):
        pass

    def get_outputs(self, node):
        assert node == 'ai_save'
        return [self]

    async def to_file(self, path):
        shutil.copy2(self.path, path)

    async def aclose(self):
        self.closed = True


def app_harness(project, tmp_path, *, enabled=True, fail=False, wait=False):
    folder, manifest = project
    generated = clip(tmp_path / 'sdk-output.mp4', 'blue', frames=124)
    client = CandidateClient(generated, fail=fail, wait=wait)
    settings = Settings('http://127.0.0.1:1', 'http://127.0.0.1:1', tmp_path / 'out',
                        tmp_path / 'workspace', ROOT / 'workflows', True, experimental_ai_edit=enabled)

    class HarnessRunner(ComfyRunner):
        async def run(self, job):
            job.update(project_id=folder.name, shots=[
                Shot(id=s['shot_id'], start=i, duration=1, prompt='old') for i, s in enumerate(manifest['shots'])])
            job.sync_shots(manifest)
            job.update(status='succeeded', stage='done', output_url='/old-export.mp4')

    runner = HarnessRunner(settings, {}, client_factory=lambda: client)
    return create_app(settings, runner), client, settings


def create_job(client):
    response = client.post('/api/jobs', json={'mode': 'text', 'settings': {'duration': 2}})
    assert response.status_code == 200, response.text
    jid = response.json()['id']
    client.get(f'/api/jobs/{jid}/events')
    return jid, f'/api/jobs/{jid}/shots/SHOT_001/ai-candidates'


def test_api_is_off_by_default_and_validates_operations(project, tmp_path):
    app, sdk, _ = app_harness(project, tmp_path, enabled=False)
    with TestClient(app) as client:
        jid, url = create_job(client)
        assert client.get(url).json() == {'enabled': False, 'candidates': []}
        assert client.post(url, json=request().model_dump()).status_code == 403
        assert client.post(f'/api/jobs/{jid}/ai-candidates/{"a" * 24}/accept').status_code == 403
        assert not sdk.submitted


def test_api_candidate_roundtrip_persistence_acceptance_and_timeline_projection(project, tmp_path):
    folder, manifest = project
    app, sdk, settings = app_harness(project, tmp_path)
    with TestClient(app) as client:
        jid, url = create_job(client)
        bad = request().model_dump() | {'operation': 'magic'}
        assert client.post(url, json=bad).status_code == 422
        assert client.post(url, json=request().model_dump() | {'prompt': '  '}).status_code == 422
        assert client.post(url, json=request().model_dump() | {'take': 'take_099'}).status_code == 422
        assert client.patch(f'/api/jobs/{jid}/shots/SHOT_001', json={'locked': True}).status_code == 200
        assert client.post(url, json=request().model_dump()).status_code == 409
        client.patch(f'/api/jobs/{jid}/shots/SHOT_001', json={'locked': False})
        response = client.post(url, json=request().model_dump())
        assert response.status_code == 200, response.text
        client.get(f'/api/jobs/{jid}/events')
        row = client.get(url).json()['candidates'][0]
        assert row['status'] == 'ready', row
        assert row['generated_seconds'] == 124 / 24
        assert json.loads((folder / 'manifest.json').read_text()) == manifest
        assert client.get(row['url']).content[:4] != b''
        assert client.get(f'/api/jobs/{jid}').json()['output_url'] == '/old-export.mp4'
        accepted = client.post(f'/api/jobs/{jid}/ai-candidates/{row["id"]}/accept')
        assert accepted.status_code == 200, accepted.text
        shots = accepted.json()['shots']
        assert [(s['start'], s['duration']) for s in shots] == [(0., 1.5), (1.5, 1.)]
        assert shots[0]['generation_prompt'] == request().prompt
        assert shots[0]['version'] == 2 and shots[0]['takes'] == 2
        assert accepted.json()['output_url'] == '/old-export.mp4'
        assert accepted.json()['warnings']
        assert sdk.closed and len(sdk.submitted) == 1
    with TestClient(create_app(settings, None)) as client:
        row = client.get(url).json()['candidates'][0]
        assert row['status'] == 'accepted'
        assert client.get(row['url']).status_code == 200


@pytest.mark.parametrize('cancel', [False, True])
def test_failure_and_cancellation_preserve_source_and_reconcile_only_own_handle(project, tmp_path, cancel):
    folder, manifest = project
    app, sdk, _ = app_harness(project, tmp_path, fail=not cancel, wait=cancel)
    with TestClient(app) as client:
        jid, url = create_job(client)
        assert client.post(url, json=request().model_dump()).status_code == 200
        if cancel:
            assert client.post(url, json=request().model_dump()).status_code == 409
            for _ in range(100):
                if client.get(f'/api/jobs/{jid}').json()['node'] == 'ai_sampler':
                    break
                time.sleep(.01)
            assert sdk.submitted
            assert client.post(f'/api/jobs/{jid}/cancel').status_code == 200
        client.get(f'/api/jobs/{jid}/events')
        state = client.get(f'/api/jobs/{jid}').json()
        row = client.get(url).json()['candidates'][0]
        assert row['status'] == ('cancelled' if cancel else 'failed')
        assert state['output_url'] == '/old-export.mp4' and row['url'] is None
        assert row['error']
        assert sdk.closed and sdk.cancelled and len(sdk.submitted) == 1
        assert json.loads((folder / 'manifest.json').read_text()) == manifest


def test_rejection_does_not_activate_a_take(project, tmp_path):
    folder, manifest = project
    app, _, _ = app_harness(project, tmp_path)
    with TestClient(app) as client:
        jid, url = create_job(client)
        client.post(url, json=request().model_dump())
        client.get(f'/api/jobs/{jid}/events')
        cid = client.get(url).json()['candidates'][0]['id']
        assert client.post(f'/api/jobs/{jid}/ai-candidates/{cid}/reject').status_code == 200
        assert client.post(f'/api/jobs/{jid}/ai-candidates/{cid}/accept').status_code == 409
        assert client.get(f'/api/jobs/{jid}/ai-candidates/{cid}/video').status_code == 404
        assert json.loads((folder / 'manifest.json').read_text()) == manifest


def test_short_model_output_fails_instead_of_pretending_generation_completed(project, tmp_path):
    folder, manifest = project
    app, sdk, _ = app_harness(project, tmp_path)
    sdk.path = clip(tmp_path / 'truncated.mp4', 'blue', frames=48)
    with TestClient(app) as client:
        jid, url = create_job(client)
        client.post(url, json=request().model_dump())
        client.get(f'/api/jobs/{jid}/events')
        row = client.get(url).json()['candidates'][0]
        assert row['status'] == 'failed' and '48 frames' in row['error']
        assert json.loads((folder / 'manifest.json').read_text()) == manifest


@pytest.mark.asyncio
async def test_cancelling_media_work_waits_for_the_thread_before_returning():
    began, finish = threading.Event(), threading.Event()
    def processing():
        began.set()
        assert finish.wait(3)
    task = asyncio.create_task(media_task(processing))
    await asyncio.to_thread(began.wait, 2)
    task.cancel()
    await asyncio.sleep(.02)
    assert not task.done()
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
