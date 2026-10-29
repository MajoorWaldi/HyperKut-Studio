import pytest
from pydantic import ValidationError

from backend.direction import apply_plan_contract
from backend.models import Settings


def graph():
    return {
        "guide": {"class_type": "MajoorCreateTimeline", "inputs": {"source": "music"}},
        "llm": {"class_type": "TextGenerate", "inputs": {}},
        "final": {"class_type": "MajoorCreateTimeline", "inputs": {
            "source": "json", "source.plan_json": ["llm", 0], "skeleton_json": ["guide", 1], "source.cut_snap": "half_beat", "music": ["audio", 0]}},
        "planner": {"class_type": "MajoorEditSkills", "inputs": {"skill": "timeline_planner"}},
    }


@pytest.mark.parametrize("mode", ["adaptive", "random", "regular", "free"])
def test_actual_final_graph_routes_every_control(mode):
    settings = Settings(music_edit_mode=mode, seed=123, music_cut_sync=.6, music_cut_variation=.3, cut_density="high", cut_every="bar", art_direction={"mood": "calm"})
    g = graph()
    apply_plan_contract(g, settings)
    final = g["final"]["inputs"]
    assert final["music_edit_mode"] == mode
    assert final["music_cut_sync"] == .6
    assert final["music_cut_variation"] == .3
    assert final["music_cut_density"] == "high"
    assert final["music_cut_every"] == "bar"
    assert final["music_cut_seed"] == 123
    assert final["music_cut_mood"] == "calm"
    assert final["source.cut_snap"] == "off"
    assert final["source.duration"] == 15
    assert "skeleton_json" not in final
    assert final["source.plan_json"] == ["llm", 0]
    assert "MUSIC CUT POLICY" in g["planner"]["inputs"]["extra_instructions"]


def test_old_settings_keep_old_graph_and_roundtrip_new_controls():
    g = graph()
    apply_plan_contract(g, Settings())
    assert "music_edit_mode" not in g["final"]["inputs"]
    assert g["final"]["inputs"]["source.cut_snap"] == "half_beat"
    assert "final_edit_density" in g
    settings = Settings(music_edit_mode="random", music_cut_variation=.7, music_cut_sync=.4)
    assert Settings.model_validate_json(settings.model_dump_json()) == settings
    assert Settings.model_validate({}).music_edit_mode == "legacy"


def test_a_graph_without_music_does_not_get_musical_retiming():
    g = graph()
    del g["guide"]
    g["final"]["inputs"].pop("skeleton_json")
    g["final"]["inputs"].pop("music")
    apply_plan_contract(g, Settings(music_edit_mode="adaptive"))
    assert "music_edit_mode" not in g["final"]["inputs"]
    assert "MUSIC CUT POLICY" not in g["planner"]["inputs"]["extra_instructions"]


@pytest.mark.parametrize("changes", [{"music_edit_mode": "bad"}, {"music_cut_sync": -1}, {"music_cut_variation": 1.1}])
def test_settings_validate_boundaries(changes):
    with pytest.raises(ValidationError):
        Settings(**changes)


def test_exported_music_template_gets_the_final_policy_not_a_fixed_take_grid():
    from backend.config import ROOT
    from backend.templates import load_templates
    template = load_templates(ROOT / "workflows", "music")["stage1"]
    g = template.fill({"planning_instructions": "User planning instructions"})
    apply_plan_contract(g, Settings(music_edit_mode="adaptive"))
    assert g["78"]["inputs"]["rhythm_reference_only"] is True
    assert g["84"]["inputs"]["music_edit_mode"] == "adaptive"
    assert g["84"]["inputs"]["source.cut_snap"] == "off"
    assert "skeleton_json" not in g["84"]["inputs"]
    assert g["84"]["inputs"]["source.plan_json"] == ["83", 0]
    assert "music_edit_mode" not in template.prompt["84"]["inputs"]


