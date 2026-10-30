from dataclasses import replace

from fastapi.testclient import TestClient

from backend.capacity import CapacityError, ensure_capacity, reservation_bytes
from backend.config import ROOT
from backend.jobs import JobStore
from backend.models import JobRequest
from backend.runner import MockRunner
from backend.server import create_app
from test_backend import _settings


def test_job_reservation_scales_with_quality_and_retry_budget():
    draft = JobRequest(mode='text', settings={'duration': 10, 'quality': 'draft', 'retry_bad_takes': False})
    max_quality = JobRequest(mode='text', settings={'duration': 10, 'quality': 'max', 'retry_bad_takes': True})
    assert reservation_bytes(max_quality) > reservation_bytes(draft)
    assert reservation_bytes(draft, 2) < reservation_bytes(draft, 10)


def test_job_is_rejected_before_runner_submission_when_workspace_budget_is_full(tmp_path):
    settings = replace(_settings(tmp_path), max_workspace_bytes=1024)
    runner = MockRunner(pace=0)
    with TestClient(create_app(settings, runner)) as client:
        response = client.post('/api/jobs', json={'mode': 'text'})
        assert response.status_code == 507
        assert 'workspace storage budget' in response.json()['detail']
        assert client.get('/api/jobs').json() == []


def test_job_capacity_includes_existing_output_projects(tmp_path):
    settings = replace(
        _settings(tmp_path),
        output_dir=tmp_path / 'out',
        max_workspace_bytes=1024,
        min_free_disk_bytes=0,
    )
    project = settings.output_dir / 'MajoorVideoTools' / 'p_abcdef12'
    project.mkdir(parents=True)
    (project / 'take.mp4').write_bytes(b'x' * 2048)
    store = JobStore(settings.workspace / 'state')
    request = JobRequest(mode='text')
    try:
        ensure_capacity(settings, store, reservation_bytes(request))
    except CapacityError as error:
        assert 'workspace storage budget' in str(error)
    else:
        raise AssertionError('Expected existing ComfyUI project media to count toward the budget')


def test_re_edit_is_rejected_when_output_budget_is_exhausted(tmp_path):
    settings = replace(_settings(tmp_path), max_workspace_bytes=400 * 1024**2, min_free_disk_bytes=1)
    with TestClient(create_app(settings, MockRunner(pace=0))) as client:
        job = client.post('/api/jobs', json={'mode': 'text', 'settings': {'duration': 2}}).json()
        client.get(f"/api/jobs/{job['id']}/events").text
        filler = settings.workspace / 'capacity-filler.bin'
        with filler.open('wb') as stream:
            stream.seek(120 * 1024**2 - 1)
            stream.write(b'x')

        rejected = client.post(f"/api/jobs/{job['id']}/re-edit", json={})
        assert rejected.status_code == 507
        assert client.get(f"/api/jobs/{job['id']}").json()['status'] == 'succeeded'
