import hashlib
import json
import os
import re
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Serialize cooperating writers; readers may still briefly hold the old file on Windows.
    with FileLock(str(path) + '.write.lock', timeout=5):
        fd, name = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(data, stream, indent=2, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            for attempt in range(20):
                try:
                    os.replace(name, path)
                    break
                except PermissionError:
                    if os.name != 'nt' or attempt == 19:
                        raise
                    time.sleep(min(.01 * 2**attempt,.2))
        finally:
            Path(name).unlink(missing_ok=True)


def project_path(root: Path, project_id: str) -> Path:
    if not re.fullmatch(r'p_[0-9a-f]{8,32}', project_id):
        raise ValueError('Invalid project id')
    root = root.resolve()
    path = (root / project_id).resolve()
    if path.parent != root:
        raise ValueError('Project path escapes its output folder')
    return path


@contextmanager
def edit_manifest(root: Path, project_id: str):
    project = project_path(root, project_id)
    with FileLock(str(project / '.lock'), timeout=120):
        manifest = json.loads((project / 'manifest.json').read_text(encoding='utf-8'))
        yield manifest
        manifest['project_revision'] = manifest.get('project_revision', 0) + 1
        key = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:12]
        write_json(project / 'manifests' / f'{key}.json', manifest)
        write_json(project / 'manifest.json', manifest)
