import asyncio
import json
import subprocess
from pathlib import Path

import pytest
from comfy_sdk import JobFailed, Progress, StatusChange
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.jobs import Job
from backend.models import EditStyle, JobRequest, Shot
from backend.runner import ComfyRunner, MockRunner
from backend.server import create_app
from backend.templates import Template, TemplateError, load_templates


def _settings(tmp_path, templates=None, mock=True) -> Settings:
    return Settings("http://127.0.0.1:1", "http://127.0.0.1:1", tmp_path / "out", tmp_path / "workspace", templates or tmp_path / "workflows", mock)


# ---- templates ---------------------------------------------------------------------------------------------------

def test_a_template_fills_its_slots_in_a_copy_and_refuses_a_name_it_does_not_have():
    template = Template({"1": {"class_type": "PrimitiveStringMultiline", "inputs": {"value": ""}}}, {"idea": (("1", "value"),)})
    assert template.fill({"idea": "hello"})["1"]["inputs"]["value"] == "hello"
    assert template.prompt["1"]["inputs"]["value"] == ""  # the template itself is not changed
    with pytest.raises(TemplateError, match="No slot named"):
        template.fill({"idee": "typo"})
    with pytest.raises(TemplateError, match="not in the prompt"):
        Template({}, {"idea": (("9", "value"),)}).fill({"idea": "x"})


def test_a_value_goes_to_every_node_of_its_slot_and_a_missing_picture_takes_its_node_out():
    prompt = {"1": {"class_type": "LoadImage", "inputs": {"image": "a.png"}}, "2": {"class_type": "LoadImage", "inputs": {"image": "b.png"}},
              "3": {"class_type": "Batch", "inputs": {"image0": ["1", 0], "image1": ["2", 0], "seed": 1}}, "4": {"class_type": "Noise", "inputs": {"seed": 1}}}
    template = Template(prompt, {"ref1": (("1", "image"),), "ref2": (("2", "image"),), "seed": (("3", "seed"), ("4", "seed"))})
    filled = template.fill({"seed": 9}, absent=("ref2",))
    assert filled["3"]["inputs"] == {"image0": ["1", 0], "seed": 9} and filled["4"]["inputs"]["seed"] == 9  # both seeds, and the input that was wired to the removed node is gone
    assert "2" not in filled and "2" in template.prompt  # the template keeps its node
    with pytest.raises(TemplateError, match="No slot named"):
        template.fill({}, absent=("ref9",))


def test_the_nodes_that_were_only_fed_by_a_missing_video_go_with_it():
    prompt = {"1": {"class_type": "LoadVideo", "inputs": {"file": "v.mp4"}}, "2": {"class_type": "Frames", "inputs": {"video": ["1", 0]}}, "3": {"class_type": "Sample", "inputs": {"frames": ["2", 0]}},
              "4": {"class_type": "H3", "inputs": {"prompt": "p", "model": ["6", 0], "ref_video": ["2", 0], "sample": ["3", 0]}},
              "5": {"class_type": "Other", "inputs": {"a": ["4", 0], "b": ["3", 0]}}, "6": {"class_type": "Model", "inputs": {}}}
    filled = Template(prompt, {"ref_video": (("1", "file"),)}).fill({}, absent=("ref_video",))
    assert sorted(filled) == ["4", "5", "6"]  # the frames and their sample went; H3 stays (it has a model), with the inputs that were wired to them taken out
    assert filled["4"]["inputs"] == {"prompt": "p", "model": ["6", 0]} and filled["5"]["inputs"] == {"a": ["4", 0]}


def test_a_mode_whose_workflows_are_not_exported_says_how_to_export_them(tmp_path):
    with pytest.raises(TemplateError, match="export_templates"):
        load_templates(tmp_path, "remix")


# ---- the interface's API with the simulated runner -----------------------------------------------------------------

