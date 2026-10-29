import asyncio
import io
import json
import subprocess
import zipfile
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.config import ROOT, Settings
from backend.jobs import Job, JobStore
from backend.models import JobRequest, JobState, Shot
from backend.runner import ComfyRunner, MockRunner
from backend.server import create_app


def settings(tmp_path, mock=True):
    return Settings('http://127.0.0.1:1', 'http://127.0.0.1:1', tmp_path/'out', tmp_path/'workspace', ROOT/'workflows', mock)


def saved_job(config, rows):
    store = JobStore(config.workspace/'state')
    job = store.create(JobRequest(mode='text'))
    job.update(status='succeeded', project_id='p_abcdef12', shots=[Shot(id=row['shot_id'], start=i, duration=1, done=True, takes=99) for i, row in enumerate(rows)])
    project = config.output_dir/'MajoorVideoTools'/job.state.project_id
    project.mkdir(parents=True)
    (project/'manifest.json').write_text(json.dumps({'source':{'uri':'sources/source.mp4','fps_num':24,'fps_den':1}, 'shots':rows}))
    return job, project


def test_html_upload_is_rejected_and_legacy_files_are_download_only(tmp_path):
    config = settings(tmp_path, False)
    uploads = config.workspace/'uploads'; uploads.mkdir(parents=True)
    (uploads/'old.html').write_bytes(b'<script>inert audit fixture</script>')
    (config.workspace/'uploads.json').write_text(json.dumps({'old':{'kind':'image','name':'old.html'}}))
    client = TestClient(create_app(config, MockRunner()))
    image = io.BytesIO(); Image.new('RGB',(8,8)).save(image,format='JPEG')
    disguised = client.post('/api/uploads', files={'file':('image.html', image.getvalue() + b'<script>inert fixture</script>', 'image/jpeg')})
    assert disguised.status_code == 200
    safe = client.get(disguised.json()['url'])
    assert safe.headers['content-type'] == 'image/jpeg'
    assert safe.headers['x-content-type-options'] == 'nosniff'
    legacy = client.get('/api/uploads/old')
    assert legacy.headers['content-type'] == 'application/octet-stream'
    assert legacy.headers['content-disposition'] == 'attachment'
    assert legacy.headers['x-content-type-options'] == 'nosniff'
    good = client.post('/api/uploads', files={'file':('image.jpg', image.getvalue(), 'image/jpeg')})
    assert good.status_code == 200
    assert client.get(good.json()['url']).headers['content-type'] == 'image/jpeg'


def test_untrusted_host_and_cross_origin_mutations_are_rejected(tmp_path):
    client = TestClient(create_app(settings(tmp_path), MockRunner()))
    assert client.get('/api/jobs', headers={'host':'untrusted.example'}).status_code == 400
    assert client.post('/api/jobs', headers={'origin':'https://untrusted.example'}, json={'mode':'text'}).status_code == 403
    assert client.post('/api/jobs', headers={'origin':'http://testserver'}, json={'mode':'text'}).status_code == 200


@pytest.mark.parametrize('field,value', [('motion_layers','not-json'), ('motion_layers','[{"type":"unknown"}]'), ('motion_layers','[{"type":"vector","shape":"invented"}]'), ('motion_layers','[{"type":"text"}]'), ('motion_direction','{broken'), ('motion_direction','{"intensity":NaN}'), ('motion_cues','[{"text":"x","start":20,"end":22}]')])
def test_invalid_finishing_never_creates_a_job(tmp_path, field, value):
    client = TestClient(create_app(settings(tmp_path), MockRunner()))
    response = client.post('/api/jobs', json={'mode':'text','settings':{field:value}})
    assert response.status_code == 422
    assert client.get('/api/jobs').json() == []


async def test_failed_regeneration_restores_prompt_and_keeps_existing_takes(tmp_path):
    config = settings(tmp_path)
    row = {'shot_id':'A','active_revision_id':'take_001','plan':{'prompt':'original'},'revisions':[{'revision_id':'take_001','media_ref':'generated/a.mp4','media_range':None}]}
    job, project = saved_job(config, [row])
    job.state = job.state.model_copy(update={'shots':[job.state.shots[0].model_copy(update={'prompt':'original'})]})
    runner = ComfyRunner(config, {}, client_factory=lambda:SimpleNamespace(aclose=lambda:asyncio.sleep(0)))
    async def fail(*args, **kwargs): raise RuntimeError('injected generation failure')
    runner._run = fail
    await runner.regenerate(job, ['A'], {'A':'replacement'})
    assert job.state.status == 'failed'
    assert job.state.shots[0].prompt == 'original'
    assert job.state.shots[0].takes == 1
    assert json.loads((project/'manifest.json').read_text())['shots'][0]['plan']['prompt'] == 'original'


