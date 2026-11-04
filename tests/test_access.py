import json
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
    with TestClient(create_app(config, MockRunner(pace=0)), base_url="https://testserver", client=("127.0.0.1", 50000)) as client:
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


def test_open_jury_ignores_the_visitor_header_from_a_remote_caller(settings):
    config = open_jury(settings, visitor=1, total=5)
    request = {"mode": "text", "settings": {"prompt": "a test"}}
    with TestClient(create_app(config, MockRunner(pace=0)), base_url="https://testserver", client=("198.51.100.7", 50000)) as client:
        assert client.post("/api/jobs", json=request, headers={"CF-Connecting-IP": "203.0.113.1"}).status_code == 200
        assert client.post("/api/jobs", json=request, headers={"CF-Connecting-IP": "203.0.113.2"}).status_code == 429


def test_open_jury_keeps_each_visitor_to_their_own_uploads_and_projects(settings):
    app = create_app(open_jury(settings, visitor=2, total=4), MockRunner(pace=0))
    with TestClient(app, base_url="https://testserver") as owner, TestClient(app, base_url="https://testserver") as stranger:
        assert stranger.get("/").status_code in (200, 404)
        uploaded = owner.post("/api/uploads", files={"file": ("a.png", b"not checked in mock", "image/png")}).json()["id"]
        job = owner.post("/api/jobs", json={"mode": "text", "settings": {"prompt": "private"}}).json()["id"]
        assert owner.cookies.get("hyperkut_visitor") != stranger.cookies.get("hyperkut_visitor")
        assert [row["id"] for row in owner.get("/api/jobs").json()] == [job]
        assert owner.get(f"/api/jobs/{job}").status_code == 200
        assert owner.get(f"/api/uploads/{uploaded}").status_code == 200
        assert stranger.get("/api/jobs").json() == []
        assert stranger.get("/api/jobs/sizes").json() == {}
        assert stranger.get(f"/api/jobs/{job}").status_code == 404
        assert stranger.get(f"/api/jobs/{job}/inputs").status_code == 404
        assert stranger.post(f"/api/jobs/{job}/cancel").status_code == 404
        assert stranger.get(f"/api/uploads/{uploaded}").status_code == 404
        assert stranger.post("/api/jobs", json={"mode": "text", "settings": {"prompt": "x"}, "music": uploaded}).status_code == 422
    with TestClient(create_app(open_jury(settings, visitor=2, total=4), MockRunner(pace=0)), base_url="https://testserver", cookies=dict(owner.cookies)) as back:
        assert [row["id"] for row in back.get("/api/jobs").json()] == [job]  # the ownership survives a restart


def test_open_jury_gives_every_visitor_the_files_of_the_app_presets(settings):
    app = create_app(open_jury(settings, visitor=1, total=4), MockRunner(pace=0))
    with TestClient(app, base_url="https://testserver") as visitor:
        presets = {p["id"]: p for p in visitor.get("/api/presets").json()}
        remix, text = presets["remix-wild-counterpoint"], presets["text-portal-atelier"]
        assert remix["missing_inputs"] == [] and remix["inputs"]["source"]["id"] == "placeholder-video"
        assert visitor.get(remix["inputs"]["source"]["url"]).status_code == 200
        picture = text["inputs"]["refs"][0]["id"]
        assert visitor.get(f"/api/uploads/{picture}").status_code == 200
        held = visitor.post("/api/jobs", json={"mode": "remix", "settings": {"prompt": "x"}, "source": "placeholder-video", "refs": [picture]})
        assert held.status_code == 422 and "placeholder" in held.json()["detail"]  # refused, and the generation is given back
        assert visitor.post("/api/jobs", json={"mode": "text", "settings": {"prompt": "x"}, "refs": [picture]}).status_code == 200
        assert visitor.post("/api/storage/caches/clean").status_code == 403  # the jury never cleans; the files are in the app


def test_open_jury_limits_every_route_that_reaches_the_gpu(settings):
    config = open_jury(settings, visitor=1, total=2)
    request = {"mode": "text", "settings": {"prompt": "a test"}}
    with TestClient(create_app(config, MockRunner(pace=0)), base_url="https://testserver") as client:
        assert client.post("/api/brief-preview", json={"mode": "bad"}).status_code == 422  # refused: nothing is spent
        for _ in range(4):
            assert client.post("/api/brief-preview", json=request).status_code == 200
        refused = client.post("/api/brief-treatments", json=request)
        assert refused.status_code == 429 and "previews" in refused.json()["detail"]
        analysis = client.post("/api/jobs", json={**request, "settings": {**request["settings"], "review_plan": True}})
        assert analysis.status_code == 429  # an analysis is an action too
        assert client.post("/api/jobs", json=request).status_code == 200  # and the refused analysis gave its generation back


def test_public_instance_has_no_api_documentation(settings):
    with TestClient(create_app(open_jury(settings), MockRunner(pace=0)), base_url="https://testserver") as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 404


