import hashlib
import io

import pytest

from backend.artifact_contract import ArtifactRef, ProjectSnapshot, SnapshotAsset
from backend.artifact_store import ArtifactIntegrityError, ArtifactQuotaError, CHUNK_SIZE, LocalArtifactStore


def ref(data):
    return ArtifactRef(hashlib.sha256(data).hexdigest(), len(data))


def test_streaming_roundtrip_and_dedup(tmp_path):
    data = b'video' * CHUNK_SIZE
    store = LocalArtifactStore(tmp_path)
    class Bounded(io.BytesIO):
        def read(self, size=-1):
            assert size == CHUNK_SIZE
            return super().read(size)
    store.put(Bounded(data), ref(data))
    store.put(Bounded(data), ref(data))
    with store.open_verified(ref(data)) as result:
        assert result.read() == data
    assert len([p for p in tmp_path.iterdir() if len(p.name) == 64]) == 1


@pytest.mark.parametrize('data', [b'', b'small binary\x00\xff'])
def test_empty_and_binary(tmp_path, data):
    store = LocalArtifactStore(tmp_path)
    store.put(io.BytesIO(data), ref(data))
    with store.open_verified(ref(data)) as source:
        assert source.read() == data


@pytest.mark.parametrize('data', [b'short', b'incorrect', b'too long bytes'])
def test_invalid_transfer_never_published(tmp_path, data):
    store = LocalArtifactStore(tmp_path)
    with pytest.raises(ArtifactIntegrityError):
        store.put(io.BytesIO(data), ref(b'original!'))
    assert not list(tmp_path.glob('.incoming-*'))
    assert not (tmp_path / ref(b'original!').sha256).exists()


def test_interrupted_transfer_preserves_existing(tmp_path):
    store = LocalArtifactStore(tmp_path)
    expected = ref(b'original')
    store.put(io.BytesIO(b'original'), expected)
    class Interrupted:
        def read(self, size):
            raise OSError('connection lost')
    with pytest.raises(OSError):
        store.put(Interrupted(), expected)
    with store.open_verified(expected) as source:
        assert source.read() == b'original'
    assert not list(tmp_path.glob('.incoming-*'))


@pytest.mark.parametrize('limits', [{'max_artifact_bytes': 2}, {'max_cache_bytes': 2}])
def test_quota_before_read(tmp_path, limits):
    store = LocalArtifactStore(tmp_path, **limits)
    with pytest.raises(ArtifactQuotaError):
        store.put(None, ref(b'abc'))


def test_total_quota_and_duplicate_does_not_double_charge(tmp_path):
    store = LocalArtifactStore(tmp_path, max_cache_bytes=5)
    store.put(io.BytesIO(b'abc'), ref(b'abc'))
    store.put(io.BytesIO(b'abc'), ref(b'abc'))
    with pytest.raises(ArtifactQuotaError):
        store.put(io.BytesIO(b'def'), ref(b'def'))


@pytest.mark.parametrize('corrupted', [b'wrong', b'123456'])
def test_read_rejects_corrupted_cache(tmp_path, corrupted):
    store = LocalArtifactStore(tmp_path)
    expected = ref(b'valid')
    store.put(io.BytesIO(b'valid'), expected)
    (tmp_path / expected.sha256).write_bytes(corrupted)
    with pytest.raises(ArtifactIntegrityError):
        with store.open_verified(expected):
            pytest.fail('Corruption exposed to consumer')


def test_disk_failure_cleans_temporary(tmp_path, monkeypatch):
    store = LocalArtifactStore(tmp_path)
    def fail(*args):
        raise OSError('disk full')
    monkeypatch.setattr('backend.artifact_store.os.fsync', fail)
    with pytest.raises(OSError):
        store.put(io.BytesIO(b'abc'), ref(b'abc'))
    assert not list(tmp_path.glob('.incoming-*'))
    assert not (tmp_path / ref(b'abc').sha256).exists()


def test_directory_cannot_impersonate_artifact(tmp_path):
    store = LocalArtifactStore(tmp_path)
    expected = ref(b'abc')
    (tmp_path / expected.sha256).mkdir()
    with pytest.raises(ArtifactIntegrityError):
        store.put(io.BytesIO(b'abc'), expected)


def test_crashed_transfer_cleanup_never_deletes_verified_blobs(tmp_path):
    store = LocalArtifactStore(tmp_path)
    store.put(io.BytesIO(b'valid'), ref(b'valid'))
    (tmp_path/'.incoming-abandoned').write_bytes(b'partial')
    assert store.discard_incomplete() == 1
    with store.open_verified(ref(b'valid')) as source:
        assert source.read() == b'valid'


