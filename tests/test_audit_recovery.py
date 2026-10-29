import asyncio
from dataclasses import replace
import json
import shutil
import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.config import ROOT, Settings
from backend.jobs import Job, JobStore
from backend.models import JobRequest
from backend.project_snapshot import capture_project
from backend.remote_graph import RemoteMirror
from backend.runner import ComfyRunner
from backend.server import create_app
from backend.storage import write_json
from test_manual_timeline import editorial_project


def settings(tmp_path, *, remote=True):
    return Settings('http://127.0.0.1:1','http://127.0.0.1:1',tmp_path/('mirror' if remote else 'out'),
                    tmp_path/'studio',ROOT/'workflows',True,
                    storage_backend='remote_artifacts' if remote else 'shared_local')


def test_publication_replay_has_durable_receipt_and_does_not_restore_old_head(editorial_project,tmp_path):
    mirror=RemoteMirror(settings(tmp_path))
    snapshot=capture_project(mirror.store,editorial_project)
    project=mirror.publish(snapshot,None,'job','operation')
    receipts=list((mirror.scratch/'publications').glob('*.json'))
    assert len(receipts)==1
    manifest=json.loads((project/'manifest.json').read_text())
    manifest['project_revision']+=1
    write_json(project/'manifest.json',manifest)
    assert mirror.publish(snapshot,None,'job','operation')==project
    assert json.loads((project/'manifest.json').read_text())==manifest


def test_crash_after_manifest_before_receipt_reconciles_exact_result(editorial_project,tmp_path,monkeypatch):
    import backend.remote_graph as module
    mirror=RemoteMirror(settings(tmp_path))
    snapshot=capture_project(mirror.store,editorial_project)
    original=module.write_json
    def fail_receipt(path,value):
        if path.parent.name=='publications':
            raise OSError('synthetic receipt failure')
        original(path,value)
    monkeypatch.setattr(module,'write_json',fail_receipt)
    with pytest.raises(OSError,match='receipt'):
        mirror.publish(snapshot,None,'job','operation')
    monkeypatch.setattr(module,'write_json',original)
    mirror.publish(snapshot,None,'job','operation')
    assert len(list((mirror.scratch/'publications').glob('*.json')))==1


def test_manual_snapshot_requires_the_revision_validated_by_the_editor(editorial_project,tmp_path):
    from backend.storage import ProjectRevisionConflict
    mirror=RemoteMirror(settings(tmp_path))
    snapshot=capture_project(mirror.store,editorial_project)
    mirror.publish(snapshot,None,'job')
    with pytest.raises(ProjectRevisionConflict,match='before remote submission'):
        mirror.prepare(snapshot.project_id,'d'*32,expected_manifest='0'*64)
    assert not (mirror.scratch/f'{"d"*32}.input.zip').exists()


def test_failed_bundle_preparation_does_not_retain_an_unsubmitted_transfer(editorial_project,tmp_path,monkeypatch):
    import backend.remote_graph as module
    mirror=RemoteMirror(settings(tmp_path))
    snapshot=capture_project(mirror.store,editorial_project)
    mirror.publish(snapshot,None,'job')
    def fail(*args):raise ValueError('synthetic quota failure')
    monkeypatch.setattr(module,'write_bundle',fail)
    with pytest.raises(ValueError,match='quota'):
        mirror.prepare(snapshot.project_id,'e'*32)
    assert not list(mirror.scratch.glob('*.input.*'))


async def test_cancelled_publication_stays_locked_until_thread_stops(tmp_path,monkeypatch):
    import backend.artifact_transfer as transfer
    runner=ComfyRunner(settings(tmp_path),{})
    job=Job(JobRequest(mode='text'))
    job.pending_remote={'token':'a'*32,'project_id':'p_12345678','expected':None}
    job.record_handle('own')
    entered=threading.Event()
    finish=threading.Event()
    writes=[]
    released=[]
    def publish(*args):
        entered.set()
        assert finish.wait(5)
        writes.append('completed')
    async def download(*args):
        return SimpleNamespace(project_id='p_12345678')
    async def release(*args,**kwargs):
        released.append(True)
    monkeypatch.setattr(transfer,'download_snapshot_outputs',download)
    monkeypatch.setattr(runner.remote,'publish',publish)
    monkeypatch.setattr(runner,'_release_workspace',release)
    outputs=[SimpleNamespace(type='file',name='x.descriptor.json'),
             SimpleNamespace(type='file',name='x.snapshot.zip')]
    task=asyncio.create_task(runner._receive_remote(None,job,SimpleNamespace(get_outputs=lambda _:outputs)))
    try:
        assert await asyncio.to_thread(entered.wait,3)
        task.cancel()
        await asyncio.sleep(.02)
        task.cancel()
        await asyncio.sleep(.02)
        assert job.updating_project and not task.done()
        assert not released and not writes
    finally:
        finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert writes==['completed'] and not job.updating_project
    assert not released and job.pending_handle=='own' and job.pending_remote


