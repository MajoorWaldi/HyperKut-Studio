"""Local, content-addressed cache. Not connected to the generation runner.

The cache directory must be private to the Studio OS account. File locks coordinate
cooperating processes; they do not defend against a hostile local filesystem owner.
"""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import stat
import tempfile

from filelock import FileLock

from .artifact_contract import ArtifactRef, ProjectSnapshot

CHUNK_SIZE = 64 * 1024


class ArtifactIntegrityError(ValueError):
    pass


class ArtifactQuotaError(ValueError):
    pass


def _regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise ArtifactIntegrityError('Artifact must be a regular file, without reparse points')
    return info


class LocalArtifactStore:
    def __init__(self, root, *, max_artifact_bytes=2 * 1024**3, max_cache_bytes=20 * 1024**3):
        for value in (max_artifact_bytes, max_cache_bytes):
            if type(value) is not int or value < 1:
                raise ValueError('Artifact limits must be positive integers')
        self.root = Path(root).absolute()
        # Reject existing symlink/junction ancestors before creating anything.
        for path in (self.root, *self.root.parents):
            if os.path.lexists(path):
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                    raise ArtifactIntegrityError('Cache root cannot contain reparse points')
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_artifact_bytes = max_artifact_bytes
        self.max_cache_bytes = max_cache_bytes
        self.lock = FileLock(str(self.root / '.cache.lock'))

    def _path(self, ref):
        if not isinstance(ref, ArtifactRef):
            raise TypeError('Expected ArtifactRef')
        return self.root / ref.sha256

    def _used_bytes(self):
        total = 0
        for path in self.root.iterdir():
            if len(path.name) == 64 and all(c in '0123456789abcdef' for c in path.name):
                total += _regular(path).st_size
        return total

    def _retained_digests(self, retained_snapshots, retained_refs):
        refs = list(retained_refs)
        for snapshot in retained_snapshots:
            if not isinstance(snapshot, ProjectSnapshot):
                raise TypeError('Expected retained ProjectSnapshot')
            refs.append(snapshot.manifest)
            refs.extend(asset.artifact for asset in snapshot.assets)
        if not all(isinstance(ref, ArtifactRef) for ref in refs):
            raise TypeError('Expected retained ArtifactRef')
        return {ref.sha256 for ref in refs}

    def _inventory_locked(self, retained, references_complete):
        artifacts = []
        for path in sorted(self.root.iterdir()):
            if len(path.name) != 64 or any(c not in '0123456789abcdef' for c in path.name):
                continue
            size = _regular(path).st_size
            state = ('retained' if path.name in retained else
                     'reclaimable' if references_complete else 'unclassified')
            artifacts.append({'sha256': path.name, 'size_bytes': size, 'state': state})
        result = {'references_complete': references_complete, 'artifacts': artifacts,
                  'artifact_count': len(artifacts),
                  'total_bytes': sum(row['size_bytes'] for row in artifacts)}
        for state in ('retained', 'reclaimable', 'unclassified'):
            rows = [row for row in artifacts if row['state'] == state]
            result[f'{state}_count'] = len(rows)
            result[f'{state}_bytes'] = sum(row['size_bytes'] for row in rows)
        return result

    def inventory(self, retained_snapshots=(), *, retained_refs=(), references_complete=False):
        """Inventory digest blobs without assuming missing references mean garbage.

        Include every retained historical snapshot and active operation's refs.
        Only a caller with authoritative, complete reference coverage may set
        references_complete=True. Scratch files are not included.
        """
        if type(references_complete) is not bool:
            raise TypeError('references_complete must be a boolean')
        retained = self._retained_digests(retained_snapshots, retained_refs)
        with self.lock:
            return self._inventory_locked(retained, references_complete)

    def collect_garbage(self, retained_snapshots=(), *, retained_refs=(),
                        references_complete=False, dry_run=True):
        """Collect only explicitly proven unreferenced blobs; default to preview.

        The caller must prevent reference creation/removal for the entire call,
        e.g. under its operation/project metadata lock. The cache lock protects
        cooperating readers and writers, not external reference metadata.
        Failed unlinks are reported and never counted as freed space.
        """
        if type(references_complete) is not bool or type(dry_run) is not bool:
            raise TypeError('GC flags must be booleans')
        retained = self._retained_digests(retained_snapshots, retained_refs)
        with self.lock:
            result = self._inventory_locked(retained, references_complete)
            result.update(dry_run=dry_run, removed_count=0, removed_bytes=0, errors=[])
            if dry_run or not references_complete:
                return result
            for row in result['artifacts']:
                if row['state'] != 'reclaimable':
                    continue
                path = self.root / row['sha256']
                try:
                    size = _regular(path).st_size
                    path.unlink()
                except OSError as exc:
                    result['errors'].append({'sha256': row['sha256'], 'error': str(exc)})
                else:
                    result['removed_count'] += 1
                    result['removed_bytes'] += size
            return result

    def put(self, stream, expected):
        """Read bounded chunks, verify all bytes, then atomically publish.

        Unknown-length transfers must obtain an expected descriptor first. Failures
        leave existing artifacts intact and remove this operation's temporary file.
        """
        target = self._path(expected)
        if expected.size_bytes > self.max_artifact_bytes:
            raise ArtifactQuotaError('Artifact exceeds per-file limit')
        with self.lock:
            existing_size = _regular(target).st_size if target.exists() or target.is_symlink() else 0
            if self._used_bytes() - existing_size + expected.size_bytes > self.max_cache_bytes:
                raise ArtifactQuotaError('Artifact cache quota exceeded')
            fd, temporary = tempfile.mkstemp(prefix='.incoming-', dir=self.root)
            try:
                digest = hashlib.sha256()
                size = 0
                with os.fdopen(fd, 'wb') as output:
                    while True:
                        chunk = stream.read(CHUNK_SIZE)
                        if not isinstance(chunk, bytes):
                            raise TypeError('Artifact stream must return bytes')
                        if not chunk:
                            break
                        size += len(chunk)
                        if len(chunk) > CHUNK_SIZE or size > expected.size_bytes:
                            raise ArtifactIntegrityError('Artifact stream exceeds declared size')
                        digest.update(chunk)
                        output.write(chunk)
                    if size != expected.size_bytes or digest.hexdigest() != expected.sha256:
                        raise ArtifactIntegrityError('Artifact size or SHA-256 mismatch')
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, target)
            finally:
                Path(temporary).unlink(missing_ok=True)
        return expected

    @contextmanager
    def open_verified(self, ref):
        """Verify and rewind the same read-only handle before exposing bytes."""
        path = self._path(ref)
        with self.lock:
            if _regular(path).st_size != ref.size_bytes:
                raise ArtifactIntegrityError('Cached artifact size mismatch')
            with path.open('rb') as source:
                digest = hashlib.sha256()
                while chunk := source.read(CHUNK_SIZE):
                    digest.update(chunk)
                if digest.hexdigest() != ref.sha256:
                    raise ArtifactIntegrityError('Cached artifact SHA-256 mismatch')
                source.seek(0)
                yield source


    def discard_incomplete(self):
        """Remove crashed-transfer scratch files under the exclusive writer lock.

        An active cooperating writer holds this same lock for its whole transfer.
        Published digest blobs and all project files are left untouched.
        """
        count = 0
        with self.lock:
            for path in self.root.glob('.incoming-*'):
                _regular(path)
                path.unlink()
                count += 1
        return count
