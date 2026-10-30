from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from backend.access import validate_access
from backend.config import Settings
from backend.runner import MockRunner
from backend.server import create_app


@pytest.fixture
def settings(tmp_path):
    return Settings("http://127.0.0.1:1", "http://127.0.0.1:1", tmp_path / "output",
                    tmp_path / "workspace", tmp_path / "templates", True)


def test_default_instance_rejects_non_loopback_clients(settings):
    with TestClient(create_app(settings, MockRunner(pace=0)), client=("192.0.2.1", 1234)) as client:
        assert client.get("/api/studio/status").status_code == 403
        assert client.get("/").status_code == 403


@pytest.mark.parametrize("changes", [
    {"access_mode": "unknown"}, {"access_mode": "jury"},
    {"access_mode": "jury", "access_username": "jury", "access_password": "short"},
    {"access_mode": "jury", "access_username": "jury", "access_password": "x" * 24, "allowed_hosts": ("*",)},
    {"max_workspace_bytes": True}, {"min_free_disk_bytes": -1},
])
def test_invalid_access_settings_fail_closed(settings, changes):
    with pytest.raises(ValueError):
        validate_access(replace(settings, **changes))


def jury(settings):
    return replace(settings, access_mode="jury", access_username="jury", access_password="test-only-password-of-32-characters")


def test_jury_requires_tls_and_auth_for_api_media_and_frontend(settings):
    config = jury(settings)
    auth = (config.access_username, config.access_password)
    with TestClient(create_app(config, MockRunner(pace=0)), base_url="http://testserver") as client:
        assert client.get("/api/studio/status", auth=auth).status_code == 403
    with TestClient(create_app(config, MockRunner(pace=0)), base_url="https://testserver") as client:
        for path in ("/", "/api/studio/status", "/api/uploads/not-known", "/assets/missing.js"):
            response = client.get(path)
            assert response.status_code == 401 and "Basic" in response.headers["www-authenticate"]
        assert client.get("/api/studio/status", auth=("jury", "wrong")).status_code == 401
        assert client.get("/api/studio/status", headers={"Authorization": "Basic !invalid!"}).status_code == 401
        status = client.get("/api/studio/status", auth=auth)
        assert status.status_code == 200 and config.access_password not in status.text
        assert client.post("/api/studio/restart", auth=auth).status_code == 403
        assert client.post("/api/uploads", auth=auth, headers={"Origin": "https://other.invalid"}).status_code == 403
    assert config.access_password not in repr(config)


def test_upload_storage_quota_rejects_and_removes_partial_file(settings):
    config = replace(settings, max_workspace_bytes=5)
    with TestClient(create_app(config, MockRunner(pace=0))) as client:
        assert client.post("/api/uploads", files={"file": ("one.wav", b"1234", "audio/wav")}).status_code == 200
        response = client.post("/api/uploads", files={"file": ("two.wav", b"12", "audio/wav")})
        assert response.status_code == 507
        assert sum(path.stat().st_size for path in (config.workspace / "uploads").iterdir()) == 4


def test_body_limit_is_checked_before_parsing(settings):
    with TestClient(create_app(settings, MockRunner(pace=0))) as client:
        for length in (str(17 * 1024**2), "9" * 5000, "-1", "unknown"):
            assert client.post("/api/jobs", content=b"{}", headers={"Content-Length": length}).status_code == 413


def test_project_import_uses_the_workspace_body_limit(settings):
    config = replace(settings, max_upload_bytes=15 * 1024**2, max_workspace_bytes=20 * 1024**2)
    with TestClient(create_app(config, MockRunner(pace=0))) as client:
        oversized_for_json = {"Content-Length": str(17 * 1024**2)}
        assert client.post('/api/jobs', content=b'{}', headers=oversized_for_json).status_code == 413
        assert client.post('/api/projects/import', content=b'{}', headers=oversized_for_json).status_code == 422