async def test_initial_snapshot_recovery_restores_plan_and_takes_without_submit(editorial_project,tmp_path,monkeypatch):
    import backend.artifact_transfer as transfer
    config=settings(tmp_path)
    store=JobStore(config.workspace/'state')
    job=store.create(JobRequest(mode='text'))
    job.pending_remote={'token':'b'*32,'project_id':None,'expected':None}
    job.pending_result={'stage':'analyze'}
    job.record_handle('completed-analysis')
    runner=ComfyRunner(config,{})
    snapshot=capture_project(runner.remote.store,editorial_project)
    async def download(*args):return snapshot
    async def release(*args,**kwargs):pass
    async def nothing():pass
    outputs=[SimpleNamespace(type='file',name='x.descriptor.json'),
             SimpleNamespace(type='file',name='x.snapshot.zip')]
    handle=SimpleNamespace(status='succeeded',refresh=nothing,get_outputs=lambda _:outputs)
    async def get(handle_id):
        assert handle_id=='completed-analysis'
        return handle
    runner.client_factory=lambda:SimpleNamespace(jobs=SimpleNamespace(get=get),aclose=nothing)
    monkeypatch.setattr(transfer,'download_snapshot_outputs',download)
    monkeypatch.setattr(runner,'_release_workspace',release)
    restored=JobStore(config.workspace/'state').get(job.id)
    await runner.recover(restored)
    persisted=JobStore(config.workspace/'state').get(job.id)
    assert persisted.state.project_id==snapshot.project_id
    assert len(persisted.state.shots)==2
    assert all(shot.done and shot.takes==2 for shot in persisted.state.shots)
    assert persisted.state.status=='cancelled' and 'recovered' in persisted.state.error
    assert persisted.pending_remote is None and persisted.pending_handle is None
    persisted.pending_remote=dict(job.pending_remote)
    persisted.pending_result={'stage':'analyze'}
    persisted.record_handle('completed-analysis')
    await runner.recover(persisted)
    assert len(list((runner.remote.scratch/'publications').glob('*.json')))==1
    assert all(shot.done for shot in persisted.state.shots)


async def test_final_export_recovery_downloads_without_generating(editorial_project,tmp_path):
    config=settings(tmp_path,remote=False)
    store=JobStore(config.workspace/'state')
    job=store.create(JobRequest(mode='text'))
    job.update(project_id=editorial_project.name)
    job.pending_result={'stage':'edit','output_node':'saved','edit_version':4,
                        'style':{'text':False},'warnings':['retained']}
    job.record_handle('export')
    source=editorial_project/'generated'/'red.mp4'
    class Output:
        async def to_file(self,path):shutil.copy2(source,path)
    async def nothing():pass
    handle=SimpleNamespace(status='succeeded',refresh=nothing,get_outputs=lambda node:[Output()] if node=='saved' else [])
    async def get(handle_id):
        assert handle_id=='export'
        return handle
    runner=ComfyRunner(config,{},client_factory=lambda:SimpleNamespace(jobs=SimpleNamespace(get=get),aclose=nothing))
    restored=JobStore(config.workspace/'state').get(job.id)
    await runner.recover(restored)
    persisted=JobStore(config.workspace/'state').get(job.id)
    assert persisted.state.status=='succeeded' and persisted.edits==4
    assert persisted.state.output_url==f'/api/jobs/{job.id}/video?v=4'
    assert persisted.state.style.text is False and persisted.state.warnings==['retained']
    assert runner.video_path(persisted).read_bytes()==source.read_bytes()
    assert persisted.pending_handle is None and persisted.pending_result is None


def test_unreconciled_project_does_not_block_independent_job(tmp_path):
    config=settings(tmp_path,remote=False)
    store=JobStore(config.workspace/'state')
    old=store.create(JobRequest(mode='text'))
    old.record_handle('unreachable')
    class Runner(ComfyRunner):
        async def recover(self,job):raise ConnectionError('proxy unavailable')
        async def run(self,job):job.update(status='succeeded')
    with TestClient(create_app(config,Runner(config,{}))) as client:
        assert client.post('/api/jobs',json={'mode':'text'}).status_code==200
        response=client.post(f'/api/jobs/{old.id}/free')
        assert response.status_code==503 and 'other projects remain available' in response.text