def test_a_job_runs_through_its_stages_and_the_events_end_with_the_result(tmp_path):
    with TestClient(create_app(_settings(tmp_path), MockRunner(pace=0.03))) as client:  # the context keeps one event loop alive: the job runs in the background of the requests
        _a_job_runs(client)


def _a_job_runs(client):
    upload = client.post("/api/uploads", files={"file": ("clip.mp4", b"fake", "video/mp4")}).json()
    assert upload["kind"] == "video" and client.get(upload["url"]).content == b"fake"
    job = client.post("/api/jobs", json={"mode": "remix", "source": upload["id"], "settings": {"duration": 14}}).json()
    states = [json.loads(line[6:]) for line in client.get(f"/api/jobs/{job['id']}/events").text.splitlines() if line.startswith("data: ")]
    assert states[-1]["status"] == "succeeded" and states[-1]["progress"] == 1.0 and states[-1]["stage"] == "done"
    assert len(states) >= 4 and {s["stage"] for s in states} >= {"shots", "done"}  # the interface follows the job as it moves
    assert len(states[-1]["shots"]) == 7 and all(s["done"] for s in states[-1]["shots"])
    assert sorted(s["progress"] for s in states) == [s["progress"] for s in states]  # never backwards


def test_the_api_refuses_what_cannot_run(tmp_path):
    client = TestClient(create_app(_settings(tmp_path), MockRunner(pace=0)))
    assert client.post("/api/jobs", json={"mode": "remix"}).status_code == 422  # the template of a remix is its video
    assert client.post("/api/jobs", json={"mode": "text", "refs": ["nope"]}).status_code == 422
    assert client.post("/api/uploads", files={"file": ("a.txt", b"x", "text/plain")}).status_code == 415
    assert client.get("/api/jobs/unknown").status_code == 404
    assert client.get("/api/jobs/unknown/video").status_code == 404


async def test_a_job_can_be_cancelled(tmp_path):
    app = create_app(_settings(tmp_path), MockRunner(pace=5))
    job = Job(JobRequest(mode="text"))
    job.task = asyncio.create_task(MockRunner(pace=5).run(job))
    await asyncio.sleep(0.05)
    job.task.cancel()
    await asyncio.gather(job.task, return_exceptions=True)
    assert job.state.status == "cancelled" and app is not None


# ---- the real runner against a fake client --------------------------------------------------------------------------

class FakeHandle:
    id = "test-sdk-handle"
    def __init__(self, client, prompt):
        self.client, self.prompt = client, prompt

    async def events(self):
        yield StatusChange(status="running")
        yield Progress(value=0.5, nodes_done=1, nodes_total=2, current_node="7", step=5, steps=10)
        yield StatusChange(status="succeeded")

    async def refresh(self):
        self.refreshed = True

    async def result(self):
        return self

    async def cancel(self):
        self.client.cancelled = True

    async def wait(self, timeout=None):
        return self

    def get_outputs(self, node):
        return [FakeOutput()] if getattr(self, "refreshed", False) else []  # like the SDK: nothing before a refresh


class FakeOutput:
    async def to_file(self, path):  # a coroutine, like the one of the SDK: a call that is not awaited writes nothing
        subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=red:s=64x64:r=24:d=0.25','-c:v','libx264','-pix_fmt','yuv420p',str(path)],check=True)


class FakeWorkflow:
    def __init__(self, prompt):
        self.prompt, self.inputs = prompt, {}

    def set_input(self, node, field, value):
        self.inputs[(node, field)] = value