def test_export_contains_project_source_music_and_uploaded_references(tmp_path):
    config = settings(tmp_path)
    row = {'shot_id':'A','active_revision_id':'take_001','source_media_ref':'sources/source.mp4','revisions':[{'revision_id':'take_001','media_ref':'generated/a.mp4','media_range':None}]}
    job, project = saved_job(config, [row])
    for rel in ('sources/source.mp4','generated/a.mp4','music/retained.wav'):
        path = project/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(b'fixture')
    client = TestClient(create_app(config, MockRunner()))
    uploaded = client.post('/api/uploads', files={'file':('portrait.png', b'fake image', 'image/png')}).json()
    state_file = config.workspace/'state'/f'{job.id}.json'
    data = json.loads(state_file.read_text()); data['request']['refs'] = [uploaded['id']]; state_file.write_text(json.dumps(data))
    client = TestClient(create_app(config, MockRunner()))
    archive = client.get(f'/api/jobs/{job.id}/export')
    assert archive.status_code == 200
    with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
        assert {'sources/source.mp4','generated/a.mp4','music/retained.wav','request_files.json'} <= set(bundle.namelist())
        mapping = json.loads(bundle.read('request_files.json'))
        assert bundle.read(mapping[uploaded['id']]) == b'fake image'


def test_original_thumbnails_follow_the_shot_range_and_have_distinct_cache_keys(tmp_path):
    config = settings(tmp_path)
    rows = [{'shot_id':sid,'active_revision_id':'original','revisions':[{'revision_id':'original','media_ref':'sources/source.mp4','media_range':{'start_frame':i*24,'end_frame_exclusive':(i+1)*24}}]} for i,sid in enumerate(('A','B'))]
    job, project = saved_job(config, rows)
    source = project/'sources/source.mp4'; source.parent.mkdir()
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=red:s=64x64:r=24:d=1','-f','lavfi','-i','color=blue:s=64x64:r=24:d=1','-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0[v]','-map','[v]','-c:v','libx264','-pix_fmt','yuv420p',str(source)],check=True)
    client = TestClient(create_app(config, MockRunner()))
    a = client.get(f'/api/jobs/{job.id}/shots/A/thumb'); b = client.get(f'/api/jobs/{job.id}/shots/B/thumb')
    assert a.status_code == b.status_code == 200
    assert a.headers['cache-control'] == b.headers['cache-control'] == 'no-cache'
    assert a.content != b.content
    assert len(list((config.workspace/'thumbs').glob('*.jpg'))) == 2


def test_job_metadata_is_reconciled_from_manifest(tmp_path):
    config = settings(tmp_path)
    row = {'shot_id':'A','active_revision_id':'take_002','plan':{'prompt':'actual prompt'},'revisions':[{'revision_id':f'take_{i:03d}','media_ref':f'generated/{i}.mp4','media_range':None} for i in (1,2)]}
    job, _ = saved_job(config, [row])
    client = TestClient(create_app(config, MockRunner()))
    shot = client.get(f'/api/jobs/{job.id}').json()['shots'][0]
    assert (shot['takes'],shot['version'],shot['prompt']) == (2,2,'actual prompt')


async def test_recovery_cancels_only_the_persisted_sdk_job_and_clears_it(tmp_path):
    config = settings(tmp_path)
    store = JobStore(config.workspace/'state'); job = store.create(JobRequest(mode='text'))
    job.record_handle('own-sdk-id')
    calls = []
    async def cancel(): calls.append('cancelled')
    async def get(id): calls.append(id); return SimpleNamespace(cancel=cancel, wait=lambda **kwargs:asyncio.sleep(0))
    client = SimpleNamespace(jobs=SimpleNamespace(get=get), aclose=lambda:asyncio.sleep(0))
    await ComfyRunner(config, {}, client_factory=lambda:client).recover(job)
    assert calls == ['own-sdk-id','cancelled']
    assert JobStore(config.workspace/'state').get(job.id).pending_handle is None
