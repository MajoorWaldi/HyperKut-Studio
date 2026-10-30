import io
import hashlib
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from backend.artifact_contract import ArtifactRef, ProjectSnapshot, SnapshotAsset
from backend.artifact_store import ArtifactIntegrityError, ArtifactQuotaError, LocalArtifactStore
from backend.project_snapshot import capture_project, materialize_snapshot
from backend.artifact_bundle import write_bundle, read_bundle
from backend.snapshot_repository import SnapshotRepository, RevisionConflict
from test_manual_timeline import editorial_project


def packed(store, snapshot):
    stream = io.BytesIO()
    write_bundle(store, snapshot, stream)
    stream.seek(0)
    return stream


def test_bundle_cold_cache_worker(editorial_project, tmp_path):
    sender = LocalArtifactStore(tmp_path / 'sender')
    snapshot = capture_project(sender, editorial_project)
    receiver = LocalArtifactStore(tmp_path / 'receiver')
    assert read_bundle(receiver, packed(sender, snapshot)) == snapshot
    with materialize_snapshot(receiver, snapshot, tmp_path / 'worker') as project:
        assert (project / 'music/retained.wav').read_bytes() == (editorial_project / 'music/retained.wav').read_bytes()


@pytest.mark.parametrize('extra', ['../escape', 'sha256/not-a-digest', '/absolute', 'extra.bin'])
def test_bundle_rejects_unlisted_entries(editorial_project, tmp_path, extra):
    store = LocalArtifactStore(tmp_path / 'cache')
    snapshot = capture_project(store, editorial_project)
    stream = packed(store, snapshot)
    with zipfile.ZipFile(stream, 'a') as archive:
        archive.writestr(extra, b'bad')
    stream.seek(0)
    with pytest.raises(ArtifactIntegrityError):
        read_bundle(LocalArtifactStore(tmp_path / 'other'), stream)


def test_bundle_rejects_corrupt_blob(editorial_project, tmp_path):
    store = LocalArtifactStore(tmp_path / 'cache')
    snapshot = capture_project(store, editorial_project)
    source = packed(store, snapshot)
    bad = io.BytesIO()
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(bad, 'w') as archive:
        for index, item in enumerate(original.infolist()):
            data = original.read(item.filename)
            if index == 1:
                data = bytes(b ^ 1 for b in data)
            archive.writestr(item.filename, data)
    bad.seek(0)
    with pytest.raises(ArtifactIntegrityError):
        read_bundle(LocalArtifactStore(tmp_path / 'other'), bad)


def test_repository_conflict_and_retry(editorial_project, tmp_path):
    store = LocalArtifactStore(tmp_path / 'cache')
    snapshot = capture_project(store, editorial_project)
    repo = SnapshotRepository(tmp_path / 'repo', store)
    assert repo.commit(snapshot, expected_revision=0) == snapshot
    assert repo.commit(snapshot, expected_revision=0) == snapshot
    assert repo.head(snapshot.project_id) == snapshot
    # Different content with the same revision cannot silently replace the head.
    manifest = editorial_project / 'manifest.json'
    data = json.loads(manifest.read_bytes())
    data['shots'][0]['plan'] = {'prompt':'changed'}
    manifest.write_text(json.dumps(data))
    stale = capture_project(store, editorial_project)
    with pytest.raises(RevisionConflict):
        repo.commit(stale, expected_revision=0)
    assert repo.head(snapshot.project_id) == snapshot
    assert not list((tmp_path / 'repo' / snapshot.project_id / 'revisions').glob('2-*'))


def test_two_repositories_cannot_accept_competing_results(editorial_project, tmp_path):
    store = LocalArtifactStore(tmp_path / 'cache')
    first = capture_project(store, editorial_project)
    repo = SnapshotRepository(tmp_path / 'repo', store)
    repo.commit(first, expected_revision=0)
    manifest = editorial_project / 'manifest.json'
    snapshots = []
    for prompt in ('A', 'B'):
        data = json.loads(manifest.read_bytes())
        data['project_revision'] = 2
        data['shots'][0]['plan'] = {'prompt':prompt}
        manifest.write_text(json.dumps(data))
        snapshots.append(capture_project(store, editorial_project))
    def accept(snapshot):
        try:
            SnapshotRepository(tmp_path / 'repo', store).commit(snapshot, expected_revision=1)
            return 'accepted'
        except RevisionConflict:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(accept, snapshots)) == ['accepted','conflict']
    assert repo.head(first.project_id) in snapshots


def test_zip_directory_limit_checked_before_index_allocation(tmp_path):
    import struct
    from backend.artifact_store import ArtifactQuotaError
    footer = struct.pack('<4s4H2LH',b'PK\x05\x06',0,0,5000,5000,0,0,0)
    with pytest.raises(ArtifactQuotaError):
        read_bundle(LocalArtifactStore(tmp_path/'cache'),io.BytesIO(footer))


def test_bundle_preflights_per_asset_limit_before_writing(tmp_path):
    store = LocalArtifactStore(tmp_path / "cache")
    snapshot = ProjectSnapshot(
        "p_0123456789ab", 1,
        ArtifactRef(hashlib.sha256(b"manifest").hexdigest(), len(b"manifest")),
    )
    oversized = SnapshotAsset(
        "video/too-large.mp4",
        ArtifactRef(hashlib.sha256(b"oversized").hexdigest(), store.max_artifact_bytes + 1),
    )
    snapshot = replace(snapshot, assets=(*snapshot.assets, oversized))
    target = io.BytesIO()
    with pytest.raises(ArtifactQuotaError, match="video/too-large.mp4.*per-asset limit"):
        write_bundle(store, snapshot, target)
    assert target.getvalue() == b""


def test_bundle_preflights_total_cache_quota(tmp_path):
    store = LocalArtifactStore(tmp_path / "cache")
    maximum = store.max_artifact_bytes
    extra = tuple(
        SnapshotAsset(
            f"extra/blob-{index}.bin",
            ArtifactRef(hashlib.sha256(str(index).encode()).hexdigest(), maximum),
        )
        for index in range(store.max_cache_bytes // maximum + 1)
    )
    snapshot = ProjectSnapshot(
        "p_0123456789ab", 1,
        ArtifactRef(hashlib.sha256(b"manifest").hexdigest(), len(b"manifest")),
        extra,
    )
    with pytest.raises(ArtifactQuotaError, match="artifact cache quota"):
        write_bundle(store, snapshot, io.BytesIO())