class FakeClient:
    """Records every prompt it is given; the plan writes the project file that Save Project Info writes."""

    def __init__(self, project_file: Path):
        self.submitted, self.project_file, self.closed = [], project_file, False
        self.workflows = type("W", (), {"from_json": staticmethod(FakeWorkflow)})()
        self.assets = type("A", (), {"from_file": staticmethod(lambda path: f"asset:{Path(path).name}")})()

    async def submit(self, workflow):
        self.submitted.append(workflow)
        if len(self.submitted) == 1:
            self.project_file.parent.mkdir(parents=True, exist_ok=True)
            self.project_file.write_text(json.dumps({"project_id": "p_0123456789ab", "shots": [{"id": "SHOT_001", "start": 0, "duration": 1.5, "prompt": "a"}, {"id": "SHOT_002", "start": 1.5, "duration": 2, "prompt": "b"}]}))
        return FakeHandle(self, workflow)

    async def aclose(self):
        self.closed = True


def _templates(directory: Path):
    folder = directory / "text"
    folder.mkdir(parents=True)
    node = lambda inputs: {"1": {"class_type": "Fake", "inputs": inputs}}  # noqa: E731
    for phase, inputs in (("stage1", {"idea": "", "image": ""}), ("shot", {"shot_id": "", "project": ""}), ("final", {"project": "", "path": ""})):
        (folder / f"{phase}.api.json").write_text(json.dumps(node(inputs)))
    (folder / "slots.json").write_text(json.dumps({"stage1": {"idea": [["1", "idea"]], "ref1": [["1", "image"]], "job_name": [["1", "idea2"]]}, "shot": {"shot_id": [["1", "shot_id"]], "project_id": [["1", "project"]]},
                                                     "final": {"project_id": [["1", "project"]], "save": [["1", "path"]]}}))


async def test_the_plan_then_one_prompt_per_shot_then_the_edit(tmp_path):
    _templates(tmp_path / "workflows")
    settings = _settings(tmp_path, mock=False)
    picture = tmp_path / "ref.png"
    picture.write_bytes(b"png")
    request = JobRequest(mode="text", settings={"prompt": "a fashion film"}, refs=["r1"])  # the same brief reaches every supported request alias
    job = Job(request)
    client = FakeClient(settings.output_dir / "MajoorVideoTools" / "_jobs" / f"{job.id}.json")
    await ComfyRunner(settings, {"r1": picture}, lambda: client).run(job)
    assert job.state.status == "succeeded", job.state.error
    prompts = [w.prompt["1"]["inputs"] for w in client.submitted]
    assert [p.get("shot_id") for p in prompts] == [None, "SHOT_001", "SHOT_002", None]  # plan, two shots, the edit
    assert prompts[0].get("idea") == "a fashion film" and client.submitted[0].inputs == {("1", "image"): "asset:ref.png"}  # a file goes through an asset, not a path
    assert prompts[1]["project"] == prompts[3]["project"] == "p_0123456789ab"  # the edit is made from the project of the plan
    assert [s.done for s in job.state.shots] == [True, True] and job.state.progress == 1.0 and job.state.output_url
    assert (settings.workspace / "jobs" / f"{job.id}.mp4").stat().st_size > 0 and client.closed


async def test_a_missing_template_ends_the_job_with_a_message_and_closes_the_client(tmp_path):
    settings = _settings(tmp_path, mock=False)
    job = Job(JobRequest(mode="music"))
    client = FakeClient(tmp_path / "unused.json")
    await ComfyRunner(settings, {}, lambda: client).run(job)
    assert job.state.status == "failed" and "not exported yet" in job.state.error and client.closed


def test_the_progress_of_a_job_never_goes_back():
    job = Job(JobRequest(mode="text"))
    job.update(progress=0.4)
    job.update(progress=0.3, stage="shots")
    assert job.state.progress == 0.4 and job.state.stage == "shots"


def _finished_job(client):
    upload = client.post("/api/uploads", files={"file": ("clip.mp4", b"fake", "video/mp4")}).json()
    job = client.post("/api/jobs", json={"mode": "remix", "source": upload["id"], "settings": {"duration": 14}}).json()
    client.get(f"/api/jobs/{job['id']}/events").text  # reading the stream to its end waits for the job
    return job["id"]


