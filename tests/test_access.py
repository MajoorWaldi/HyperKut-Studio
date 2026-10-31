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


def open_jury(settings, visitor=2, total=3):
    return replace(settings, access_mode="jury_open", jury_visitor_limit=visitor, jury_total_limit=total)


def test_open_jury_needs_tls_but_no_password_and_closes_sensitive_routes(settings):
    config = open_jury(settings)
    with TestClient(create_app(config, MockRunner(pace=0)), base_url="http://testserver") as client:
        assert client.get("/api/studio/status").status_code == 403
    with TestClient(create_app(config, MockRunner(pace=0)), base_url="https://testserver") as client:
        assert client.get("/api/studio/status").status_code == 200
        for method, path in (("POST", "/api/studio/restart"), ("POST", "/api/projects/import"), ("POST", "/api/storage/cache/gc"),
                             ("POST", "/api/jobs/abc/free"), ("DELETE", "/api/jobs/abc"), ("POST", "/api/presets"), ("DELETE", "/api/presets/abc")):
            assert client.request(method, path).status_code == 403, path


@pytest.mark.parametrize("changes", [{"allowed_hosts": ("*",)}, {"jury_visitor_limit": 0}, {"jury_visitor_limit": 5, "jury_total_limit": 4}])
def test_open_jury_settings_fail_closed(settings, changes):
    with pytest.raises(ValueError):
        validate_access(replace(open_jury(settings), **changes))


def test_open_jury_limits_generations_per_visitor_and_in_total(settings):
    config = open_jury(settings)
    request = {"mode": "text", "settings": {"prompt": "a test"}}
    with TestClient(create_app(config, MockRunner(pace=0)), base_url="https://testserver") as client:
        first = {"CF-Connecting-IP": "203.0.113.1"}
        second = {"CF-Connecting-IP": "203.0.113.2"}
        third = {"CF-Connecting-IP": "203.0.113.3"}
        assert client.post("/api/jobs", json=request, headers=first).status_code == 200
        assert client.post("/api/jobs", json=request, headers=first).status_code == 200
        refused = client.post("/api/jobs", json=request, headers=first)
        assert refused.status_code == 429 and "2 generations" in refused.json()["detail"]
        assert client.post("/api/jobs", json=request, headers=second).status_code == 200
        total = client.post("/api/jobs", json=request, headers=third)
        assert total.status_code == 429 and "3 generations" in total.json()["detail"]
    with TestClient(create_app(config, MockRunner(pace=0)), base_url="https://testserver") as client:
        assert client.post("/api/jobs", json=request, headers=third).status_code == 429  # the count survives a restart
    assert "203.0.113" not in (config.workspace / "jury-quota.json").read_text()


def test_open_jury_refunds_a_rejected_generation(settings):
    config = open_jury(settings, visitor=1, total=1)
    with TestClient(create_app(config, MockRunner(pace=0)), base_url="https://testserver") as client:
        assert client.post("/api/jobs", json={"mode": "bad"}).status_code == 422
        assert client.post("/api/jobs", json={"mode": "text", "settings": {"prompt": "ok"}}).status_code == 200
