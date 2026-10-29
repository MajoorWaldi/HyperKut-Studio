import pytest
from fastapi.testclient import TestClient
from backend.server import create_app
from backend.runner import MockRunner
from backend.jobs import JobStore
from backend.models import JobRequest
from backend import restart
from test_backend import _settings


def test_restart_accepts_idle_once_and_blocks_further_writes(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(restart, 'restart_command', lambda: ['python', '-m', 'uvicorn', 'backend.server:create_app'])
    monkeypatch.setattr(restart, 'launch_restart', lambda workspace: calls.append(workspace))
    config = _settings(tmp_path)
    with TestClient(create_app(config, MockRunner())) as client:
        response = client.post('/api/studio/restart')
        assert response.status_code == 202 and response.json()['instance_id']
        assert calls == [config.workspace]
        assert client.post('/api/studio/restart').status_code == 503
        assert client.post('/api/presets', json={'name': 'Blocked', 'mode': 'text'}).status_code == 503
        assert client.get('/api/presets').status_code == 200


def test_restart_refuses_a_running_project_and_cross_origin(tmp_path, monkeypatch):
    config = _settings(tmp_path)
    job = JobStore(config.workspace/'state').create(JobRequest(mode='text'))
    job.update(status='running')
    monkeypatch.setattr(restart, 'launch_restart', lambda _: pytest.fail('Must not spawn a helper'))
    with TestClient(create_app(config, MockRunner())) as client:
        assert client.post('/api/studio/restart').status_code == 409
        assert client.post('/api/studio/restart', headers={'Origin': 'https://foreign.invalid'}).status_code == 403


def test_restart_spawn_failure_reopens_admission(tmp_path, monkeypatch):
    monkeypatch.setattr(restart, 'restart_command', lambda: [])
    def failed(_):
        raise OSError('Spawn denied')
    monkeypatch.setattr(restart, 'launch_restart', failed)
    with TestClient(create_app(_settings(tmp_path), MockRunner())) as client:
        assert client.post('/api/studio/restart').status_code == 503
        assert client.post('/api/presets', json={'name': 'Still works', 'mode': 'text'}).status_code == 200


def test_restart_command_refuses_supervisors_and_unrelated_processes():
    command = ['python', '-m', 'uvicorn', 'backend.server:create_app', '--factory', '--port', '8090']
    assert restart.restart_command(command)[1:] == command[1:]
    for bad in [['python', '-m', 'pytest'], command + ['--reload'], command + ['--workers=2']]:
        with pytest.raises(ValueError):
            restart.restart_command(bad)
