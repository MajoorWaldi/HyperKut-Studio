"""Bounded SDK output transfer. Never persists download URLs or resubmits jobs."""
import hashlib
import os
from pathlib import Path
import tempfile

from .artifact_contract import ArtifactRef, ProjectSnapshot
from .artifact_store import ArtifactIntegrityError, ArtifactQuotaError
from .artifact_bundle import read_bundle, transfer_limit, validate_snapshot_limits
from .project_snapshot import MAX_JSON_BYTES, read_json


class BoundedSink:
    def __init__(self, stream, maximum):
        self.stream, self.maximum = stream, maximum
        self.size = 0
        self.digest = hashlib.sha256()

    def write(self, chunk):
        if self.size + len(chunk) > self.maximum:
            raise ArtifactQuotaError(f'SDK output exceeds its declared {self.maximum:,}-byte limit')
        count = self.stream.write(chunk)
        if count is None or not 0 < count <= len(chunk):
            raise OSError('SDK download write made no progress')
        self.digest.update(chunk[:count])
        self.size += count
        return count


async def download_snapshot_outputs(handle, node_id, store, scratch):
    """Download an explicit JSON descriptor and ZIP from one output node.

    A failed download can call this function again with the same handle; no GPU
    submission occurs here. Callers retain the SDK handle until commit succeeds.
    """
    outputs = handle.get_outputs(node_id)
    descriptors = [o for o in outputs if o.type == 'file' and o.name.endswith('.descriptor.json')]
    bundles = [o for o in outputs if o.type == 'file' and o.name.endswith('.snapshot.zip')]
    if len(descriptors) != 1 or len(bundles) != 1:
        raise ArtifactIntegrityError('Expected one descriptor and one snapshot bundle')
    scratch = Path(scratch)
    from .artifact_store import LocalArtifactStore
    LocalArtifactStore(scratch)
    with tempfile.TemporaryDirectory(prefix='transfer-', dir=scratch) as directory:
        metadata_path = Path(directory) / 'descriptor.json'
        with metadata_path.open('xb') as output:
            await descriptors[0].to_stream(BoundedSink(output, MAX_JSON_BYTES))
        metadata = read_json(metadata_path.read_bytes())
        if not isinstance(metadata, dict) or set(metadata) != {'artifact', 'snapshot'}:
            raise ArtifactIntegrityError('Invalid transfer descriptor')
        expected = ArtifactRef.from_dict(metadata['artifact'])
        snapshot = ProjectSnapshot.from_dict(metadata['snapshot'])
        validate_snapshot_limits(store, snapshot)
        maximum = transfer_limit(store)
        if expected.size_bytes > maximum:
            raise ArtifactQuotaError(
                f'Snapshot archive is {expected.size_bytes:,} bytes; effective transfer limit is {maximum:,} bytes'
            )
        bundle_path = Path(directory) / 'snapshot.zip'
        with bundle_path.open('xb') as output:
            sink = BoundedSink(output, expected.size_bytes)
            await bundles[0].to_stream(sink)
            if sink.size != expected.size_bytes or sink.digest.hexdigest() != expected.sha256:
                raise ArtifactIntegrityError('SDK snapshot archive failed integrity check')
            output.flush()
            os.fsync(output.fileno())
        with bundle_path.open('rb') as source:
            restored = read_bundle(store, source)
        if restored != snapshot:
            raise ArtifactIntegrityError('Archive and transfer descriptor disagree')
        return restored
