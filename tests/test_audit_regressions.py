import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.config import ROOT, Settings
from backend.jobs import Job, JobStore
from backend.models import EditStyle, JobRequest
from backend.runner import ComfyRunner
from backend.runner import MockRunner
from backend.server import create_app
from backend.templates import load_templates


def settings(tmp_path):
    return Settings('http://127.0.0.1:1', 'http://127.0.0.1:1', tmp_path/'out', tmp_path/'workspace', ROOT/'workflows', False)


def test_style_survives_later_edits_and_regeneration(tmp_path):
    runner = ComfyRunner(settings(tmp_path), {})
    job = Job(JobRequest(mode='text'))
    job.update(style=EditStyle(music_volume=0.25, text=False))
    values = runner._values(job)
    assert values['edit_music_volume'] == 0.25
    assert values['edit_text'] is False


def test_progress_resets_for_a_new_operation():
    job = Job(JobRequest(mode='text'))
    job.update(status='succeeded', progress=1)
    job.begin('shots')
    job.update(progress=0.2)
    assert job.state.progress == 0.2 and job.state.operation == 1


def test_corrupt_saved_job_does_not_hide_valid_jobs(tmp_path):
    store = JobStore(tmp_path)
    job = store.create(JobRequest(mode='text'))
    (tmp_path/'broken.json').write_text('{')
    recovered = JobStore(tmp_path)
    assert recovered.get(job.id)
    assert recovered.load_errors


def test_replacing_prompt_handles_a_detected_shot_without_a_plan(tmp_path):
    runner = ComfyRunner(settings(tmp_path), {})
    project = runner.projects()/'p_0123456789ab'
    project.mkdir(parents=True)
    (project/'manifest.json').write_text(json.dumps({'project_id':project.name,'project_revision':1,'shots':[{'shot_id':'SHOT_001','plan':None}]}))
    runner._set_prompt(project.name, 'SHOT_001', 'red shoes')
    assert json.loads((project/'manifest.json').read_text())['shots'][0]['plan']['prompt'] == 'red shoes'
    assert list((project/'manifests').glob('*.json'))


def test_remix_override_reaches_the_prompt_writer():
    template = load_templates(ROOT/'workflows', 'remix')['shot']
    selects = [i for i,n in template.prompt.items() if n['class_type']=='MajoorSelectShot']
    assert any(v == [selects[0],3] for n in template.prompt.values() for v in n['inputs'].values())


async def test_empty_save_outputs_fail_the_job(tmp_path):
    class Handle:
        id = "test-sdk-handle"
        def get_outputs(self, node): return []
    class Runner(ComfyRunner):
        async def _run(self,*args,**kwargs): return Handle()
    runner = Runner(settings(tmp_path), {})
    job = Job(JobRequest(mode='text'))
    with pytest.raises(Exception, match='video|output|SaveVideo'):
        await runner._edit(None, job, load_templates(ROOT/'workflows','text'), runner._values(job))
    assert job.state.status != 'succeeded'


async def test_unexpected_exception_ends_the_job(tmp_path):
    class Client:
        async def aclose(self): pass
    class Runner(ComfyRunner):
        async def _run(self,*args,**kwargs): raise ValueError('bad provider payload')
    runner = Runner(settings(tmp_path), {}, Client)
    job = Job(JobRequest(mode='text'))
    await runner.run(job)
    assert job.state.status == 'failed' and 'bad provider payload' in job.state.error


