"""Bounded ZIP transport for validated, content-addressed snapshots.

ZIP entries are never extracted as filesystem paths. Only named SHA-256 blobs
from the descriptor are streamed into the verified cache.
"""
import json
import struct
import zipfile

from .artifact_contract import ProjectSnapshot
from .artifact_store import CHUNK_SIZE, ArtifactIntegrityError, ArtifactQuotaError
from .project_snapshot import MAX_JSON_BYTES, read_json, validate_snapshot

DESCRIPTOR = 'snapshot.json'


def transfer_limit(store):
    return store.max_cache_bytes + 2 * MAX_JSON_BYTES


def _refs(snapshot):
    refs = {}
    for ref in (snapshot.manifest, *(asset.artifact for asset in snapshot.assets)):
        if ref.sha256 in refs and refs[ref.sha256].size_bytes != ref.size_bytes:
            raise ArtifactIntegrityError('Same digest has conflicting sizes')
        refs[ref.sha256] = ref
    return refs


def validate_snapshot_limits(store, snapshot):
    if snapshot.manifest.size_bytes > MAX_JSON_BYTES:
        raise ArtifactQuotaError(
            f'Snapshot manifest is {snapshot.manifest.size_bytes:,} bytes; metadata limit is {MAX_JSON_BYTES:,} bytes'
        )
    for asset in snapshot.assets:
        size = asset.artifact.size_bytes
        if size > store.max_artifact_bytes:
            raise ArtifactQuotaError(
                f'Snapshot asset {asset.relative_path!r} is {size:,} bytes; '
                f'per-asset limit is {store.max_artifact_bytes:,} bytes'
            )
    refs = _refs(snapshot)
    total = sum(ref.size_bytes for ref in refs.values())
    if total > store.max_cache_bytes:
        raise ArtifactQuotaError(
            f'Snapshot assets total {total:,} bytes; artifact cache quota is {store.max_cache_bytes:,} bytes'
        )
    return refs


def write_bundle(store, snapshot, target):
    """Write to a caller-owned temporary stream; caller publishes atomically."""
    refs = validate_snapshot_limits(store, snapshot)
    validate_snapshot(store, snapshot)
    start = target.tell()
    try:
        with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            encoded = json.dumps(snapshot.to_dict(), ensure_ascii=False, allow_nan=False).encode('utf-8')
            if len(encoded) > MAX_JSON_BYTES:
                raise ArtifactQuotaError('Snapshot descriptor exceeds the 16 MiB metadata limit')
            archive.writestr(DESCRIPTOR, encoded)
            for digest, ref in sorted(refs.items()):
                with store.open_verified(ref) as source, archive.open('sha256/' + digest, 'w', force_zip64=True) as output:
                    while chunk := source.read(CHUNK_SIZE):
                        output.write(chunk)
        size = target.tell() - start
        maximum = transfer_limit(store)
        if size > maximum:
            raise ArtifactQuotaError(
                f'Snapshot archive is {size:,} bytes; effective transfer limit is {maximum:,} bytes'
            )
    except Exception:
        target.seek(start)
        target.truncate()
        raise


def _bounded_directory(source, limit):
    # Inspect the fixed ZIP directory footer before ZipFile allocates its index.
    # Input must be a seekable binary stream owned by the caller.
    source.seek(0, 2)
    length = source.tell()
    maximum = limit + 2 * MAX_JSON_BYTES
    if length > maximum:
        raise ArtifactQuotaError(
            f'Snapshot archive is {length:,} bytes; effective transfer limit is {maximum:,} bytes'
        )
    if length < 22:
        raise ArtifactIntegrityError('Snapshot archive is truncated')
    source.seek(max(0, length - 65557))
    tail = source.read(65557)
    offset = tail.rfind(b'PK\x05\x06')
    if offset < 0 or offset + 22 > len(tail):
        raise ArtifactIntegrityError('Missing ZIP directory footer')
    end = struct.unpack('<4s4H2LH', tail[offset:offset + 22])
    if offset + 22 + end[-1] != len(tail) or end[1] or end[2]:
        raise ArtifactIntegrityError('Unsupported split/trailing ZIP data')
    entries, directory_bytes = end[4], end[5]
    if entries == 65535 or directory_bytes == 0xffffffff or end[6] == 0xffffffff:
        footer_at = length - len(tail) + offset
        if footer_at < 20:
            raise ArtifactIntegrityError('Missing ZIP64 locator')
        source.seek(footer_at - 20)
        locator = struct.unpack('<4sLQL', source.read(20))
        if locator[0] != b'PK\x06\x07' or locator[1] or locator[3] != 1:
            raise ArtifactIntegrityError('Invalid ZIP64 locator')
        source.seek(locator[2])
        record = source.read(56)
        if len(record) != 56:
            raise ArtifactIntegrityError('Truncated ZIP64 footer')
        footer = struct.unpack('<4sQ2H2L4Q', record)
        if footer[0] != b'PK\x06\x06' or footer[4] or footer[5]:
            raise ArtifactIntegrityError('Unsupported ZIP64 directory')
        entries, directory_bytes = footer[7], footer[8]
    if entries > 4098 or directory_bytes > MAX_JSON_BYTES:
        raise ArtifactQuotaError('ZIP directory exceeds metadata limit')
    source.seek(0)


def read_bundle(store, source):
    """Validate exact membership, quotas, sizes and hashes before returning a snapshot.

    On interruption, already verified cache blobs may remain for a later retry;
    no project revision is changed by importing a bundle.
    """
    _bounded_directory(source, transfer_limit(store) - 2 * MAX_JSON_BYTES)
    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)) or len(names) > 4098:
            raise ArtifactIntegrityError('Duplicate or excessive ZIP entries')
        if DESCRIPTOR not in names:
            raise ArtifactIntegrityError('Missing snapshot descriptor')
        descriptor = archive.getinfo(DESCRIPTOR)
        if descriptor.file_size > MAX_JSON_BYTES:
            raise ArtifactQuotaError('Snapshot descriptor too large')
        with archive.open(descriptor) as stream:
            snapshot = ProjectSnapshot.from_dict(read_json(stream.read(MAX_JSON_BYTES + 1)))
        refs = validate_snapshot_limits(store, snapshot)
        expected = {DESCRIPTOR, *('sha256/' + digest for digest in refs)}
        if set(names) != expected:
            raise ArtifactIntegrityError('ZIP entries differ from snapshot descriptor')
        for entry in entries:
            mode = entry.external_attr >> 16
            if entry.flag_bits & 1 or entry.is_dir() or mode & 0o170000 not in (0, 0o100000):
                raise ArtifactIntegrityError('Unsupported ZIP entry type')
            if entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise ArtifactIntegrityError('Unsupported ZIP compression')
        for digest, ref in refs.items():
            entry = archive.getinfo('sha256/' + digest)
            if entry.file_size != ref.size_bytes:
                raise ArtifactIntegrityError('ZIP size differs from descriptor')
            with archive.open(entry) as stream:
                store.put(stream, ref)
        validate_snapshot(store, snapshot)
        return snapshot
