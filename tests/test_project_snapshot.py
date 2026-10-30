import io
import json
import hashlib
from pathlib import Path

import pytest

from backend.artifact_contract import ProjectSnapshot, SnapshotAsset
from backend.artifact_store import ArtifactIntegrityError, LocalArtifactStore
from backend.project_snapshot import capture_project, materialize_snapshot, read_json, validate_snapshot
from test_manual_timeline import editorial_project, montage
from backend.manual_timeline import save_document, record_token


def test_full_snapshot_roundtrip_including_editor_and_music(editorial_project, tmp_path):
    project = editorial_project
    save_document(project, montage(project), record_token(None))
    store = LocalArtifactStore(tmp_path / 'cache')
    snapshot = capture_project(store, project)
    paths = {a.relative_path for a in snapshot.assets}
    assert {'editor/timeline.json', 'music/retained.wav', 'sources/source.mp4'} <= paths
    with materialize_snapshot(store, snapshot, tmp_path / 'worker') as restored:
        assert restored != project
        for relative in ['manifest.json', *paths]:
            assert (restored / relative).read_bytes() == (project / relative).read_bytes()
        (restored / 'generated/red.mp4').write_bytes(b'worker mutation')
    assert not restored.exists()
    with store.open_verified(next(a.artifact for a in snapshot.assets if a.relative_path == 'generated/red.mp4')) as source:
        assert source.read(4) != b'work'
    assert not (project / 'generated/red.mp4').read_bytes().startswith(b'worker')


def test_unrelated_private_files_not_captured(editorial_project, tmp_path):
    (editorial_project / 'private-secret.txt').write_text('private')
    snapshot = capture_project(LocalArtifactStore(tmp_path / 'cache'), editorial_project)
    assert 'private-secret.txt' not in {a.relative_path for a in snapshot.assets}


def test_persistent_audio_is_verified_and_transportable(editorial_project, tmp_path):
    content = b'persistent user-supplied audio'
    digest = hashlib.sha256(content).hexdigest()
    fingerprint = 'sha256:' + digest
    relative = f'sources/audio/{digest}.wav'
    path = editorial_project / relative
    path.parent.mkdir()
    path.write_bytes(content)
    record = {'version': 1, 'assets': {fingerprint: {
        'asset_id': fingerprint, 'sha256': fingerprint, 'media_ref': relative}}}
    (path.parent / 'index.json').write_text(json.dumps(record), encoding='utf-8')
    store = LocalArtifactStore(tmp_path / 'cache')
    snapshot = capture_project(store, editorial_project)
    with materialize_snapshot(store, snapshot, tmp_path / 'worker') as restored:
        assert (restored / relative).read_bytes() == content
    path.write_bytes(b'changed')
    with pytest.raises(ValueError, match='audio is missing or has changed'):
        capture_project(store, editorial_project)


def test_persistent_audio_index_cannot_capture_unrelated_paths(editorial_project, tmp_path):
    from backend.project_snapshot import audio_references
    digest = 'a' * 64
    fingerprint = 'sha256:' + digest
    with pytest.raises(ValueError, match='path differs'):
        audio_references({'version': 1, 'assets': {fingerprint: {
            'asset_id': fingerprint, 'sha256': fingerprint, 'media_ref': 'private-secret.txt'}}})


def test_missing_reference_rejected(editorial_project, tmp_path):
    store = LocalArtifactStore(tmp_path / 'cache')
    snapshot = capture_project(store, editorial_project)
    broken = ProjectSnapshot(snapshot.project_id, snapshot.revision, snapshot.manifest, snapshot.assets[1:])
    with pytest.raises(ValueError, match='missing referenced'):
        validate_snapshot(store, broken)


def test_revision_mismatch_rejected(editorial_project, tmp_path):
    store = LocalArtifactStore(tmp_path / 'cache')
    snapshot = capture_project(store, editorial_project)
    broken = ProjectSnapshot(snapshot.project_id, snapshot.revision + 1, snapshot.manifest, snapshot.assets)
    with pytest.raises(ValueError, match='identity/revision'):
        validate_snapshot(store, broken)


def test_failed_materialization_cleans_worker(editorial_project, tmp_path):
    store = LocalArtifactStore(tmp_path / 'cache')
    snapshot = capture_project(store, editorial_project)
    (store.root / snapshot.assets[0].artifact.sha256).write_bytes(b'corrupt')
    with pytest.raises(ArtifactIntegrityError):
        with materialize_snapshot(store, snapshot, tmp_path / 'worker'):
            pytest.fail('Invalid data materialized')
    assert not list((tmp_path / 'worker').glob('snapshot-*'))


@pytest.mark.parametrize('data', [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'])
def test_strict_json(data):
    with pytest.raises(ValueError):
        read_json(data)


def test_manifest_directory_collision_rejected():
    from backend.artifact_contract import ArtifactRef
    with pytest.raises(ValueError):
        SnapshotAsset('Manifest.json/child', ArtifactRef('a' * 64, 0))


def test_symlink_source_rejected(editorial_project, tmp_path):
    target = editorial_project / 'linked.bin'
    try:
        target.symlink_to(editorial_project / 'generated/red.mp4')
    except OSError:
        pytest.skip('OS account cannot create symlinks')
    with pytest.raises(ArtifactIntegrityError):
        capture_project(LocalArtifactStore(tmp_path / 'cache'), editorial_project, extra_paths=['linked.bin'])


def test_missing_cache_blob_rejected_before_publication(editorial_project, tmp_path):
    store = LocalArtifactStore(tmp_path/'cache')
    snapshot = capture_project(store, editorial_project)
    (store.root/snapshot.assets[0].artifact.sha256).unlink()
    with pytest.raises(FileNotFoundError):
        validate_snapshot(store,snapshot)