def test_a_shot_is_made_again_with_its_new_prompt_and_a_locked_shot_is_kept(tmp_path):
    with TestClient(create_app(_settings(tmp_path), MockRunner(pace=0.01))) as client:
        job = _finished_job(client)
        assert client.patch(f"/api/jobs/{job}/shots/SHOT_002", json={"locked": True}).json()["shots"][1]["locked"]
        assert client.post(f"/api/jobs/{job}/regenerate", json={"shots": ["SHOT_002"]}).status_code == 409
        assert client.post(f"/api/jobs/{job}/regenerate", json={"shots": ["SHOT_099"]}).status_code == 422
        again = client.post(f"/api/jobs/{job}/regenerate", json={"shots": ["SHOT_001"], "prompts": {"SHOT_001": "a red car", "SHOT_003": "ignored"}})
        assert again.status_code == 200
        client.get(f"/api/jobs/{job}/events").text
        shots = client.get(f"/api/jobs/{job}").json()["shots"]
        assert (shots[0]["prompt"], shots[0]["takes"], shots[0]["version"]) == ("a red car", 2, 2)
        assert shots[2]["prompt"] == "Shot 3" and shots[2]["takes"] == 1


def test_the_edit_is_made_again_with_another_style_and_the_shots_stay_as_they_are(tmp_path):
    with TestClient(create_app(_settings(tmp_path), MockRunner(pace=0.01))) as client:
        job = _finished_job(client)
        again = client.post(f"/api/jobs/{job}/re-edit", json={"effects": False, "duck": 0.7})
        assert again.status_code == 200
        client.get(f"/api/jobs/{job}/events").text
        state = client.get(f"/api/jobs/{job}").json()
        assert state["status"] == "succeeded" and (state["style"]["effects"], state["style"]["duck"], state["style"]["text"]) == (False, 0.7, False)
        assert all(s["takes"] == 1 for s in state["shots"])
        assert client.post(f"/api/jobs/{job}/re-edit", json={"duck": 3}).status_code == 422


async def test_the_style_goes_to_the_assembly_and_only_the_last_prompt_runs(tmp_path):
    _templates(tmp_path / "workflows")
    folder = tmp_path / "workflows" / "text"
    slots = json.loads((folder / "slots.json").read_text())
    slots["final"]["edit_sub_cuts"] = [["1", "sub_cuts"]]
    slots["final"]["edit_duck"] = [["1", "duck_music"]]
    (folder / "slots.json").write_text(json.dumps(slots))
    settings = _settings(tmp_path, mock=False)
    job = Job(JobRequest(mode="text"))
    job.update(project_id="p_0123456789ab", shots=[Shot(id="SHOT_001", start=0, duration=1, done=True, takes=1)])
    client = FakeClient(tmp_path / "unused.json")
    await ComfyRunner(settings, {}, lambda: client).re_edit(job, EditStyle(sub_cuts=False, duck=0.7))
    assert job.state.status == "succeeded", job.state.error
    assert len(client.submitted) == 1  # no plan, no shot
    inputs = client.submitted[0].prompt["1"]["inputs"]
    assert (inputs["sub_cuts"], inputs["duck_music"], inputs["project"]) == (False, 0.7, "p_0123456789ab")
    assert job.state.style.duck == 0.7 and job.state.output_url.endswith("v=1")


async def test_a_prompt_that_fails_says_which_node_and_why(tmp_path):
    _templates(tmp_path / "workflows")
    settings = _settings(tmp_path, mock=False)
    job = Job(JobRequest(mode="text"))
    client = FakeClient(settings.output_dir / "MajoorVideoTools" / "_jobs" / f"{job.id}.json")
    error = type("E", (), {"message": "SHOT_001: still the template placeholder", "node_id": "131", "code": "x"})()

    async def result():
        raise JobFailed("failed", error=error)

    submit = client.submit

    async def failing(workflow):
        handle = await submit(workflow)
        handle.result = result
        return handle

    client.submit = failing
    await ComfyRunner(settings, {}, lambda: client).run(job)
    assert job.state.status == "failed" and job.state.error == "SHOT_001: still the template placeholder (node 131)"


