"""Preflight storage accounting for local uploads and generation jobs."""
import asyncio
import json
import math
import os
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path

from filelock import FileLock, Timeout

from .storage import write_json

MIB = 1024**2
QUALITY_MIB_PER_SECOND = {'draft': 8, 'standard': 16, 'max': 28, 'xhigh': 48}


class CapacityError(ValueError):
    pass


class CapacityBusy(RuntimeError):
    """The storage lock stayed held by an upload, an import or an export for the whole wait."""


def reservation_bytes(request, duration_seconds: float | None = None) -> int:
    settings = request.settings
    duration = settings.duration if duration_seconds is None else duration_seconds
    if not math.isfinite(duration) or duration < 0:
        raise ValueError('Capacity duration must be a finite non-negative number')
    rate = QUALITY_MIB_PER_SECOND[settings.quality]
    retries = (settings.quality_check if request.mode == 'remix' else settings.retry_bad_takes) or settings.best_of_two
    return 256 * MIB + math.ceil(duration * rate * MIB * (2 if retries else 1))


def capacity_lock(settings) -> FileLock:
    return FileLock(str(settings.workspace / '.capacity.lock'), thread_local=False, timeout=30)


async def acquire_async(lock: FileLock, timeout: float = 30) -> None:
    """Wait for the lock without blocking the event loop: the request that holds it must be able to finish and release it."""
    started = time.monotonic()
    while True:
        try:
            lock.acquire(timeout=0)
            return
        except Timeout:
            if time.monotonic() - started >= timeout:
                raise CapacityBusy('Storage is busy with an upload, an import or an export. Retry shortly.') from None
            await asyncio.sleep(.05)


@asynccontextmanager
async def capacity_held(settings, timeout: float = 30):
    lock = capacity_lock(settings)
    await acquire_async(lock, timeout)
    try:
        yield
    finally:
        lock.release()


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


UPLOAD_RESERVATION_SECONDS = 6 * 3600  # an upload whose request died without its cleanup frees its room after this


def write_upload_reservation(settings, upload_id: str, amount: int) -> None:
    """The room of an upload being written, counted while the file grows outside the lock."""
    write_json(settings.workspace / '.upload-reservations' / f'{upload_id}.json', {'bytes': int(amount)})


def release_upload_reservation(settings, upload_id: str) -> None:
    (settings.workspace / '.upload-reservations' / f'{upload_id}.json').unlink(missing_ok=True)


def _upload_reservations(settings) -> int:
    total, now = 0, time.time()
    for path in (settings.workspace / '.upload-reservations').glob('*.json'):
        try:
            if now - path.stat().st_mtime > UPLOAD_RESERVATION_SECONDS:
                path.unlink(missing_ok=True)
                continue
            amount = json.loads(path.read_text(encoding='utf-8')).get('bytes')
        except (OSError, ValueError):
            continue
        part = settings.workspace / 'uploads' / f'{path.stem}.part'
        written = part.stat().st_size if part.is_file() else 0  # the part already on disk is counted by the walk
        if type(amount) is int and amount > written:
            total += amount - written
    return total


def _active_reservations(settings, store) -> int:
    directory = settings.workspace / '.job-reservations'
    active = {job.id for job in store.jobs.values() if job.state.status in ('queued', 'running')}
    total = _upload_reservations(settings)
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


def ensure_capacity(settings, store, extra_bytes: int) -> int:
    """Raises CapacityError when extra_bytes do not fit; returns the bytes that still fit, so a stream can count down instead of scanning again."""
    if extra_bytes < 0:
        raise ValueError('Capacity reservation must not be negative')
    roots = _storage_roots(settings)
    used = sum(_tree_bytes(root) for root in roots)
    reserved = _active_reservations(settings, store)
    room = settings.max_workspace_bytes - used - reserved
    if extra_bytes > room:
        raise CapacityError(
            'The configured workspace storage budget would be exceeded. '
            'Remove unused uploads or projects, or increase MAX_WORKSPACE_MB.'
        )

    checked_devices = set()
    for root in roots:
        probe = root
        while not probe.exists():
            probe = probe.parent
        device = probe.stat().st_dev
        if device in checked_devices:
            continue
        checked_devices.add(device)
        free = shutil.disk_usage(probe).free - settings.min_free_disk_bytes
        if free < extra_bytes:
            raise CapacityError(
                'There is not enough free disk space for this operation. '
                'Remove temporary files or increase the available disk space.'
            )
        room = min(room, free)
    return room


def write_reservation(settings, job_id: str, amount: int) -> None:
    write_json(settings.workspace / '.job-reservations' / f'{job_id}.json', {'bytes': amount})
