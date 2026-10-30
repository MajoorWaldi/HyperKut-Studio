"""Preflight storage accounting for local uploads and generation jobs."""
import json
import math
import os
import shutil
from pathlib import Path

from filelock import FileLock

from .storage import write_json

MIB = 1024**2
QUALITY_MIB_PER_SECOND = {'draft': 8, 'standard': 16, 'max': 28, 'xhigh': 48}


class CapacityError(ValueError):
    pass


def reservation_bytes(request, duration_seconds: float | None = None) -> int:
    settings = request.settings
    duration = settings.duration if duration_seconds is None else duration_seconds
    if not math.isfinite(duration) or duration < 0:
        raise ValueError('Capacity duration must be a finite non-negative number')
    rate = QUALITY_MIB_PER_SECOND[settings.quality]
    retries = settings.quality_check if request.mode == 'remix' else settings.retry_bad_takes
    return 256 * MIB + math.ceil(duration * rate * MIB * (2 if retries else 1))


def capacity_lock(settings) -> FileLock:
    return FileLock(str(settings.workspace / '.capacity.lock'), thread_local=False, timeout=30)


def _storage_roots(settings) -> list[Path]:
    candidates = [settings.workspace.resolve()]
    if settings.output_dir is not None:
        candidates.append((settings.output_dir / 'MajoorVideoTools').resolve())
    roots: list[Path] = []
    for candidate in candidates:
        if any(candidate == root or root in candidate.parents for root in roots):
            continue
        roots = [root for root in roots if candidate not in root.parents]
        roots.append(candidate)
    return roots


def _tree_bytes(root: Path) -> int:
    if not root.exists():
        return 0
    total = 0
    for directory, children, files in os.walk(root, followlinks=False):
        children[:] = [name for name in children if not (Path(directory) / name).is_symlink()]
        for name in files:
            path = Path(directory) / name
            if not path.is_symlink():
                total += path.stat().st_size
    return total


def _active_reservations(settings, store) -> int:
    directory = settings.workspace / '.job-reservations'
    active = {job.id for job in store.jobs.values() if job.state.status in ('queued', 'running')}
    total = 0
    for path in directory.glob('*.json'):
        if path.stem not in active:
            path.unlink()
            continue
        data = json.loads(path.read_text(encoding='utf-8'))
        amount = data.get('bytes')
        if type(amount) is not int or amount < 0:
            raise CapacityError(f'Invalid disk reservation record: {path.name}')
        total += amount
    return total


def ensure_capacity(settings, store, extra_bytes: int) -> None:
    if extra_bytes < 0:
        raise ValueError('Capacity reservation must not be negative')
    roots = _storage_roots(settings)
    used = sum(_tree_bytes(root) for root in roots)
    reserved = _active_reservations(settings, store)
    if used + reserved + extra_bytes > settings.max_workspace_bytes:
        raise CapacityError(
            'The configured workspace storage budget would be exceeded. '
            'Remove unused uploads or projects, or increase MAX_WORKSPACE_MB.'
        )

    checked_devices = set()
    required_free = settings.min_free_disk_bytes + extra_bytes
    for root in roots:
        probe = root
        while not probe.exists():
            probe = probe.parent
        device = probe.stat().st_dev
        if device in checked_devices:
            continue
        checked_devices.add(device)
        if shutil.disk_usage(probe).free < required_free:
            raise CapacityError(
                'There is not enough free disk space for this operation. '
                'Remove temporary files or increase the available disk space.'
            )


def write_reservation(settings, job_id: str, amount: int) -> None:
    write_json(settings.workspace / '.job-reservations' / f'{job_id}.json', {'bytes': amount})
