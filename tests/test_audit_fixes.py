"""Fixes of the deep audit: the end of a job reaches its stream, the API key never travels in clear, the deployment schemas grow old."""
import json
import os
import time

import pytest

from backend.config import key_travels_safely
from backend.deployment import cached_schemas, _cache_path
from backend.jobs import Job
from backend.models import JobRequest
from test_backend import _settings


@pytest.mark.asyncio
async def test_the_last_state_of_a_job_reaches_a_stream_that_was_busy_when_it_came():
    job = Job(JobRequest(mode='text', settings={'prompt': 'x'}))
    events = job.events()
    assert (await events.__anext__()).status == 'queued'
    job.update(status='running')
    assert (await events.__anext__()).status == 'running'
    job.update(status='succeeded')  # comes while the stream is still sending "running"
    assert (await events.__anext__()).status == 'succeeded'
    with pytest.raises(StopAsyncIteration):
        await events.__anext__()


def test_the_api_key_goes_only_over_https_or_to_this_computer():
    assert key_travels_safely('https://deploy.example.com') and key_travels_safely('http://127.0.0.1:8189') and key_travels_safely('http://localhost:9')
    assert not key_travels_safely('http://deploy.example.com') and not key_travels_safely('ftp://127.0.0.1')


def test_the_schemas_of_a_deployment_are_read_again_after_a_day(tmp_path):
    settings = _settings(tmp_path)
    path = _cache_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'Node': {}}), encoding='utf-8')
    assert cached_schemas(settings) == {'Node': {}}
    old = time.time() - 2 * 24 * 3600
    os.utime(path, (old, old))
    assert cached_schemas(settings) is None and not path.exists()  # redeployed at the same address: the badges and schemas are read again
    path.write_text('{damaged', encoding='utf-8')
    assert cached_schemas(settings) is None and not path.exists()