def test_music_requires_a_track_before_job_submission(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        response = client.post('/api/jobs',json={'mode':'music'})
        assert response.status_code == 422


def test_reference_limit_is_enforced_at_the_api_boundary():
    with pytest.raises(ValueError):
        JobRequest(mode='text',refs=['x']*6)


def test_partial_edit_style_defaults_do_not_claim_to_be_rendered():
    # The renderer receives only persisted successful overrides, never unset values.
    assert EditStyle(music_volume=.2).model_dump(exclude_none=True)=={'music_volume':.2}


def test_shared_legacy_project_cannot_be_deleted_or_changed(tmp_path):
    config=settings(tmp_path)
    project=config.output_dir/'MajoorVideoTools/p_12345678'
    project.mkdir(parents=True)
    (project/'manifest.json').write_text('{}')
    class Shared(MockRunner):
        async def run(self,job):job.update(status='succeeded',project_id='p_12345678')
    with TestClient(create_app(config,Shared())) as client:
        a=client.post('/api/jobs',json={'mode':'text'}).json()['id']
        b=client.post('/api/jobs',json={'mode':'text'}).json()['id']
        client.get(f'/api/jobs/{b}/events')
        for url,method,body in [(f'/api/jobs/{a}?project=true','DELETE',None),(f'/api/jobs/{a}/free','POST',None),(f'/api/jobs/{a}/re-edit','POST',{})]:
            assert client.request(method,url,json=body).status_code==409
        assert project.is_dir() and client.get(f'/api/jobs/{b}').status_code==200


def test_bad_render_does_not_replace_the_previous_video(tmp_path):
    from backend.media import validate_video
    path=tmp_path/'bad.mp4'
    path.write_bytes(b'not video')
    with pytest.raises(ValueError):validate_video(path)


def test_progress_listeners_keep_only_the_latest_state():
    import asyncio
    job=Job(JobRequest(mode='text'))
    q=asyncio.Queue(maxsize=1)
    job._listeners.append(q)
    for i in range(100):job.update(progress=i/100)
    assert q.qsize()==1 and q.get_nowait().progress==.99


async def test_interrupted_reedit_keeps_last_rendered_style_on_disk(tmp_path):
    import asyncio
    entered=asyncio.Event()
    class Client:
        async def aclose(self):pass
    class Paused(ComfyRunner):
        async def _run(self,*args,**kwargs):
            entered.set()
            await asyncio.Event().wait()
    store=JobStore(tmp_path/'state')
    job=store.create(JobRequest(mode='text'))
    job.update(status='succeeded',style=EditStyle(text=False))
    task=asyncio.create_task(Paused(settings(tmp_path),{},Client).re_edit(job,EditStyle(text=True)))
    try:
        await asyncio.wait_for(entered.wait(),3)
        recovered=JobStore(tmp_path/'state').get(job.id)
        assert recovered.state.status=='cancelled'
        assert recovered.state.style.text is False
    finally:
        task.cancel()
        await asyncio.gather(task,return_exceptions=True)


def test_project_deletion_reserves_job_until_files_are_gone(tmp_path,monkeypatch):
    import shutil,threading
    from concurrent.futures import ThreadPoolExecutor
    from backend.models import Shot
    config=settings(tmp_path)
    project=config.output_dir/'MajoorVideoTools/p_12345678'
    project.mkdir(parents=True)
    (project/'manifest.json').write_text('{}')
    entered,release=threading.Event(),threading.Event()
    original=shutil.rmtree
    def paused(path,*args,**kwargs):
        if Path(path)==project:
            entered.set()
            assert release.wait(5)
        return original(path,*args,**kwargs)
    monkeypatch.setattr(shutil,'rmtree',paused)
    class Ready(MockRunner):
        async def run(self,job):
            job.update(status='succeeded',project_id=project.name,shots=[Shot(id='SHOT_001',start=0,duration=2,done=True)])
    with TestClient(create_app(config,Ready())) as client,ThreadPoolExecutor() as executor:
        job=client.post('/api/jobs',json={'mode':'text'}).json()['id']
        client.get(f'/api/jobs/{job}/events')
        deletion=executor.submit(client.delete,f'/api/jobs/{job}?project=true')
        try:
            assert entered.wait(3)
            response=client.post(f'/api/jobs/{job}/re-edit',json={})
        finally:
            release.set()
        assert deletion.result().status_code==200
        assert response.status_code==409


def test_validated_upload_kind_survives_an_unusual_filename_and_restart(tmp_path):
    import io
    from PIL import Image
    data=io.BytesIO()
    Image.new('RGB',(16,16),'blue').save(data,format='PNG')
    config=settings(tmp_path)
    with TestClient(create_app(config,MockRunner(pace=0))) as client:
        uploaded=client.post('/api/uploads',files={'file':('reference.data',data.getvalue(),'image/png')})
        assert uploaded.status_code==200
        upload_id=uploaded.json()['id']
    with TestClient(create_app(config,MockRunner(pace=0))) as client:
        response=client.post('/api/jobs',json={'mode':'text','refs':[upload_id]})
        assert response.status_code==200,response.text
        inputs=client.get(f'/api/jobs/{response.json()["id"]}/inputs').json()
        assert inputs['refs'][0]['kind']=='image' and inputs['refs'][0]['name']=='reference.data'


def test_reedit_response_resets_progress_before_worker_runs(tmp_path):
    from backend.models import Shot
    class Ready(MockRunner):
        async def run(self,job):job.update(status='succeeded',progress=1,shots=[Shot(id='SHOT_001',start=0,duration=2,done=True)])
        async def re_edit(self,job,style):
            import asyncio
            await asyncio.Event().wait()
    with TestClient(create_app(settings(tmp_path),Ready())) as client:
        job=client.post('/api/jobs',json={'mode':'text'}).json()['id']
        client.get(f'/api/jobs/{job}/events')
        response=client.post(f'/api/jobs/{job}/re-edit',json={}).json()
        try:
            assert response['progress']==0 and response['operation']==1
        finally:
            client.post(f'/api/jobs/{job}/cancel')


def test_atomic_json_survives_a_temporary_windows_reader(tmp_path):
    import os,threading
    from backend.storage import write_json
    if os.name!='nt':pytest.skip('Windows file-sharing semantics')
    path=tmp_path/'state.json'
    write_json(path,{'value':'before'})
    reader=path.open('rb')
    timer=threading.Timer(.12,reader.close)
    timer.start()
    try:
        write_json(path,{'value':'after'})
    finally:
        timer.join()
        reader.close()
    assert json.loads(path.read_text())=={'value':'after'}
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('schemas, native_text', [({}, True), ({'MajoorHyperFrames': {}}, False)])
async def test_planned_text_is_kept_when_hyperframes_is_absent(tmp_path, monkeypatch, schemas, native_text):
    import httpx
    async def object_info(self, url, **kwargs):
        return httpx.Response(200, json=schemas, request=httpx.Request('GET', url))
    monkeypatch.setattr(httpx.AsyncClient, 'get', object_info)
    sent = {}
    class Handle:
        def get_outputs(self, node): return []
    class Runner(ComfyRunner):
        async def _run(self, client, job, template, values, *args, **kwargs):
            sent.update(values)
            return Handle()
    runner = Runner(settings(tmp_path), {})
    job = Job(JobRequest(mode='text', settings={'text': True, 'motion_design': True}))
    with pytest.raises(Exception, match='SaveVideo'):
        await runner._edit(None, job, load_templates(ROOT/'workflows', 'text'), runner._values(job))
    assert sent['edit_text'] is native_text


@pytest.mark.parametrize('backend, access', [('remote_artifacts', 'local'), ('shared_local', 'jury')])
def test_sfx_library_stays_inside_its_root_when_remote(tmp_path, backend, access):
    from dataclasses import replace
    root = tmp_path / 'sfx'
    (root / 'kit').mkdir(parents=True)
    runner = ComfyRunner(replace(settings(tmp_path), storage_backend=backend, access_mode=access, sfx_root=root.resolve()), {})
    assert runner._sfx_library('kit') == str((root / 'kit').resolve())
    assert runner._sfx_library('') == ''
    for outside in ('..', str(tmp_path), '../elsewhere'):
        with pytest.raises(ValueError, match='SFX_ROOT'):
            runner._sfx_library(outside)
    with pytest.raises(ValueError, match='SFX_ROOT'):
        ComfyRunner(replace(settings(tmp_path), storage_backend=backend, access_mode=access), {})._sfx_library('kit')


def test_sfx_library_is_free_on_a_local_studio(tmp_path):
    assert ComfyRunner(settings(tmp_path), {})._sfx_library('D:/my/cues') == 'D:/my/cues'


def test_stage_timings_add_up_each_stage(monkeypatch):
    now = iter([100.0, 103.0, 110.0])
    monkeypatch.setattr('backend.jobs.time.monotonic', lambda: next(now))
    job = Job(JobRequest(mode='text'))
    job.begin('analyze')
    job.begin('shots')
    job.update(status='succeeded', stage='done')
    assert job.state.timings == {'analyze': 3.0, 'shots': 7.0}