async def test_cancelling_a_job_cancels_the_prompt_on_the_gpu(tmp_path):
    _templates(tmp_path / "workflows")
    settings = _settings(tmp_path, mock=False)
    job = Job(JobRequest(mode="text"))
    client = FakeClient(settings.output_dir / "MajoorVideoTools" / "_jobs" / f"{job.id}.json")
    submit = client.submit

    async def slow(workflow):
        handle = await submit(workflow)

        async def events():
            yield Progress(value=0.1, nodes_done=0, nodes_total=2, current_node="1", step=1, steps=10)
            await asyncio.sleep(30)

        handle.events = events
        return handle

    client.submit = slow
    task = asyncio.create_task(ComfyRunner(settings, {}, lambda: client).run(job))
    await asyncio.sleep(0.2)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert client.cancelled and job.state.status == "cancelled"


def test_the_jobs_come_back_after_the_server_restarts(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings, MockRunner(pace=0.01))) as client:
        job = _finished_job(client)
    with TestClient(create_app(settings, MockRunner(pace=0.01))) as client:
        state = client.get(f"/api/jobs/{job}").json()
        assert state["status"] == "succeeded" and len(state["shots"]) == 7 and client.get("/api/jobs").json()[0]["id"] == job


async def test_cancelling_while_the_prompt_is_being_sent_still_cancels_it(tmp_path):
    _templates(tmp_path / "workflows")
    settings = _settings(tmp_path, mock=False)
    job = Job(JobRequest(mode="text"))
    client = FakeClient(settings.output_dir / "MajoorVideoTools" / "_jobs" / f"{job.id}.json")
    submit = client.submit

    async def slow(workflow):
        await asyncio.sleep(0.3)
        return await submit(workflow)

    client.submit = slow
    task = asyncio.create_task(ComfyRunner(settings, {}, lambda: client).run(job))
    await asyncio.sleep(0.1)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert client.cancelled and job.state.status == "cancelled"


def test_a_project_gives_back_its_settings_and_its_files(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings, MockRunner(pace=0.01))) as client:
        clip = client.post("/api/uploads", files={"file": ("my clip.mp4", b"fake", "video/mp4")}).json()
        picture = client.post("/api/uploads", files={"file": ("me.png", b"png", "image/png")}).json()
        job = client.post("/api/jobs", json={"mode": "remix", "source": clip["id"], "refs": [picture["id"]], "settings": {"prompt": "hello", "duration": 12}}).json()["id"]
        client.get(f"/api/jobs/{job}/events").text
    with TestClient(create_app(settings, MockRunner(pace=0.01))) as client:
        made = client.get(f"/api/jobs/{job}/inputs").json()
        assert made["mode"] == "remix" and made["settings"]["prompt"] == "hello" and made["settings"]["duration"] == 12
        assert (made["source"]["name"], made["source"]["kind"], made["refs"][0]["kind"], made["voice"]) == ("my clip.mp4", "video", "image", None)
        assert client.get(made["refs"][0]["url"]).content == b"png"


def _project_on_disk(settings, project_id="p_0123456789ab"):
    folder = settings.output_dir / "MajoorVideoTools" / project_id
    (folder / "generated").mkdir(parents=True)
    (folder / "generated" / "SHOT_001_take_001.mp4").write_bytes(b"one")
    (folder / "generated" / "SHOT_001_take_002.mp4").write_bytes(b"two")
    (folder / 'sources').mkdir()
    (folder / 'sources/source.mp4').write_bytes(b'source')
    revisions = [{"revision_id": "original", "media_range": {"start_frame": 0}, "media_ref": "sources/source.mp4"},
                 {"revision_id": "take_001", "media_range": None, "media_ref": "generated/SHOT_001_take_001.mp4"},
                 {"revision_id": "take_002", "media_range": None, "media_ref": "generated/SHOT_001_take_002.mp4"}]
    (folder / "manifest.json").write_text(json.dumps({"shots": [{"shot_id": "SHOT_001", "revisions": revisions, "active_revision_id": "take_002"}]}))
    return folder