def test_exported_text_template_uses_adaptive_instead_of_fixed_snap_and_burst():
    from backend.config import ROOT
    from backend.templates import load_templates
    template = load_templates(ROOT / "workflows", "text")["stage1"]
    g = template.fill({"planning_instructions": "User planning instructions"})
    apply_plan_contract(g, Settings(music_edit_mode="adaptive"), mode="text")
    assert g["84"]["inputs"]["music_edit_mode"] == "adaptive"
    assert g["84"]["inputs"]["source.cut_snap"] == "off"
    assert g["84"]["inputs"]["source.plan_json"] == g["burst"]["inputs"]["plan_json"]
    assert "MUSIC CUT POLICY" in g["82"]["inputs"]["extra_instructions"]


@pytest.mark.parametrize("audio", ["original", "new", "voice"])
def test_remix_adapts_only_the_new_music_final_export(audio):
    from backend.config import ROOT
    from backend.templates import load_templates
    template = load_templates(ROOT / "workflows", "remix")["final"]
    g = template.fill({})
    apply_plan_contract(g, Settings(music_edit_mode="adaptive", audio=audio), mode="remix")
    final = g["123"]["inputs"]
    assert (final.get("music_edit_mode") == "adaptive") is (audio == "new")
    assert final["shot_list"] == template.prompt["123"]["inputs"]["shot_list"]
    assert final["music"] == template.prompt["123"]["inputs"]["music"]


def test_outdated_live_node_is_rejected_before_any_model_submission(tmp_path, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import Mock
    import httpx
    from backend.jobs import Job
    from backend.models import JobRequest
    from backend.runner import ComfyRunner
    from backend.templates import Template
    from test_backend import _settings

    class Probe:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            return httpx.Response(200, json={"MajoorCreateTimeline": {"input": {"optional": {}}}}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Probe())
    from_json = Mock(side_effect=AssertionError("No workflow should be submitted"))
    client = SimpleNamespace(workflows=SimpleNamespace(from_json=from_json))
    job = Job(JobRequest(mode="music", settings={"music_edit_mode": "random"}))
    runner = ComfyRunner(_settings(tmp_path), {})
    with pytest.raises(ValueError, match="Restart ComfyUI"):
        asyncio.run(runner._run(client, job, Template(graph(), {}), {}, "analyze"))
    from_json.assert_not_called()


@pytest.mark.parametrize("mode", ["adaptive", "legacy"])
def test_explicit_dialogue_keeps_narrative_timing_and_enables_safe_assembly(mode):
    g = graph()
    g["assemble"] = {"class_type": "MajoorShotAssemble", "inputs": {}}
    apply_plan_contract(g, Settings(music_edit_mode=mode, audio="voice", dialogue="0-3 s: A complete sentence."))
    assert g["final"]["inputs"]["music_edit_mode"] == "free"
    assert g["assemble"]["inputs"]["preserve_dialogue"] is True
    assert "DIALOGUE SAFETY" in g["planner"]["inputs"]["extra_instructions"]
    assert "free (dialogue protection)" in g["planner"]["inputs"]["extra_instructions"]


def test_old_dialogue_assembler_is_rejected_in_stage_one_before_generation(tmp_path, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import Mock
    import httpx
    from backend.jobs import Job
    from backend.models import JobRequest
    from backend.runner import ComfyRunner
    from backend.templates import Template
    from test_backend import _settings

    class Probe:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            assert url.endswith('/object_info/MajoorShotAssemble')
            return httpx.Response(200, json={"MajoorShotAssemble": {"input": {"optional": {"music_edit_mode": []}}}}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Probe())
    from_json = Mock(side_effect=AssertionError("Generation must not be submitted"))
    client = SimpleNamespace(workflows=SimpleNamespace(from_json=from_json))
    job = Job(JobRequest(mode="text", settings={"audio": "voice"}))
    runner = ComfyRunner(_settings(tmp_path), {})
    with pytest.raises(ValueError, match="independent dialogue"):
        asyncio.run(runner._run(client, job, Template({"llm": {"class_type": "TextGenerate", "inputs": {}}}, {}), {}, "analyze"))
    from_json.assert_not_called()
