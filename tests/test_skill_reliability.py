import asyncio
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import httpx
import pytest

from backend.jobs import Job, JobStore
from backend.models import JobRequest
from backend.runner import ComfyRunner
from backend.server import create_app
from backend.storage import write_json
from test_audit_regressions import settings


def test_writers_to_one_state_file_are_serialized(tmp_path, monkeypatch):
    import backend.storage as storage
    replace = storage.os.replace
    active = peak = 0
    guard = threading.Lock()

    def slow_replace(*args):
        nonlocal active, peak
        with guard:
            active += 1
            peak = max(peak, active)
        try:
            time.sleep(.02)
            return replace(*args)
        finally:
            with guard:
                active -= 1

    monkeypatch.setattr(storage.os, 'replace', slow_replace)
    path = tmp_path / 'state.json'
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda n: write_json(path, {'n': n}), range(12)))
    assert peak == 1
    assert json.loads(path.read_text())['n'] in range(12)
    assert not list(tmp_path.glob('*.tmp'))


def test_failed_write_preserves_previous_state(tmp_path, monkeypatch):
    import backend.storage as storage
    path = tmp_path / 'state.json'
    write_json(path, {'n': 1})

    def fail(*args):
        raise OSError('disk unavailable')

    monkeypatch.setattr(storage.os, 'replace', fail)
    with pytest.raises(OSError, match='disk unavailable'):
        write_json(path, {'n': 2})
    assert json.loads(path.read_text()) == {'n': 1}
    assert not list(tmp_path.glob('*.tmp'))


async def test_concurrent_mutations_reconcile_a_persisted_handle_once(tmp_path):
    config = settings(tmp_path)
    store = JobStore(config.workspace / 'state')
    old = store.create(JobRequest(mode='text'))
    old.update(status='failed')
    old.record_handle('only-this-sdk-job')

    class Runner(ComfyRunner):
        calls = 0

        async def recover(self, job):
            self.calls += 1
            await asyncio.sleep(.04)
            assert job.pending_handle == 'only-this-sdk-job'
            job.record_handle(None)

        async def run(self, job):
            job.update(status='succeeded')

    runner = Runner(config, {})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(config, runner)), base_url='http://testserver') as client:
        responses = await asyncio.gather(*(client.post('/api/jobs', json={'mode': 'text'}) for _ in range(2)))
    assert all(r.status_code in (200, 429) for r in responses)
    assert runner.calls == 1
    assert JobStore(config.workspace / 'state').get(old.id).pending_handle is None


async def test_empty_exception_is_actionable_and_never_resubmitted(tmp_path):
    class Runner(ComfyRunner):
        calls = 0

        async def _run(self, *args, **kwargs):
            self.calls += 1
            raise TimeoutError()

    runner = Runner(settings(tmp_path), {}, lambda: SimpleNamespace(aclose=lambda: asyncio.sleep(0)))
    job = Job(JobRequest(mode='text'))
    await runner.run(job)
    assert job.state.status == 'failed'
    assert 'TimeoutError' in job.state.error and 'Saved takes' in job.state.error
    assert runner.calls == 1


@pytest.mark.parametrize('cancel_fails', [False, True])
async def test_lost_progress_cancels_only_own_request_or_keeps_handle(tmp_path, cancel_fails):
    from test_backend import FakeClient, _settings, _templates
    _templates(tmp_path / 'workflows')
    config = _settings(tmp_path, mock=False)
    job = JobStore(config.workspace / 'state').create(JobRequest(mode='text'))
    client = FakeClient(config.output_dir / 'MajoorVideoTools' / '_jobs' / f'{job.id}.json')
    submit = client.submit
    calls = []

    async def interrupted(workflow):
        handle = await submit(workflow)
        calls.append(handle.id)

        async def events():
            assert JobStore(config.workspace / 'state').get(job.id).pending_handle == handle.id
            raise ConnectionError('progress connection lost')
            yield  # async generator protocol

        handle.events = events
        if cancel_fails:
            async def cancel():
                raise ConnectionError('proxy offline')
            handle.cancel = cancel
        return handle

    client.submit = interrupted
    await ComfyRunner(config, {}, lambda: client).run(job)
    saved = JobStore(config.workspace / 'state').get(job.id)
    assert job.state.status == 'failed' and len(calls) == 1
    assert saved.pending_handle == (calls[0] if cancel_fails else None)
    assert 'progress connection lost' in job.state.error