def test_gc_unknown_reference_coverage_is_never_permission_to_delete(tmp_path):
    store = LocalArtifactStore(tmp_path)
    store.put(io.BytesIO(b'unknown historical snapshot'), ref(b'unknown historical snapshot'))
    report = store.collect_garbage(dry_run=False)
    assert report['references_complete'] is False
    assert report['reclaimable_bytes'] == report['removed_bytes'] == 0
    assert report['unclassified_bytes'] == report['total_bytes']
    assert store.inventory()['artifact_count'] == 1


def test_gc_retains_historical_and_active_snapshots_and_shared_assets(tmp_path):
    store = LocalArtifactStore(tmp_path)
    data = (b'historical manifest', b'current manifest', b'shared take',
            b'active upload', b'garbage')
    for value in data:
        store.put(io.BytesIO(value), ref(value))
    snapshots = [
        ProjectSnapshot('p_12345678', i, ref(manifest),
                        (SnapshotAsset('takes/shared.mp4', ref(b'shared take')),))
        for i, manifest in enumerate(data[:2], 1)
    ]
    report = store.collect_garbage(snapshots, retained_refs=[ref(b'active upload')],
                                   references_complete=True)
    assert report['retained_count'] == 4
    assert report['reclaimable_bytes'] == len(b'garbage')
    assert report['removed_bytes'] == 0
    assert (tmp_path / ref(b'garbage').sha256).exists()
    report = store.collect_garbage(snapshots, retained_refs=[ref(b'active upload')],
                                   references_complete=True, dry_run=False)
    assert report['removed_count'] == 1
    assert report['removed_bytes'] == len(b'garbage')
    assert report['errors'] == []
    assert store.inventory(snapshots, retained_refs=[ref(b'active upload')])['unclassified_bytes'] == 0
    for value in data[:-1]:
        with store.open_verified(ref(value)) as stream:
            assert stream.read() == value


def test_gc_reports_only_successful_unlinks_as_freed(tmp_path, monkeypatch):
    store = LocalArtifactStore(tmp_path)
    for value in (b'locked', b'unlocked'):
        store.put(io.BytesIO(value), ref(value))
    original = type(tmp_path).unlink
    def unlink(path, *args, **kwargs):
        if path.name == ref(b'locked').sha256:
            raise PermissionError('File in use')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(type(tmp_path), 'unlink', unlink)
    report = store.collect_garbage(references_complete=True, dry_run=False)
    assert report['removed_bytes'] == len(b'unlocked')
    assert report['removed_count'] == len(report['errors']) == 1
    assert (tmp_path / ref(b'locked').sha256).exists()


def test_gc_validates_entire_inventory_before_deletion_and_leaves_scratch(tmp_path):
    store = LocalArtifactStore(tmp_path)
    store.put(io.BytesIO(b'valid'), ref(b'valid'))
    (tmp_path / ref(b'not a file').sha256).mkdir()
    (tmp_path / '.incoming-active').write_bytes(b'partial')
    with pytest.raises(ArtifactIntegrityError):
        store.collect_garbage(references_complete=True, dry_run=False)
    assert (tmp_path / ref(b'valid').sha256).is_file()
    assert (tmp_path / '.incoming-active').read_bytes() == b'partial'


@pytest.mark.parametrize('arguments', [
    {'retained_snapshots': [{}]}, {'retained_refs': ['not a ref']},
    {'references_complete': 'yes'}, {'dry_run': 'no'},
])
def test_gc_rejects_ambiguous_retention_inputs(tmp_path, arguments):
    with pytest.raises(TypeError):
        LocalArtifactStore(tmp_path).collect_garbage(**arguments)


def test_gc_waits_for_active_verified_reader(tmp_path):
    import threading
    store = LocalArtifactStore(tmp_path)
    store.put(io.BytesIO(b'reading'), ref(b'reading'))
    started = threading.Event()
    done = threading.Event()
    reports = []
    def collect():
        started.set()
        reports.append(store.collect_garbage(references_complete=True, dry_run=False))
        done.set()
    with store.open_verified(ref(b'reading')) as source:
        thread = threading.Thread(target=collect, daemon=True)
        thread.start()
        assert started.wait(2)
        assert not done.wait(.1)
        assert source.read() == b'reading'
    thread.join(3)
    assert done.is_set()
    assert reports[0]['removed_bytes'] == len(b'reading')