def test_remote_candidate_flag_is_not_advertised_or_submitted(tmp_path):
    config=replace(settings(tmp_path),experimental_ai_edit=True)
    store=JobStore(config.workspace/'state')
    job=store.create(JobRequest(mode='text'))
    with TestClient(create_app(config,ComfyRunner(config,{}))) as client:
        url=f'/api/jobs/{job.id}/shots/SHOT_001/ai-candidates'
        assert client.get(url).json()=={'enabled':False,'candidates':[]}
        response=client.post(url,json={'operation':'regenerate','take':'take_001','prompt':'paper moon'})
        assert response.status_code==409 and 'remote_artifacts' in response.text
    assert not list(config.output_dir.rglob('candidate.json'))


def test_gc_preserves_history_and_releases_only_explicitly_purged_project(editorial_project,tmp_path):
    import io
    from backend.artifact_contract import ArtifactRef
    import hashlib
    mirror=RemoteMirror(settings(tmp_path))
    snapshot=capture_project(mirror.store,editorial_project)
    mirror.publish(snapshot,None,'job')
    data=b'unreferenced'
    ref=ArtifactRef(hashlib.sha256(data).hexdigest(),len(data))
    mirror.store.put(io.BytesIO(data),ref)
    report=mirror.cache_inventory(collect=True,dry_run=False)
    assert report['removed_bytes']==len(data)
    assert mirror.cache_inventory()['retained_bytes']>0
    mirror.forget_project(snapshot.project_id)
    report=mirror.cache_inventory(collect=True,dry_run=False)
    assert report['removed_bytes']>0 and mirror.cache_inventory()['total_bytes']==0


def test_legacy_cache_without_reference_coverage_is_not_deleted(tmp_path):
    import hashlib
    import io
    from backend.artifact_contract import ArtifactRef
    from backend.artifact_store import LocalArtifactStore
    config=settings(tmp_path)
    store=LocalArtifactStore(config.workspace/'artifacts')
    data=b'legacy historical data'
    store.put(io.BytesIO(data),ArtifactRef(hashlib.sha256(data).hexdigest(),len(data)))
    mirror=RemoteMirror(config)
    report=mirror.cache_inventory(collect=True,dry_run=False)
    assert report['removed_bytes']==0 and not report['references_complete']


def test_invalid_ui_projection_is_rejected_before_publication(editorial_project,tmp_path):
    mirror=RemoteMirror(settings(tmp_path))
    path=editorial_project/'manifest.json'
    manifest=json.loads(path.read_text())
    manifest['shots'][0]['plan']['prompt']={'invalid':'not a string'}
    write_json(path,manifest)
    snapshot=capture_project(mirror.store,editorial_project)
    with pytest.raises(ValueError):
        mirror.publish(snapshot,None,'job')
    assert not (mirror.root/snapshot.project_id/'manifest.json').exists()


def test_storage_api_separates_cache_metrics_and_collects_only_when_idle(tmp_path):
    import hashlib
    import io
    from backend.artifact_contract import ArtifactRef
    config=settings(tmp_path)
    runner=ComfyRunner(config,{})
    data=b'unreferenced bytes'
    runner.remote.store.put(io.BytesIO(data),ArtifactRef(hashlib.sha256(data).hexdigest(),len(data)))
    with TestClient(create_app(config,runner)) as client:
        inventory=client.get('/api/storage').json()
        assert inventory['worker_bytes'] is None
        assert inventory['cache']['reclaimable_bytes']==len(data)
        preview=client.post('/api/storage/cache/gc').json()
        assert preview['removed_bytes']==0
        result=client.post('/api/storage/cache/gc?dry_run=false').json()
        assert result['removed_bytes']==len(data)
        assert client.get('/api/storage').json()['cache']['total_bytes']==0


async def test_failed_worker_cleanup_is_persisted_and_acknowledgement_retried(tmp_path):
    config=settings(tmp_path)
    runner=ComfyRunner(config,{})
    async def fail(*args):raise ConnectionError('worker offline')
    client=SimpleNamespace(workflows=SimpleNamespace(from_json=lambda graph:graph),submit=fail)
    token='c'*32
    await runner._release_workspace(client,token,acknowledged=True)
    path=runner.remote.scratch/f'{token}.cleanup.json'
    assert json.loads(path.read_text())=={'token':token,'acknowledged':True}
    graphs=[]
    async def nothing(**kwargs):pass
    async def submit(graph):
        graphs.append(graph)
        return SimpleNamespace(wait=nothing,result=nothing)
    client.submit=submit
    await runner._release_workspace(client,token,acknowledged=True)
    assert graphs[0]['release']['inputs']['acknowledged'] is True
    assert not path.exists()
