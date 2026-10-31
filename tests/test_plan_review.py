import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.jobs import Job, JobStore
from backend.models import JobRequest, JobState, Settings, Shot
from backend.runner import ComfyRunner, MockRunner
from backend.server import create_app
from test_backend import _settings
from test_resume import _saved_project


def wait_for(client, job_id, status):
    for _ in range(200):
        state = client.get(f'/api/jobs/{job_id}').json()
        if state['status'] == status:
            return state
        client.get(f'/api/jobs/{job_id}/events')
    raise AssertionError(f'{job_id} stayed {state["status"]}')


def test_a_reviewed_mock_plan_waits_then_is_generated_with_the_changed_prompt(tmp_path):
    with TestClient(create_app(_settings(tmp_path), MockRunner(pace=0))) as client:
        job_id = client.post('/api/jobs', json={'mode': 'text', 'settings': {'prompt': 'a test', 'review_plan': True}}).json()['id']
        waiting = wait_for(client, job_id, 'review')
        assert waiting['shots'] and not any(shot['done'] for shot in waiting['shots']) and waiting['generation_budget']['seconds'] > 0
        client.post(f'/api/jobs/{job_id}/approve', json={'prompts': {}})  # no saved plan: refused, the review stays open
        assert client.get(f'/api/jobs/{job_id}').json()['status'] == 'review'
        assert client.post(f'/api/jobs/{job_id}/approve', json={'prompts': {'NOPE': 'x'}}).status_code == 422
        assert client.post(f'/api/jobs/{job_id}/cancel').json()['status'] == 'cancelled'
        assert client.post(f'/api/jobs/{job_id}/approve', json={}).status_code == 409


def test_without_review_a_mock_job_runs_to_the_end(tmp_path):
    with TestClient(create_app(_settings(tmp_path), MockRunner(pace=0))) as client:
        job_id = client.post('/api/jobs', json={'mode': 'text', 'settings': {'prompt': 'a test'}}).json()['id']
        assert all(shot['done'] for shot in wait_for(client, job_id, 'succeeded')['shots'])


def test_approving_writes_the_changed_prompts_into_the_project_and_restarts_the_job(tmp_path):
    settings = _settings(tmp_path)
    store = JobStore(settings.workspace / 'state')
    job = store.create(JobRequest(mode='text'))
    job.update(status='review', project_id='p_abcdef123456', shots=[Shot(id='SHOT_001', start=0, duration=1, prompt='one'), Shot(id='SHOT_002', start=1, duration=1, prompt='two')])
    project = _saved_project(settings, job.id, job.state.project_id)
    started = []

    class Runner(ComfyRunner):
        async def run(self, current):
            started.append(current.id)
            current.update(status='succeeded', stage='done')

    with TestClient(create_app(settings, Runner(settings, {}))) as client:
        assert client.post(f'/api/jobs/{job.id}/approve', json={'prompts': {'SHOT_002': 'two, closer', 'SHOT_001': 'one'}}).status_code == 200
        wait_for(client, job.id, 'succeeded')
    manifest = json.loads((project / 'manifest.json').read_text())
    plans = {row['shot_id']: (row.get('plan') or {}).get('prompt') for row in manifest['shots']}
    assert plans == {'SHOT_001': None, 'SHOT_002': 'two, closer'}  # the prompt left as it was is not rewritten
    assert started == [job.id]


@pytest.mark.asyncio
async def test_the_runner_stops_after_the_plan_when_it_is_reviewed_and_makes_no_shot(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    job_id, project_id = 'reviewjob1', 'p_abcdef123456'
    _saved_project(settings, job_id, project_id)
    job = Job(JobRequest(mode='text', settings=Settings(review_plan=True)), JobState(id=job_id, mode='text'))
    runner = ComfyRunner(settings, {})
    calls = []
    monkeypatch.setattr('backend.runner.load_templates', lambda *_: {'stage1': {}, 'shot': {}, 'local': {}, 'edit': {}})

    async def fake_run(client, current, template, values, stage, *args, **kwargs):
        calls.append(stage)

    runner._run = fake_run
    runner.client_factory = lambda: SimpleNamespace(aclose=lambda: asyncio.sleep(0))
    await runner.run(job)
    assert calls == ['analyze'] and job.state.status == 'review'
    assert job.state.generation_budget['seconds'] > 0


def test_a_plan_index_that_names_its_takes_can_be_resumed(tmp_path):
    settings = _settings(tmp_path)
    job = Job(JobRequest(mode='text'), JobState(id='indexjob1', mode='text', status='review', project_id='p_abcdef123456', shots=[Shot(id='SHOT_001', start=0, duration=1)]))
    _saved_project(settings, job.id, job.state.project_id)
    index = settings.output_dir / 'MajoorVideoTools' / '_jobs' / f'{job.id}.json'
    saved = json.loads(index.read_text())
    saved['shots'][0]['takes'] = ['original']
    index.write_text(json.dumps(saved))
    ComfyRunner(settings, {})._hydrate_project(job)
    assert isinstance(job.state.shots[0].takes, int)
