import asyncio
import json
import subprocess
import threading
import zipfile

import httpx
import pytest
from filelock import FileLock

from backend.media import validate_media
from backend.models import Shot
from backend.jobs import Job
from backend.models import EditStyle,JobRequest
from backend.runner import ComfyRunner,MockRunner
from backend.server import create_app
from test_audit_regressions import settings


def test_local_source_prompt_edit_is_refused_before_rendering(tmp_path):
    from fastapi.testclient import TestClient
    from backend.jobs import JobStore
    config=settings(tmp_path)
    job=Job(JobRequest(mode='text'))
    job.update(status='succeeded',shots=[Shot(id='TITLE',start=0,duration=2,prompt='old',render_source='graphic')])
    store=JobStore(config.workspace/'state');store.save(job)
    with TestClient(create_app(config,MockRunner())) as client:
        response=client.post(f'/api/jobs/{job.id}/regenerate',json={'shots':['TITLE'],'prompts':{'TITLE':'new'}})
        assert response.status_code==422
        assert 'render_source' in response.json()['detail']


def test_truncated_video_is_refused_even_when_its_metadata_is_readable(tmp_path):
    path=tmp_path/'truncated.mp4'
    subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','testsrc2=s=128x128:r=24:d=2','-c:v','libx264','-movflags','+faststart',str(path)],check=True)
    path.write_bytes(path.read_bytes()[:-700])
    with pytest.raises(ValueError,match='decod|corrupt'):
        validate_media(path,'video')


def test_decoder_accepts_valid_audio_first_video(tmp_path):
    path=tmp_path/'audio-first.mp4'
    subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','sine=duration=1','-f','lavfi','-i','color=s=64x64:r=24:d=1','-map','0:a','-map','1:v','-c:a','aac','-c:v','libx264',str(path)],check=True)
    validate_media(path,'video')


def test_decoder_accepts_valid_variable_frame_rate_video(tmp_path):
    path=tmp_path/'variable-rate.mp4'
    subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','testsrc2=s=64x64:r=24:d=1','-vf',"select='not(mod(n,2))+not(mod(n,3))'",'-fps_mode','vfr','-c:v','libx264',str(path)],check=True)
    validate_media(path,'video')


@pytest.mark.parametrize('operation',['free','choose'])
async def test_waiting_for_project_lock_does_not_block_other_requests(tmp_path,operation):
    config=settings(tmp_path)
    project=config.output_dir/'MajoorVideoTools/p_12345678'
    project.mkdir(parents=True)
    manifest={'project_id':project.name,'shots':[{'shot_id':'SHOT_001','active_revision_id':'take_001','revisions':[{'revision_id':'take_001','media_ref':'generated/a.mp4','media_range':None}]}]}
    (project/'manifest.json').write_text(json.dumps(manifest))
    class Ready(MockRunner):
        async def run(self,job):job.update(status='succeeded',project_id=project.name,shots=[Shot(id='SHOT_001',start=0,duration=2,done=True)])
    app=create_app(config,Ready())
    locked,health_done=threading.Event(),threading.Event()
    observed=[]
    def hold():
        with FileLock(str(project/'.lock')):
            locked.set()
            observed.append(health_done.wait(1))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver') as client:
        job=(await client.post('/api/jobs',json={'mode':'text'})).json()['id']
        await asyncio.sleep(0)
        holder=threading.Thread(target=hold)
        holder.start()
        assert await asyncio.to_thread(locked.wait,2)
        url=f'/api/jobs/{job}/free' if operation=='free' else f'/api/jobs/{job}/shots/SHOT_001/active'
        mutation=asyncio.create_task(client.post(url,json={} if operation=='free' else {'take':'take_001'}))
        try:
            await asyncio.sleep(.02)
            assert (await client.get('/api/jobs')).status_code==200
            health_done.set()
            assert (await mutation).status_code==200
        finally:
            health_done.set()
            await asyncio.to_thread(holder.join)
        assert observed==[True]


async def test_cancel_waits_for_video_validator_before_removing_its_file(tmp_path,monkeypatch):
    entered,release=threading.Event(),threading.Event()
    def validate(path):
        with path.open('rb'):
            entered.set()
            assert release.wait(3)
            assert path.is_file()
    monkeypatch.setattr('backend.runner.validate_video',validate)
    class Output:
        async def to_file(self,path):path.write_bytes(b'video being checked')
    class Handle:
        id = "test-sdk-handle"
        def get_outputs(self,node):return [Output()]
    class Client:
        async def aclose(self):pass
    class Runner(ComfyRunner):
        async def _run(self,*args,**kwargs):return Handle()
    runner=Runner(settings(tmp_path),{},Client)
    job=Job(JobRequest(mode='text'))
    previous=runner.video_path(job)
    previous.write_bytes(b'previous video')
    task=asyncio.create_task(runner.re_edit(job,EditStyle(text=False)))
    try:
        assert await asyncio.to_thread(entered.wait,2)
        task.cancel()
        await asyncio.sleep(.03)
        assert not task.done()
    finally:
        release.set()
        result=await asyncio.gather(task,return_exceptions=True)
    assert isinstance(result[0],asyncio.CancelledError)
    assert previous.read_bytes()==b'previous video'
    assert job.state.status=='cancelled'


async def test_cancel_waits_for_zip_writer_before_removing_archive(tmp_path,monkeypatch):
    config=settings(tmp_path)
    project=config.output_dir/'MajoorVideoTools/p_12345678'
    project.mkdir(parents=True)
    (project/'manifest.json').write_text('{}')
    entered,release=threading.Event(),threading.Event()
    original=zipfile.ZipFile
    class HeldZip(original):
        def write(self,filename,arcname=None,*args,**kwargs):
            if arcname=='manifest.json':
                entered.set()
                assert release.wait(3)
            return super().write(filename,arcname,*args,**kwargs)
    monkeypatch.setattr(zipfile,'ZipFile',HeldZip)
    class Ready(MockRunner):
        async def run(self,job):job.update(status='succeeded',project_id=project.name)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(config,Ready())),base_url='http://testserver') as client:
        job=(await client.post('/api/jobs',json={'mode':'text'})).json()['id']
        await asyncio.sleep(0)
        task=asyncio.create_task(client.get(f'/api/jobs/{job}/export'))
        try:
            assert await asyncio.to_thread(entered.wait,2)
            task.cancel()
            await asyncio.sleep(.03)
            # A disconnected HTTP caller may finish before its shielded cleanup.
            assert list(config.workspace.glob('*.zip')), 'Archive must exist while its writer is held'
        finally:
            release.set()
            result=await asyncio.gather(task,return_exceptions=True)
        assert isinstance(result[0],asyncio.CancelledError)
        for _ in range(100):
            if not list(config.workspace.glob('*.zip')):
                break
            await asyncio.sleep(.01)
        assert not list(config.workspace.glob('*.zip'))
