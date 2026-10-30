import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.jobs import Job, JobStore
from backend.models import JobRequest, JobState, Shot
from backend.runner import ComfyRunner
from backend.server import create_app
from test_backend import _settings


def _saved_project(settings, job_id, project_id):
    root = settings.output_dir / 'MajoorVideoTools'
    project = root / project_id
    (project / 'generated').mkdir(parents=True)
    (root / '_jobs').mkdir(parents=True, exist_ok=True)
    rows = [
        {'id': 'SHOT_001', 'start': 0, 'duration': 1, 'prompt': 'one', 'render_source': 'generated'},
        {'id': 'SHOT_002', 'start': 1, 'duration': 1, 'prompt': 'two', 'render_source': 'generated'},
    ]
    (root / '_jobs' / f'{job_id}.json').write_text(json.dumps({'project_id': project_id, 'shots': rows}))
    manifest_shots = [
        {'shot_id': 'SHOT_001', 'active_revision_id': 'take_001',
         'revisions': [{'revision_id': 'take_001', 'media_ref': 'generated/one.mp4', 'media_range': None}]},
        {'shot_id': 'SHOT_002', 'active_revision_id': None, 'revisions': []},
    ]
    (project / 'manifest.json').write_text(json.dumps({'shots': manifest_shots}))
    return project


@pytest.mark.asyncio
async def test_runner_resume_skips_completed_shots_and_only_edits_after_remaining_work(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    job_id, project_id = 'resumejob1', 'p_abcdef123456'
    project = _saved_project(settings, job_id, project_id)
    job = Job(JobRequest(mode='text'), JobState(
        id=job_id, mode='text', status='cancelled', project_id=project_id,
        shots=[Shot(id='SHOT_001', start=0, duration=1, done=True),
               Shot(id='SHOT_002', start=1, duration=1, done=False)],
    ))
    runner = ComfyRunner(settings, {})
    calls = []
    monkeypatch.setattr('backend.runner.load_templates', lambda *_: {'stage1': {}, 'shot': {}, 'local': {}, 'edit': {}})

    async def fake_run(client, current, template, values, stage, *args, **kwargs):
        calls.append((stage, values.get('shot_id')))
        if stage == 'shots':
            manifest_path = project / 'manifest.json'
            manifest = json.loads(manifest_path.read_text())
            shot = next(row for row in manifest['shots'] if row['shot_id'] == values['shot_id'])
            shot['active_revision_id'] = 'take_001'
            shot['revisions'].append({
                'revision_id': 'take_001',
                'media_ref': 'generated/two.mp4',
                'media_range': None,
            })
            manifest_path.write_text(json.dumps(manifest))

    async def fake_edit(client, current, templates, values, style=None):
        calls.append(('edit', None))
        current.update(status='succeeded', stage='done')

    runner._run = fake_run
    runner._edit = fake_edit
    runner.client_factory = lambda: SimpleNamespace(aclose=lambda: asyncio.sleep(0))

    await runner.run(job)
    assert calls == [('shots', 'SHOT_002'), ('edit', None)]
    assert job.state.status == 'succeeded'
    assert all(shot.done for shot in job.state.shots)


def test_resume_endpoint_requires_a_persisted_plan_and_restarts_the_same_job(tmp_path):
    settings = _settings(tmp_path)
    store = JobStore(settings.workspace / 'state')
    job = store.create(JobRequest(mode='text'))
    job.update(status='failed', project_id='p_abcdef123456',
               shots=[Shot(id='SHOT_001', start=0, duration=1, done=True)])
    project = _saved_project(settings, job.id, job.state.project_id)
    submitted = []

    class Runner(ComfyRunner):
        async def run(self, current):
            submitted.append(current.id)
            current.update(status='succeeded', stage='done')

    runner = Runner(settings, {})
    with TestClient(create_app(settings, runner)) as client:
        response = client.post(f'/api/jobs/{job.id}/resume')
        assert response.status_code == 200
        client.get(f'/api/jobs/{job.id}/events')
        assert client.get(f'/api/jobs/{job.id}').json()['status'] == 'succeeded'
    assert submitted == [job.id]
    assert project.is_dir()


def test_resume_without_a_saved_plan_is_rejected(tmp_path):
    settings = _settings(tmp_path)
    store = JobStore(settings.workspace / 'state')
    job = store.create(JobRequest(mode='text'))
    job.update(status='failed')
    with TestClient(create_app(settings, ComfyRunner(settings, {}))) as client:
        response = client.post(f'/api/jobs/{job.id}/resume')
    assert response.status_code == 409
