import json
from pathlib import Path
import pytest
from backend.remote_graph import compile_graph,RemoteMirror
from backend.config import Settings
from backend.artifact_store import LocalArtifactStore
from backend.project_snapshot import capture_project
from backend.storage import ProjectRevisionConflict
from test_manual_timeline import editorial_project

ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('path',list((ROOT/'workflows').rglob('*.api.json')),ids=lambda path:str(path.relative_to(ROOT/'workflows')))
def test_all_modes_compile_without_missing_links(path):
    graph=json.loads(path.read_text())
    compiled=compile_graph(graph,'a'*32,initial=path.name=='stage1.api.json')
    assert '__hk_export' in compiled
    for node in compiled.values():
        for value in node['inputs'].values():
            if isinstance(value,list) and len(value)==2 and isinstance(value[0],str) and isinstance(value[1],int):
                assert value[0] in compiled
    if path.name=='stage1.api.json':
        for node in compiled.values():
            if node['class_type']=='MajoorSaveProjectMusic':assert node['inputs']['shot_list']==compiled['__hk_export']['inputs']['shot_list']
    else:
        assert not any(n['class_type']=='MajoorLoadShotList' for n in compiled.values())
        for node in compiled.values():
            if node['class_type']=='MajoorLoadProjectMusic':assert node['inputs']['project']==['__hk_import',0]
    assert graph!=compiled


def test_mirror_validates_before_publish_and_preserves_stale_result(editorial_project,tmp_path):
    from types import SimpleNamespace
    settings=SimpleNamespace(workspace=tmp_path/'studio',output_dir=tmp_path/'mirror')
    mirror=RemoteMirror(settings)
    snapshot=capture_project(mirror.store,editorial_project)
    project=mirror.publish(snapshot,None,'job')
    assert (project/'manifest.json').read_bytes()==(editorial_project/'manifest.json').read_bytes() or json.loads((project/'manifest.json').read_bytes())==json.loads((editorial_project/'manifest.json').read_bytes())
    archive,expected=mirror.prepare(snapshot.project_id,'a'*32)
    import hashlib
    assert archive.is_file()
    assert expected==hashlib.sha256((project/'manifest.json').read_bytes()).hexdigest()
    changed=json.loads((project/'manifest.json').read_text())
    changed['project_revision']+=1
    (project/'manifest.json').write_text(json.dumps(changed))
    before=(project/'manifest.json').read_bytes()
    with pytest.raises(ProjectRevisionConflict):mirror.publish(snapshot,expected,'job','new-operation')
    assert (project/'manifest.json').read_bytes()==before
    assert list(mirror.scratch.glob('*.conflict.json'))


def test_remote_configuration_never_uses_worker_disk(monkeypatch,tmp_path):
    monkeypatch.setenv('HYPERKUT_STORAGE_BACKEND','remote_artifacts')
    monkeypatch.setenv('HYPERKUT_WORKSPACE',str(tmp_path))
    monkeypatch.setenv('HYPERKUT_OUTPUT_DIR','Z:/worker-only/path')
    config=Settings.from_env()
    assert config.output_dir==tmp_path/'remote-output'
    assert config.storage_backend=='remote_artifacts'


def test_remote_preflight_rejects_missing_weights_before_submission():
    from backend.remote_graph import validate_remote_graph
    schemas={kind:{'output':[]} for kind in ('HyperKutWorkspace','HyperKutSnapshotImport','HyperKutSnapshotExport','HyperKutWorkspaceRelease')}
    schemas['UNETLoader']={'input':{'required':{'unet_name':['COMBO',{'options':['available.safetensors']}]}}}
    with pytest.raises(ValueError,match='no generation submitted'):
        validate_remote_graph({'load':{'class_type':'UNETLoader','inputs':{'unet_name':'missing.safetensors'}}},schemas)
    validate_remote_graph({'load':{'class_type':'UNETLoader','inputs':{'unet_name':'available.safetensors'}}},schemas)


def test_pending_remote_context_survives_store_reload(tmp_path):
    from backend.jobs import JobStore
    from backend.models import JobRequest
    store=JobStore(tmp_path)
    job=store.create(JobRequest(mode='text'))
    job.pending_remote={'token':'a'*32,'project_id':'p_12345678','expected':'b'*64}
    job.record_handle('sdk-own')
    restored=JobStore(tmp_path).get(job.id)
    assert restored.pending_remote==job.pending_remote and restored.pending_handle=='sdk-own'


def test_cancel_releases_remote_workspace(monkeypatch,tmp_path):
    import asyncio
    from types import SimpleNamespace
    from backend.runner import ComfyRunner

    settings=SimpleNamespace(
        storage_backend='remote_artifacts',
        workspace=tmp_path,
        output_dir=tmp_path/'output',
        proxy_url='http://127.0.0.1:8189',
    )
    monkeypatch.setenv('COMFY_BASE_URL','http://127.0.0.1:8189')
    runner=ComfyRunner(settings,{})
    client=object()
    released=[]

    async def release_workspace(actual_client,token):
        released.append((actual_client,token))

    class Handle:
        status='running'

        async def cancel(self):
            self.status='canceled'

        async def wait(self,timeout):
            return None

    runner._release_workspace=release_workspace
    job=SimpleNamespace(
        pending_remote={'token':'c'*32},
        record_handle=lambda handle: setattr(job,'pending_handle',handle),
    )
    asyncio.run(runner._cancel_handle(client,job,Handle()))
    assert released==[(client,'c'*32)]
    assert job.pending_remote is None
    assert job.pending_handle is None


async def test_terminal_partial_outputs_do_not_block_future_recovery(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from backend.runner import ComfyRunner
    from backend.jobs import Job
    from backend.models import JobRequest
    from comfy_sdk import ComfyError
    settings=SimpleNamespace(storage_backend='remote_artifacts',workspace=tmp_path,output_dir=tmp_path/'output',proxy_url='http://127.0.0.1:8189')
    runner=ComfyRunner(settings,{})
    job=Job(JobRequest(mode='text'))
    job.pending_remote={'token':'d'*32}
    job.record_handle('partial-output')
    released=[]
    async def release(client,token): released.append(token)
    runner._release_workspace=release
    with pytest.raises(ComfyError,match='without the required snapshot outputs'):
        await runner._receive_remote(object(),job,SimpleNamespace(get_outputs=lambda _: []))
    assert released==['d'*32]
    assert job.pending_remote is None and job.pending_handle is None


def test_missing_background_model_is_rejected_before_submission():
    from backend.remote_graph import validate_remote_graph
    schemas={k:{'output':[]} for k in ('HyperKutWorkspace','HyperKutSnapshotImport','HyperKutSnapshotExport','HyperKutWorkspaceRelease')}
    schemas['LoadBackgroundRemovalModel']={'input':{'required':{'bg_removal_name':['COMBO',{'options':[]}]}}}
    with pytest.raises(ValueError,match='birefnet.safetensors'):
        validate_remote_graph({'load':{'class_type':'LoadBackgroundRemovalModel','inputs':{'bg_removal_name':'birefnet.safetensors'}}},schemas)