def test_the_takes_of_a_shot_can_be_listed_played_and_chosen(tmp_path):
    settings = _settings(tmp_path)
    folder = _project_on_disk(settings)
    with TestClient(create_app(settings, MockRunner(pace=0.01))) as client:
        job = _finished_job(client)
        assert client.get(f"/api/jobs/{job}/shots/SHOT_001/takes").status_code == 404  # the simulation has no project: the route says so
    runner = MockRunner(pace=0.01)
    original = runner.run

    async def with_project(job):
        await original(job)
        job.update(project_id="p_0123456789ab")

    runner.run = with_project
    with TestClient(create_app(settings, runner)) as client:
        job = _finished_job(client)
        listed = client.get(f"/api/jobs/{job}/shots/SHOT_001/takes").json()
        assert [(t["id"], t["active"]) for t in listed] == [("take_001", False), ("take_002", True)]
        assert client.get(listed[0]["url"]).content == b"one"
        assert client.get(f"/api/jobs/{job}/shots/SHOT_001/takes/original/video").status_code == 404
        chosen = client.post(f"/api/jobs/{job}/shots/SHOT_001/active", json={"take": "take_001"}).json()
        assert [t["active"] for t in chosen] == [True, False]
        assert json.loads((folder / "manifest.json").read_text())["shots"][0]["active_revision_id"] == "take_001"
        assert client.post(f"/api/jobs/{job}/shots/SHOT_001/active", json={"take": "original"}).status_code == 404
        bundle = client.get(f"/api/jobs/{job}/export")
        assert bundle.status_code == 200 and bundle.content[:2] == b"PK"


def test_the_timeline_gives_the_tempo_the_cuts_and_the_effects_of_the_plan(tmp_path):
    settings = _settings(tmp_path)
    folder = _project_on_disk(settings)
    manifest = json.loads((folder / "manifest.json").read_text())
    manifest["detection"] = {"warnings": ["Tempo 120.1 BPM (detected), cuts snapped to the half_beat"]}
    manifest["source"] = {"fps_num": 24, "fps_den": 1}
    manifest["shots"][0].update({"timeline_index": 0, "target_duration_seconds": 1.0, "plan": {"fx": {"text": "HI", "sub_cuts": [
        {"frames": 6, "zoom": [1.4, 1.4]}, {"frames": 6, "zoom": [1, 1], "flip": True, "transition": {"type": "glitch", "frames": 6}}, {"frames": 12, "speed": 0.5}]}}})
    (folder / "manifest.json").write_text(json.dumps(manifest))
    runner = MockRunner(pace=0.01)
    original = runner.run

    async def with_project(job):
        await original(job)
        job.update(project_id="p_0123456789ab")

    runner.run = with_project
    with TestClient(create_app(settings, runner)) as client:
        job = _finished_job(client)
        info = client.get(f"/api/jobs/{job}/timeline").json()
        assert info["bpm"] == 120.1
        assert info["shots"][0]["cuts"] == [0.25, 0.5]  # the sub-cuts are 6, 6 and 12 frames of 24 per second
        assert info["shots"][0]["effects"] == ["flip", "speed", "text", "transition:glitch", "zoom"]
        assert client.get(f"/api/jobs/{job}/waveform").status_code == 404  # the simulation made no video


