"""Durable operation journal: retain identities through rendering and downloads."""
import re
from pathlib import Path

from filelock import FileLock

from .project_snapshot import read_json
from .storage import write_json

_STATES = {'prepared': {'submitting', 'cancelled'},
           'submitting': {'submitted', 'cancelled'},
           'submitted': {'rendered', 'cancelled', 'failed'},
           'rendered': {'downloaded', 'cancelled'},
           'downloaded': {'applied', 'conflict'},
           'applied': set(), 'conflict': set(), 'cancelled': set(), 'failed': set()}


class OperationJournal:
    def __init__(self, root):
        self.root = Path(root)
        from .artifact_store import LocalArtifactStore
        LocalArtifactStore(self.root)
        self.lock = FileLock(str(self.root / '.journal.lock'), timeout=120)

    def _path(self, operation_id):
        if not isinstance(operation_id, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', operation_id):
            raise ValueError('Invalid operation id')
        return self.root / f'{operation_id}.json'

    def read(self, operation_id):
        with self.lock:
            path = self._path(operation_id)
            return read_json(path.read_bytes()) if path.exists() else None

    def prepare(self, operation_id, *, request_sha256, project_id, expected_revision):
        from .artifact_contract import ArtifactRef, ProjectSnapshot
        ArtifactRef(request_sha256, 0)
        ProjectSnapshot(project_id, max(expected_revision, 1), ArtifactRef('0' * 64, 0))
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError('Invalid expected revision')
        with self.lock:
            record = {'operation_id':operation_id, 'request_sha256':request_sha256,
                      'project_id':project_id, 'expected_revision':expected_revision,
                      'idempotency_key':'hyperkut-' + operation_id, 'status':'prepared', 'handle_id':None, 'result_snapshot':None}
            previous = self.read(operation_id)
            if previous:
                if any(previous[key] != record[key] for key in ('request_sha256','project_id','expected_revision')):
                    raise ValueError('Operation id reused with a different request')
                return previous
            write_json(self._path(operation_id), record)
            return record

    def transition(self, operation_id, expected_status, status, *, handle_id=None, result_snapshot=None):
        with self.lock:
            record = self.read(operation_id)
            if not record or record['status'] != expected_status:
                raise ValueError('Operation state changed; reload before continuing')
            if status not in _STATES.get(expected_status, ()):
                raise ValueError('Invalid operation transition')
            if handle_id is not None:
                if not isinstance(handle_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', handle_id):
                    raise ValueError('Invalid SDK handle id')
                if record['handle_id'] not in (None, handle_id):
                    raise ValueError('Operation cannot switch SDK handles')
                record['handle_id'] = handle_id
            if status in ('submitted','rendered','downloaded','applied') and not record['handle_id']:
                raise ValueError('Operation must retain an SDK handle')
            if result_snapshot is not None:
                from .artifact_contract import ProjectSnapshot
                snapshot = ProjectSnapshot.from_dict(result_snapshot)
                if status != 'downloaded' or snapshot.project_id != record['project_id'] or snapshot.revision != record['expected_revision']+1:
                    raise ValueError('Operation result snapshot does not match its identity/revision')
                record['result_snapshot'] = snapshot.to_dict()
            record['status'] = status
            write_json(self._path(operation_id), record)
            return record