def test_open_jury_refunds_a_rejected_generation(settings):
    config = open_jury(settings, visitor=1, total=1)
    with TestClient(create_app(config, MockRunner(pace=0)), base_url="https://testserver") as client:
        assert client.post("/api/jobs", json={"mode": "bad"}).status_code == 422
        assert client.post("/api/jobs", json={"mode": "text", "settings": {"prompt": "ok"}}).status_code == 200


def test_open_jury_does_not_count_the_analysis_of_a_plan_to_review(settings):
    config = open_jury(settings, visitor=1, total=5)
    me = {"CF-Connecting-IP": "203.0.113.9"}
    review = {"mode": "text", "settings": {"prompt": "a test", "review_plan": True}}
    with TestClient(create_app(config, MockRunner(pace=0)), base_url="https://testserver", client=("127.0.0.1", 50000)) as client:
        assert client.post("/api/jobs", json=review, headers=me).status_code == 200
        assert client.post("/api/jobs", json=review, headers=me).status_code == 200  # two analyses, nothing counted
        assert json.loads((config.workspace / "jury-quota.json").read_text())["total"] == 0
        plain = {"mode": "text", "settings": {"prompt": "a test"}}
        assert client.post("/api/jobs", json=plain, headers=me).status_code == 200
        assert json.loads((config.workspace / "jury-quota.json").read_text())["total"] == 1
        assert client.post("/api/jobs", json=review, headers=me).status_code == 429  # the visitor has used the generation of the jury: no more plans either


def test_open_jury_takes_the_generation_when_the_plan_is_approved(settings):
    from backend.jobs import JobStore
    from backend.models import JobRequest, Shot
    from backend.runner import ComfyRunner
    from test_resume import _saved_project

    config = open_jury(settings, visitor=1, total=5)
    store = JobStore(config.workspace / "state")
    waiting = []
    for _ in range(2):
        job = store.create(JobRequest(mode="text"))
        job.update(status="review", project_id=f"p_abcdef12345{len(waiting)}", shots=[Shot(id="SHOT_001", start=0, duration=1, prompt="one")])
        _saved_project(config, job.id, job.state.project_id)
        waiting.append(job.id)

    class Runner(ComfyRunner):
        async def run(self, current):
            current.update(status="succeeded", stage="done")

    me = {"CF-Connecting-IP": "203.0.113.9"}
    visitor = "a" * 32
    (config.workspace / "jury-owners.json").write_text(json.dumps(dict.fromkeys(waiting, visitor)), encoding="utf-8")
    with TestClient(create_app(config, Runner(config, {})), base_url="https://testserver", client=("127.0.0.1", 50000), cookies={"hyperkut_visitor": visitor}) as client:
        assert client.post(f"/api/jobs/{waiting[0]}/approve", json={"prompts": {}}, headers=me).status_code == 200
        assert json.loads((config.workspace / "jury-quota.json").read_text())["total"] == 1
        refused = client.post(f"/api/jobs/{waiting[1]}/approve", json={"prompts": {}}, headers=me)
        assert refused.status_code == 429 and "1 generations" in refused.json()["detail"]


def test_local_mode_rejects_loopback_requests_forwarded_by_a_tunnel(settings):
    with TestClient(create_app(settings, MockRunner(pace=0)), client=("127.0.0.1", 1234)) as client:
        assert client.get("/api/studio/status").status_code == 200
        for header in ("CF-Connecting-IP", "X-Forwarded-For", "X-Real-IP"):
            assert client.get("/api/studio/status", headers={header: "203.0.113.9"}).status_code == 403


def test_jury_quota_covers_every_route_that_starts_gpu_work():
    from backend.access import CLOSED_ROUTES, GENERATION_ROUTE
    assert GENERATION_ROUTE.match("/api/jobs/abc/shots/s1/ai-candidates")
    assert not GENERATION_ROUTE.match("/api/jobs/abc/cancel")
    assert any(method == "PATCH" and route.match("/api/jobs/abc") for method, route in CLOSED_ROUTES)


def test_cross_origin_check_accepts_a_forwarded_https_scheme(settings):
    with TestClient(create_app(settings, MockRunner(pace=0)), client=("127.0.0.1", 1234)) as client:
        headers = {"Origin": "https://testserver", "Host": "testserver", "X-Forwarded-Proto": "https"}
        assert client.post("/api/brief-approve", json={}, headers=headers).status_code != 403
        assert client.post("/api/brief-approve", json={}, headers={**headers, "Origin": "https://evil.example"}).status_code == 403


def test_every_response_forbids_framing_and_foreign_scripts(settings):
    with TestClient(create_app(settings, MockRunner(pace=0)), client=("127.0.0.1", 1234)) as client:
        headers = client.get("/api/studio/status").headers
        assert headers["X-Frame-Options"] == "DENY"
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        assert "script-src 'self'" in headers["Content-Security-Policy"]
        assert headers["X-Content-Type-Options"] == "nosniff"
