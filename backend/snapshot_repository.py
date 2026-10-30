"""Immutable snapshot revisions and compare-and-swap heads for remote results.

This repository is experimental and is not selected by the local runner.
"""
import hashlib
import json
from pathlib import Path

from filelock import FileLock

from .artifact_contract import ProjectSnapshot
from .artifact_store import LocalArtifactStore
from .project_snapshot import read_json, validate_snapshot, MAX_JSON_BYTES
from .storage import write_json


class RevisionConflict(ValueError):
    pass


class SnapshotRepository:
    def __init__(self, root, artifacts):
        self.root = Path(root).absolute()
        LocalArtifactStore(self.root)  # Validate private-root ancestors.
        self.artifacts = artifacts
        self.lock = FileLock(str(self.root / '.repository.lock'), timeout=120)

    def _project(self, project_id):
        # Delegate project-id validation to the existing descriptor contract.
        from .artifact_contract import ArtifactRef
        ProjectSnapshot(project_id, 1, ArtifactRef('0' * 64, 0))
        return self.root / project_id

    def head(self, project_id):
        with self.lock:
            path = self._project(project_id) / 'head.json'
            if not path.exists():
                return None
            if path.stat().st_size > MAX_JSON_BYTES:
                raise ValueError('Repository head exceeds metadata limit')
            return ProjectSnapshot.from_dict(read_json(path.read_bytes()))

    def commit(self, snapshot, *, expected_revision):
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError('Expected revision must be a non-negative integer')
        validate_snapshot(self.artifacts, snapshot)
        encoded = json.dumps(snapshot.to_dict(), sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')
        digest = hashlib.sha256(encoded).hexdigest()
        with self.lock:
            project = self._project(snapshot.project_id)
            # Preserve even stale results so rejection never discards a completed render.
            write_json(project / 'results' / f'{snapshot.revision}-{digest}.json', snapshot.to_dict())
            current = self.head(snapshot.project_id)
            # Retrying the exact result is idempotent, but never replaces another head.
            if current == snapshot and snapshot.revision == expected_revision + 1:
                return current
            if (current.revision if current else 0) != expected_revision:
                raise RevisionConflict('Project changed since this operation started; result retained for reconciliation')
            if snapshot.revision != expected_revision + 1:
                raise RevisionConflict('Result must advance the project revision by exactly one')
            project = self._project(snapshot.project_id)
            # Historical record first; a crash before head publication leaves current state intact.
            write_json(project / 'revisions' / f'{snapshot.revision}-{digest}.json', snapshot.to_dict())
            write_json(project / 'head.json', snapshot.to_dict())
            return snapshot


    def initialize(self, snapshot):
        """Explicitly seed authority from a validated local snapshot, at its existing revision."""
        validate_snapshot(self.artifacts, snapshot)
        with self.lock:
            current = self.head(snapshot.project_id)
            if current is not None:
                if current != snapshot:
                    raise RevisionConflict('Repository already contains a different project state')
                return current
            encoded = json.dumps(snapshot.to_dict(), sort_keys=True).encode('utf-8')
            digest = hashlib.sha256(encoded).hexdigest()
            project = self._project(snapshot.project_id)
            write_json(project/'revisions'/f'{snapshot.revision}-{digest}.json', snapshot.to_dict())
            write_json(project/'head.json', snapshot.to_dict())
            return snapshot
