import asyncio
import pytest
from backend.jobs import JobStore
from backend.models import JobRequest


def test_transient_progress_lock_keeps_gpu_handle_and_delivers_live_progress(tmp_path, monkeypatch):
    store = JobStore(tmp_path / 'state')
    job = store.create(JobRequest(mode='text'))
    job.record_handle('owned-request')
    queue = asyncio.Queue(maxsize=1)
    job._listeners.append(queue)
    def locked(_):
        raise PermissionError('temporary reader lock')
    monkeypatch.setattr(store, 'save', locked)
    job.update(progress=.5, node='sampler', step=5, steps=10)
    assert queue.get_nowait().progress == .5
    saved = JobStore(tmp_path / 'state').get(job.id)
    assert saved.pending_handle == 'owned-request'
    assert saved.state.progress == 0
    with pytest.raises(PermissionError):
        job.update(status='succeeded')


def test_progress_is_throttled_but_handles_and_stage_changes_always_persist(tmp_path, monkeypatch):
    import backend.jobs as module
    store = JobStore(tmp_path / 'state')
    job = store.create(JobRequest(mode='text'))
    monkeypatch.setattr(module.time, 'monotonic', lambda: 100.)
    job.update(status='running', stage='shots')
    for step in range(10):
        job.update(progress=step / 10)
    saved = JobStore(tmp_path / 'state').get(job.id)
    assert saved.state.progress == 0 and job.state.progress == .9
    job.record_handle('new-owned-request')
    saved = JobStore(tmp_path / 'state').get(job.id)
    assert saved.pending_handle == 'new-owned-request' and saved.state.progress == .9