async def test_accepted_submission_with_lost_ack_is_recovered_by_its_persisted_key(tmp_path):
    from dataclasses import replace
    from test_backend import FakeClient, _settings, _templates
    _templates(tmp_path / 'workflows')
    config = replace(_settings(tmp_path, mock=False), job_metadata_labels=True)
    job = JobStore(config.workspace / 'state').create(JobRequest(mode='text'))

    class Client(FakeClient):
        calls = 0
        handle = None
        async def submit(self, workflow, **options):
            self.calls += 1
            self.key = options['idempotency_key']
            assert JobStore(config.workspace / 'state').get(job.id).submission_key == self.key
            self.handle = await super().submit(workflow)
            error = TimeoutError('response lost after acceptance')
            error.idempotency_key = self.key
            raise error
        async def list_jobs(self, **filters):
            assert filters['metadata'] == {'secator_submission': self.key}
            yield SimpleNamespace(id=self.handle.id)

    client = Client(config.output_dir / 'MajoorVideoTools' / '_jobs' / f'{job.id}.json')
    async def get(id):
        assert id == client.handle.id
        return client.handle
    client.jobs = SimpleNamespace(get=get)
    runner = ComfyRunner(config, {}, lambda: client)
    await runner.run(job)
    assert job.state.status == 'failed' and client.calls == 1
    restored = JobStore(config.workspace / 'state').get(job.id)
    assert restored.submission_key == client.key and restored.pending_handle is None
    await runner.recover(restored)
    assert client.cancelled and client.calls == 1
    assert JobStore(config.workspace / 'state').get(job.id).submission_key is None


async def test_uncertain_submission_without_unique_match_remains_blocked(tmp_path):
    job = JobStore(tmp_path / 'state').create(JobRequest(mode='text'))
    job.record_submission('uncertain-key')
    async def list_jobs(**kwargs):
        if False: yield
    client = SimpleNamespace(list_jobs=list_jobs, aclose=lambda: asyncio.sleep(0))
    with pytest.raises(Exception, match='uncertain'):
        await ComfyRunner(settings(tmp_path), {}, lambda: client).recover(job)
    assert JobStore(tmp_path / 'state').get(job.id).submission_key == 'uncertain-key'


async def test_local_proxy_receives_no_unsupported_label_object(tmp_path):
    from test_backend import FakeClient, _settings, _templates
    _templates(tmp_path / 'workflows')
    config = _settings(tmp_path, mock=False)
    job = JobStore(config.workspace / 'state').create(JobRequest(mode='text'))
    class Client(FakeClient):
        calls = 0
        async def list_jobs(self, **kwargs):
            if False: yield
        async def submit(self, workflow, **options):
            self.calls += 1
            assert 'metadata' not in options
            assert options['idempotency_key'].startswith('secator-' + job.id)
            return await super().submit(workflow)
    client = Client(config.output_dir / 'MajoorVideoTools' / '_jobs' / f'{job.id}.json')
    await ComfyRunner(config, {}, lambda: client).run(job)
    assert job.state.status == 'succeeded' and client.calls > 0


async def test_local_proxy_lost_ack_stays_blocked_without_guessing_a_job(tmp_path):
    job = JobStore(tmp_path / 'state').create(JobRequest(mode='text'))
    job.record_submission('uncertain-local-key')
    async def list_jobs(**kwargs):
        raise AssertionError('Do not infer a match from the unfiltered proxy history')
        yield
    client = SimpleNamespace(list_jobs=list_jobs, aclose=lambda: asyncio.sleep(0))
    with pytest.raises(Exception, match='no submission labels'):
        await ComfyRunner(settings(tmp_path), {}, lambda: client).recover(job)
    assert job.submission_key == 'uncertain-local-key'
