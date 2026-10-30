import io
import json

import pytest

from backend.artifact_store import LocalArtifactStore
from backend.artifact_bundle import write_bundle, read_bundle
from backend.project_snapshot import capture_project, materialize_snapshot
from backend.snapshot_worker import transform_snapshot
from test_manual_timeline import editorial_project


def prepared(project, tmp_path):
    store = LocalArtifactStore(tmp_path/'source')
    snapshot = capture_project(store, project)
    source = io.BytesIO()
    write_bundle(store, snapshot, source)
    source.seek(0)
    return snapshot, source


def test_worker_edits_cold_snapshot_without_touching_studio(editorial_project, tmp_path):
    before = (editorial_project/'manifest.json').read_bytes()
    snapshot, source = prepared(editorial_project, tmp_path)
    result, bundle, descriptor = transform_snapshot(source, tmp_path/'worker-output',
        {'kind':'set_prompt','project_id':snapshot.project_id,'expected_revision':snapshot.revision,
         'shot_id':'SHOT_001','prompt':'Light emerges from the paper.'})
    assert result.revision == snapshot.revision+1
    assert (editorial_project/'manifest.json').read_bytes() == before
    assert not list((tmp_path/'worker-output').glob('worker-*'))
    store = LocalArtifactStore(tmp_path/'receiver')
    with bundle.open('rb') as stream:
        assert read_bundle(store, stream) == result
    with materialize_snapshot(store, result, tmp_path/'review') as project:
        manifest = json.loads((project/'manifest.json').read_bytes())
        assert manifest['shots'][0]['plan']['prompt'] == 'Light emerges from the paper.'
        assert manifest['shots'][1]['plan']['prompt'] == 'blue'
    assert json.loads(descriptor.read_bytes())['snapshot'] == result.to_dict()


def test_worker_rejects_stale_operation(editorial_project, tmp_path):
    snapshot, source = prepared(editorial_project, tmp_path)
    with pytest.raises(ValueError, match='identity/revision'):
        transform_snapshot(source, tmp_path/'worker-output',
            {'kind':'verify','project_id':snapshot.project_id,'expected_revision':snapshot.revision+1})
    assert not list((tmp_path/'worker-output').glob('*.snapshot.zip'))


def test_worker_verify_preserves_revision(editorial_project, tmp_path):
    snapshot, source = prepared(editorial_project, tmp_path)
    result, _, _ = transform_snapshot(source, tmp_path/'worker-output',
        {'kind':'verify','project_id':snapshot.project_id,'expected_revision':snapshot.revision})
    assert result == snapshot
