"""Fixture-only worker execution: no Comfy server, model imports or GPU."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import types

from filelock import FileLock, Timeout
import pytest

import backend
from backend.artifact_bundle import write_bundle
from backend.artifact_store import LocalArtifactStore
from backend.project_snapshot import capture_project
from backend.snapshot_schema import core


@pytest.fixture
def editorial_project(tmp_path):
    models, _, _ = core()
    project = tmp_path / 'projects' / 'p_0123456789ab'
    (project / 'sources').mkdir(parents=True)
    (project / 'sources' / 'source.mp4').write_bytes(b'fixture source bytes')
    source = models.Source(uri='sources/source.mp4', fingerprint='sha256:fixture',
                           width=64, height=64, fps_num=24, fps_den=1, timing_mode='CFR',
                           frame_count=48, duration_seconds=2., has_audio=False, template=False)
    revisions = (models.Revision('original', 'sources/source.mp4', 2., 'original',
                                media_range={'start_frame': 0, 'end_frame_exclusive': 48}),)
    shot = models.Shot('SHOT_001', 0, 0, 48, None, None, 2., 'sources/source.mp4',
                       'original', revisions, plan={'prompt': 'fixture'})
    manifest = models.ShotList(project.name, source, models.Detection('fixture', 0., 1, 'test'), (shot,))
    (project / 'manifest.json').write_text(json.dumps(manifest.to_dict()), encoding='utf-8')
    return project


@pytest.fixture
def worker(tmp_path, monkeypatch):
    inputs = tmp_path / 'input'
    outputs = tmp_path / 'output'
    inputs.mkdir()
    outputs.mkdir()
    paths = types.ModuleType('folder_paths')
    paths.get_input_directory = lambda: str(inputs)
    paths.get_output_directory = lambda: str(outputs)
    paths.get_annotated_filepath = lambda archive: str(inputs / archive)
    monkeypatch.setitem(sys.modules, 'folder_paths', paths)
    api = types.ModuleType('comfy_api.latest')
    class NodeOutput:
        def __init__(self, *values, ui=None):
            self.values = values
            self.ui = ui
    api.io = types.SimpleNamespace(ComfyNode=object, NodeOutput=NodeOutput)
    api.ComfyExtension = object
    monkeypatch.setitem(sys.modules, 'comfy_api', types.ModuleType('comfy_api'))
    monkeypatch.setitem(sys.modules, 'comfy_api.latest', api)
    name = '_retention_fixture_worker'
    for suffix in ('runtime', 'runtime.studio'):
        monkeypatch.setitem(sys.modules, f'{name}.{suffix}', types.ModuleType(f'{name}.{suffix}'))
    monkeypatch.setitem(sys.modules, f'{name}.runtime.studio.backend', backend)
    path = Path(__file__).resolve().parents[1] / 'experimental' / 'comfyui_snapshot_worker' / '__init__.py'
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    yield module, inputs, outputs
    for manager in module._CONTEXTS.values():
        manager.__exit__(None, None, None)


def upload(editorial_project, tmp_path, inputs):
    store = LocalArtifactStore(tmp_path / 'source-cache')
    snapshot = capture_project(store, editorial_project)
    stream = io.BytesIO()
    write_bundle(store, snapshot, stream)
    stream.seek(0)
    path = inputs / 'uploaded.snapshot.zip'
    path.write_bytes(stream.read())
    return snapshot, path


def transform(worker, snapshot, operation_id, archive='uploaded.snapshot.zip'):
    module, _, _ = worker
    return module.HyperKutSnapshotTransform.execute(
        archive, json.dumps({'kind': 'verify', 'project_id': snapshot.project_id,
                             'expected_revision': snapshot.revision}), operation_id)


def test_acknowledged_graph_release_cleans_workspace_upload_and_published_files(
        worker, editorial_project, tmp_path):
    module, inputs, outputs = worker
    _, source = upload(editorial_project, tmp_path, inputs)
    operation_id = 'a' * 32
    imported = module.HyperKutSnapshotImport.execute(source.name, operation_id)
    with pytest.raises(ValueError, match='active'):
        module.release_operation(operation_id, acknowledged=True)
    result = module.HyperKutSnapshotExport.execute(imported.values[0], operation_id)
    published = [outputs / 'hyperkut_artifacts' / row['filename'] for row in result.ui['files']]
    expected_bytes = source.stat().st_size + sum(path.stat().st_size for path in published)
    report = module.release_operation(operation_id, acknowledged=True)
    assert report == {'removed_bytes': expected_bytes, 'removed_files': 3}
    assert not source.exists()
    assert not any(path.exists() for path in published)
    assert not (outputs / '_hyperkut_workspaces' / operation_id).exists()
    assert module.release_operation(operation_id, acknowledged=True)['removed_bytes'] == 0


def test_legacy_release_preserves_outputs_until_ack_and_ack_survives_reload(
        worker, editorial_project, tmp_path):
    module, inputs, outputs = worker
    _, source = upload(editorial_project, tmp_path, inputs)
    operation_id = 'b' * 32
    imported = module.HyperKutSnapshotImport.execute(source.name, operation_id)
    exported = module.HyperKutSnapshotExport.execute(imported.values[0], operation_id)
    module.release_operation(operation_id)
    assert source.is_file()
    assert all((outputs / 'hyperkut_artifacts' / row['filename']).is_file()
               for row in exported.ui['files'])
    # There is no in-memory context after legacy release; durable records suffice.
    assert module._CONTEXTS == {}
    assert module.release_operation(operation_id, acknowledged=True)['removed_files'] == 3


def test_shared_upload_is_protected_by_active_and_unacknowledged_operations(
        worker, editorial_project, tmp_path):
    module, inputs, _ = worker
    snapshot, source = upload(editorial_project, tmp_path, inputs)
    transform(worker, snapshot, 'c' * 32)
    imported = module.HyperKutSnapshotImport.execute(source.name, 'd' * 32)
    assert module.release_operation('c' * 32, acknowledged=True)['removed_files'] == 2
    assert source.is_file()
    module.HyperKutSnapshotExport.execute(imported.values[0], 'd' * 32)
    transform(worker, snapshot, 'e' * 32)
    assert module.release_operation('d' * 32, acknowledged=True)['removed_files'] == 2
    assert source.is_file()
    assert module.release_operation('e' * 32, acknowledged=True)['removed_files'] == 3
    assert not source.exists()


def test_release_does_not_remove_replaced_upload_or_unowned_files(worker, editorial_project, tmp_path):
    module, inputs, outputs = worker
    snapshot, source = upload(editorial_project, tmp_path, inputs)
    result = transform(worker, snapshot, 'f' * 32)
    unrelated = outputs / 'hyperkut_artifacts' / ('0' * 32 + '.snapshot.zip')
    unrelated.write_bytes(b'not owned by this operation')
    source.write_bytes(b'a newly uploaded file with the same name')
    with pytest.raises(ValueError, match='changed'):
        module.release_operation('f' * 32, acknowledged=True)
    assert source.read_bytes() == b'a newly uploaded file with the same name'
    assert unrelated.is_file()
    assert all((outputs / 'hyperkut_artifacts' / row['filename']).is_file()
               for row in result.ui['files'])


def test_release_refuses_inflight_operation_lock(worker):
    module, _, outputs = worker
    module.HyperKutWorkspace.execute('1' * 32)
    lock = FileLock(str(outputs / '_hyperkut_retention' / '.retention.lock'))
    with lock, pytest.raises(Timeout):
        module.release_operation('1' * 32, acknowledged=True)


def test_release_rejects_path_escape_in_persisted_receipt(worker, editorial_project, tmp_path):
    module, inputs, outputs = worker
    snapshot, _ = upload(editorial_project, tmp_path, inputs)
    transform(worker, snapshot, '2' * 32)
    path = outputs / '_hyperkut_retention' / ('2' * 32 + '.json')
    receipt = json.loads(path.read_bytes())
    receipt['published'][0]['path'] = '..\\outside.snapshot.zip'
    path.write_text(json.dumps(receipt), encoding='utf-8')
    with pytest.raises(ValueError, match='ownership'):
        module.release_operation('2' * 32, acknowledged=True)


def test_transform_emits_generated_operation_id_for_explicit_ack(worker, editorial_project, tmp_path):
    module, inputs, _ = worker
    snapshot, source = upload(editorial_project, tmp_path, inputs)
    result = module.HyperKutSnapshotTransform.execute(source.name, json.dumps({
        'kind': 'verify', 'project_id': snapshot.project_id,
        'expected_revision': snapshot.revision}))
    operation_id = result.ui['text'][0]
    assert len(operation_id) == 32
    assert module.release_operation(operation_id, acknowledged=True)['removed_files'] == 3