def test_a_project_can_be_renamed_pinned_listed_by_date_and_deleted(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings, MockRunner(pace=0.01))) as client:
        first = _finished_job(client)
        second = _finished_job(client)
        assert [j["id"] for j in client.get("/api/jobs").json()] == [second, first]  # the last one first
        renamed = client.patch(f"/api/jobs/{first}", json={"title": "My ad", "pinned": True}).json()
        assert (renamed["title"], renamed["pinned"]) == ("My ad", True)
        assert client.delete(f"/api/jobs/{second}").status_code == 200
        assert client.get(f"/api/jobs/{second}").status_code == 404
    with TestClient(create_app(settings, MockRunner(pace=0.01))) as client:  # kept after a restart, and the deleted one stays deleted
        kept = client.get("/api/jobs").json()
        assert [(j["id"], j["title"], j["pinned"]) for j in kept] == [(first, "My ad", True)]


def test_deleting_a_project_with_its_folder_and_freeing_the_takes_that_are_not_used(tmp_path):
    settings = _settings(tmp_path)
    folder = _project_on_disk(settings)
    runner = MockRunner(pace=0.01)
    original = runner.run

    async def with_project(job):
        await original(job)
        job.update(project_id="p_0123456789ab")

    runner.run = with_project
    with TestClient(create_app(settings, runner)) as client:
        job = _finished_job(client)
        sizes = client.get("/api/jobs/sizes").json()
        assert sizes[job] >= 6  # the two takes
        freed = client.post(f"/api/jobs/{job}/free").json()["freed"]
        assert freed == 3 and not (folder / "generated" / "SHOT_001_take_001.mp4").exists() and (folder / "generated" / "SHOT_001_take_002.mp4").exists()
        assert [t["id"] for t in client.get(f"/api/jobs/{job}/shots/SHOT_001/takes").json()] == ["take_002"]
        assert client.delete(f"/api/jobs/{job}?project=true").status_code == 200
        assert not folder.exists()


def test_the_presets_saved_here_are_listed_after_the_ones_of_the_app_and_can_be_deleted(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings, MockRunner(pace=0.01))) as client:
        builtin = client.get('/api/presets').json()
        saved = client.post("/api/presets", json={"name": "My Neon Ad!", "mode": "text", "prompt": "a fox", "settings": {"duration": 20}}).json()
        assert saved["id"] == "user-my-neon-ad" and saved["user"]
        listed = client.get("/api/presets").json()
        assert listed[-1]["id"] == "user-my-neon-ad" and listed[-1]["settings"] == {"duration": 20} and listed[:-1] == builtin
        assert client.delete("/api/presets/katana-remix").status_code == 404  # the presets of the app stay
        assert client.delete("/api/presets/user-my-neon-ad").status_code == 200
        assert client.delete("/api/presets/user-..%2F..%2Fx").status_code in (404, 405, 422)
        assert all(not p["user"] for p in client.get("/api/presets").json())


def test_the_picture_of_a_preset_is_served_from_the_media_folder_only(tmp_path):
    settings = _settings(tmp_path)
    media = settings.workspace / "presets" / "media"
    media.mkdir(parents=True)
    (media / "loop.gif").write_bytes(b"GIF89a")
    (tmp_path / "secret.txt").write_text("no")
    with TestClient(create_app(settings, MockRunner(pace=0.01))) as client:
        assert client.get("/api/presets/media/loop.gif").content == b"GIF89a"
        assert client.get("/api/presets/media/missing.gif").status_code == 404
        assert client.get("/api/presets/media/..%2F..%2Fsecret.txt").status_code in (404, 405)


def test_the_edit_controls_show_what_the_final_prompt_applies():
    from backend.templates import applied_style, load_templates

    templates = Path(__file__).resolve().parents[1] / "workflows"
    remix = applied_style(load_templates(templates, "remix")["final"], {})
    text = applied_style(load_templates(templates, "text")["final"], {})
    assert remix["duck"] == 0.0 and remix["auto_sfx"] is False and text["shot_volume"] == 0.8
    assert applied_style(load_templates(templates, "text")["final"], {"edit_duck": 0.2, "edit_effects": False}) | {} == {**text, "duck": 0.2, "effects": False}
