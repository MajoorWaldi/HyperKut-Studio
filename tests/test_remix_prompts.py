import json
import subprocess

import pytest
from fastapi.testclient import TestClient

from backend.config import ROOT
from backend.jobs import JobStore
from backend.models import Shot
from backend.runner import MockRunner
from backend.server import create_app
from test_backend import _settings, _project_on_disk, _finished_job


@pytest.mark.parametrize("keep,check,failed,expected", [
    (False, False, False, "base prompt"),
    (False, False, True, "base prompt"),
    (False, True, False, "base prompt"),
    (False, True, True, "retry prompt"),
    (True, False, False, ""),
    (True, True, True, ""),
])
def test_recorded_prompt_follows_the_video_branch_lazily(keep, check, failed, expected):
    graph = json.loads((ROOT / "workflows/remix/shot.api.json").read_text(encoding="utf-8"))
    values = {("115", 2): keep, ("14", 0): check, ("110:9029", 0): failed,
              ("91:149", 0): "base prompt", ("108:149", 0): "retry prompt"}
    visited = set()

    def evaluate(link):
        if not isinstance(link, list):
            return link
        key = tuple(link)
        visited.add(key)
        if key in values:
            return values[key]
        node = graph[link[0]]
        assert node["class_type"] == "ComfySwitchNode"
        inputs = node["inputs"]
        return evaluate(inputs["on_true"] if evaluate(inputs["switch"]) else inputs["on_false"])

    assert evaluate(graph["119"]["inputs"]["generation_prompt"]) == expected
    if keep:
        assert ("91:149", 0) not in visited and ("108:149", 0) not in visited
    if not check or keep:
        assert ("110:9029", 0) not in visited
    assert graph["91:139"]["inputs"]["prompt"] == ["91:149", 0]
    assert graph["108:139"]["inputs"]["prompt"] == ["108:149", 0]
    assert graph["137"]["inputs"]["string_b"] == ["75", 3]


def test_exporter_reproduces_recorded_prompt_wiring():
    script = r"""
const fs = require('node:fs');
const source = fs.readFileSync('scripts\\export_templates.js', 'utf8');
const start = source.indexOf('  const retainRemixPrompts =');
const end = source.indexOf('  const titleOf =', start);
const retain = new Function(source.slice(start, end) + '\nreturn retainRemixPrompts;')();
const graph = JSON.parse(fs.readFileSync('workflows\\remix\\shot.api.json', 'utf8'));
const before = JSON.stringify(graph);
retain(graph);
if (JSON.stringify(graph) !== before) throw new Error('Exported Remix graph is stale');
"""
    subprocess.run(["node", "-e", script], cwd=ROOT, check=True, capture_output=True, text=True)


def test_api_take_selection_and_job_reopen_preserve_prompt_and_correction(tmp_path):
    config = _settings(tmp_path)
    folder = _project_on_disk(config)
    manifest = json.loads((folder / "manifest.json").read_text())
    row = manifest["shots"][0]
    row["plan"] = {"prompt": "User correction"}
    row["revisions"][1]["generation_prompt"] = "First generated prompt"
    row["revisions"][2]["generation_prompt"] = "Retry generated prompt"
    (folder / "manifest.json").write_text(json.dumps(manifest))
    runner = MockRunner(pace=.001)
    run = runner.run

    async def with_project(job):
        await run(job)
        job.update(project_id="p_0123456789ab")

    runner.run = with_project
    with TestClient(create_app(config, runner)) as client:
        job_id = _finished_job(client)
        endpoint = f"/api/jobs/{job_id}/shots/SHOT_001"
        takes = client.get(endpoint + "/takes").json()
        assert [t["generation_prompt"] for t in takes] == ["First generated prompt", "Retry generated prompt"]
        state = client.get(f"/api/jobs/{job_id}").json()
        assert state["shots"][0]["generation_prompt"] == "Retry generated prompt"
        assert state["shots"][0]["prompt"] == "User correction"
        assert client.post(endpoint + "/active", json={"take": "take_001"}).status_code == 200
        state = client.get(f"/api/jobs/{job_id}").json()
        assert state["shots"][0]["generation_prompt"] == "First generated prompt"
        assert state["shots"][0]["prompt"] == "User correction"
    with TestClient(create_app(config, runner)) as client:
        state = client.get(f"/api/jobs/{job_id}").json()
        assert state["shots"][0]["generation_prompt"] == "First generated prompt"
        assert state["shots"][0]["prompt"] == "User correction"


def test_sync_and_legacy_jobs_keep_generation_prompts_separate(tmp_path):
    from backend.models import JobRequest
    store = JobStore(tmp_path)
    job = store.create(JobRequest(mode="remix"))
    job.update(shots=[Shot(id="SHOT_001", start=0, duration=2, prompt="Correction")])
    job.sync_shots({"shots": [{"shot_id": "SHOT_001", "plan": {"prompt": "Correction"},
        "active_revision_id": "take_001", "revisions": [
            {"revision_id": "take_001", "generation_prompt": "Actual prompt"}]}]})
    restored = JobStore(tmp_path).get(job.id)
    assert restored.state.shots[0].prompt == "Correction"
    assert restored.state.shots[0].generation_prompt == "Actual prompt"
    job.sync_shots({"shots": [{"shot_id": "SHOT_001", "plan": None,
        "active_revision_id": "original", "revisions": [
            {"revision_id": "original", "media_range": {"start_frame": 0}}]}]})
    assert job.state.shots[0].generation_prompt == ""
