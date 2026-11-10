"""A plan whose API cost goes over the budget is paid only once it is approved: no other way out of the review starts paid takes."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import api_cost
from backend.jobs import Job, JobStore
from backend.models import JobRequest, JobState, Shot
from backend.runner import ComfyRunner
from backend.server import create_app
from test_backend import _settings
from test_resume import _saved_project

OVER = {'prompt': 'a film', 'video_model': 'seedance_2_5', 'api_budget_seconds': 1}


def _waiting(settings, status='review'):
    store = JobStore(settings.workspace / 'state')
    job = store.create(JobRequest(mode='text', settings=OVER))
    job.update(status=status, project_id='p_abcdef123456', api_cost={'over_budget': True, 'approved': False, 'seconds_high': 16},
               shots=[Shot(id='SHOT_001', start=0, duration=1, prompt='one'), Shot(id='SHOT_002', start=1, duration=1, prompt='two')])
    _saved_project(settings, job.id, job.state.project_id)
    return job


class _Counting(ComfyRunner):
    started: list

    async def run(self, current):
        self.started.append(current.id)
        current.update(status='succeeded', stage='done')


def test_resume_and_regenerate_do_not_take_a_plan_out_of_its_cost_review(tmp_path):
    settings = _settings(tmp_path)
    job = _waiting(settings)
    runner = _Counting(settings, {})
    runner.started = []
    with TestClient(create_app(settings, runner)) as client:
        assert client.post(f'/api/jobs/{job.id}/resume').status_code == 409
        assert client.post(f'/api/jobs/{job.id}/regenerate', json={'shots': ['SHOT_001'], 'prompts': {}}).status_code == 409
        assert client.get(f'/api/jobs/{job.id}').json()['status'] == 'review' and runner.started == []
        assert client.post(f'/api/jobs/{job.id}/approve', json={'prompts': {}}).status_code == 200  # the one way out
        cost = client.get(f'/api/jobs/{job.id}').json()['api_cost']
    assert runner.started == [job.id] and cost['approved'] and cost['approved_seconds'] == 16


@pytest.mark.asyncio
async def test_a_cancelled_plan_over_the_budget_goes_back_to_review_when_it_is_resumed(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    job = Job(JobRequest(mode='text', settings=OVER), JobState(id='overjob1', mode='text', status='cancelled', project_id='p_abcdef123456',
                                                                 shots=[Shot(id='SHOT_001', start=0, duration=1), Shot(id='SHOT_002', start=1, duration=1)]))
    _saved_project(settings, job.id, job.state.project_id)
    monkeypatch.setattr('backend.runner.load_templates', lambda *_: {'stage1': {}, 'shot': {}, 'local': {}, 'edit': {}})
    runner = ComfyRunner(settings, {})
    shots = []

    async def fake_run(client, current, template, values, stage, *args, **kwargs):
        shots.append(values.get('shot_id'))

    runner._run, runner._schemas = fake_run, lambda: asyncio.sleep(0, {})
    runner.client_factory = lambda: SimpleNamespace(aclose=lambda: asyncio.sleep(0))
    await runner.run(job)
    assert job.state.status == 'review' and shots == [] and job.state.api_cost['over_budget']  # nothing was asked of the model
    job.update(api_cost=api_cost.approve(job.state.api_cost), status='running')
    seen = []

    async def edit(client, current, templates, values, style=None):
        seen.append((values['api_budget_seconds'], values['api_budget_key']))
        current.update(status='succeeded')

    runner._edit = edit
    await runner.run(job)
    assert shots == ['SHOT_002'] and job.state.status == 'succeeded'  # approved: the shot left is made
    assert seen[0][0] >= 1 and seen[0][1] == job.id  # with the approved cap, never 0, counted under the job
