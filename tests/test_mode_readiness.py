import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.runner import MockRunner
from backend.server import create_app
from backend.templates import Template, combo_options, graph_readiness, reachable_graph
from backend.remote_graph import validate_remote_graph


def node(kind, **inputs):
    return {"class_type": kind, "inputs": inputs}


@pytest.mark.parametrize("spec", [
    [["available.safetensors"]],
    [["available.safetensors"], {}],
    ["COMBO", {"options": ["available.safetensors"]}],
])
def test_model_enums_share_legacy_and_v3_handling(spec):
    graph = {"model": node("ModelPatchLoader", name="missing.safetensors"),
             "sink": node("SaveVideo", video=["model", 0])}
    schemas = {"SaveVideo": {}, "ModelPatchLoader": {"input": {"required": {"name": spec}}}}
    assert combo_options(spec) == ["available.safetensors"]
    assert graph_readiness(graph, schemas) == ([], ["ModelPatchLoader.name: missing.safetensors"])
    graph["model"]["inputs"]["name"] = "available.safetensors"
    assert graph_readiness(graph, schemas) == ([], [])


def test_only_sink_ancestors_are_required_and_inputs_are_not_mutated():
    graph = {
        "model": node("UNETLoader", unet_name="selected.safetensors"),
        "render": node("Render", model=["model", 0], literal=["not-a-link", "text"]),
        "sink": node("SaveVideo", video=["render", 0]),
        "unused": node("NotInstalled", unet_name="unrelated.safetensors"),
        "mask": node("LoadBackgroundRemovalModel", bg_removal_name="absent.safetensors"),
    }
    original = copy.deepcopy(graph)
    schemas = {"SaveVideo": {}, "Render": {}, "UNETLoader": {
        "input": {"required": {"unet_name": ["COMBO", {"options": ["selected.safetensors"]}]}}}}
    assert set(reachable_graph(graph, schemas)) == {"model", "render", "sink"}
    assert graph_readiness(graph, schemas) == ([], [])
    assert graph == original
    del schemas["UNETLoader"]
    assert graph_readiness(graph, schemas) == (["UNETLoader"], [])
    del schemas["SaveVideo"]
    assert graph_readiness(graph, schemas)[0] == ["SaveVideo", "UNETLoader"]


def test_schema_sink_cycles_and_unknown_enum_are_conservative():
    graph = {"a": node("CustomOutput", value=["b", 0]),
             "b": node("UNETLoader", unet_name="unknown.safetensors", cycle=["a", 0]),
             "dead": node("Dead")}
    schemas = {"CustomOutput": {"output_node": True}, "UNETLoader": {}}
    assert set(reachable_graph(graph, schemas)) == {"a", "b"}
    assert graph_readiness(graph, schemas) == ([], [])
    assert reachable_graph({"fragment": node("Unknown")}, {}) == {"fragment": node("Unknown")}


def test_optional_absence_is_applied_before_model_readiness():
    graph = {"ref": node("ReferenceOnly", image="ref.png"),
             "model": node("UNETLoader", unet_name="available.safetensors"),
             "render": node("Render", image=["ref", 0], model=["model", 0]),
             "sink": node("SaveVideo", video=["render", 0])}
    template = Template(graph, {"ref1": (("ref", "image"),)})
    schemas = {"UNETLoader": {}, "Render": {}, "SaveVideo": {}}
    assert graph_readiness(template.fill({}, absent=("ref1",)), schemas) == ([], [])
    assert graph_readiness(template.fill({}), schemas) == (["ReferenceOnly"], [])


@pytest.mark.parametrize("spec", [[[]], ["COMBO", {"options": []}]])
def test_empty_model_enum_means_model_is_missing(spec):
    assert graph_readiness({"load": node("UNETLoader", unet_name="missing")}, {
        "UNETLoader": {"input": {"optional": {"unet_name": spec}}}
    }) == ([], ["UNETLoader.unet_name: missing"])


def test_remote_validation_ignores_dead_models_but_rejects_reachable_classes_and_patch():
    schemas = {kind: {"output": []} for kind in (
        "HyperKutWorkspace", "HyperKutSnapshotImport", "HyperKutSnapshotExport", "HyperKutWorkspaceRelease")}
    schemas.update({"SaveVideo": {}, "ModelPatchLoader": {
        "input": {"required": {"name": ["COMBO", {"options": ["available"]}]}}}})
    graph = {"patch": node("ModelPatchLoader", name="available"),
             "sink": node("SaveVideo", video=["patch", 0]), "dead": node("NotInstalled")}
    validate_remote_graph(graph, schemas)
    graph["patch"]["inputs"]["name"] = "missing"
    with pytest.raises(ValueError, match="ModelPatchLoader.name: missing"):
        validate_remote_graph(graph, schemas)
    graph["sink"]["inputs"]["video"] = ["dead", 0]
    with pytest.raises(ValueError, match="Remote nodes missing.*NotInstalled"):
        validate_remote_graph(graph, schemas)


def test_health_checks_selected_filled_phases_only(tmp_path, monkeypatch):
    workflows = tmp_path / "workflows"
    graph = {"model": node("UNETLoader", unet_name="available"),
             "reference": node("ReferenceOnly", image="ref.png"),
             "render": node("Render", model=["model", 0], image=["reference", 0]),
             "sink": node("SaveVideo", video=["render", 0]),
             "unused": node("NotInstalled", unet_name="unrelated")}
    for mode in ("remix", "text", "music"):
        folder = workflows / mode
        folder.mkdir(parents=True)
        document = copy.deepcopy(graph)
        if mode == "text":
            document["model"] = node("CheckpointLoaderSimple", ckpt_name="text-only")
        for phase in ("stage1", "shot", "final"):
            (folder / f"{phase}.api.json").write_text(json.dumps(document), encoding="utf-8")
        (folder / "local.api.json").write_text(json.dumps({"local": node("LocalOnly")}), encoding="utf-8")
        (folder / "slots.json").write_text(json.dumps({
            phase: {"ref1": [["reference", "image"]]} for phase in ("stage1", "shot", "final")
        }), encoding="utf-8")
    schemas = {"SaveVideo": {}, "Render": {},
               "UNETLoader": {"input": {"required": {"unet_name": [["available"]]}}},
               "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": ["COMBO", {"options": []}]}}}}

    class Probe:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url):
            data = schemas if url.endswith("/object_info") else {"status": "healthy"}
            return httpx.Response(200, json=data, request=httpx.Request("GET", url))

    monkeypatch.setattr("backend.server.httpx.AsyncClient", Probe)
    settings = Settings("http://comfy", "http://proxy", tmp_path / "output", tmp_path / "workspace", workflows, False)
    with TestClient(create_app(settings, MockRunner())) as client:
        for mode in ("remix", "music"):
            result = client.get(f"/api/health?mode={mode}").json()
            assert result["mode"] == mode and result["videotools"]
            assert result["missing_nodes"] == result["missing_models"] == []
        assert client.get("/api/health").json()["mode"] == "remix"
        result = client.get("/api/health?mode=text").json()
        assert result["missing_models"] == ["CheckpointLoaderSimple.ckpt_name: text-only"]
        result = client.get("/api/health?mode=music&refs=1").json()
        assert result["missing_nodes"] == ["ReferenceOnly"]
        assert not result["videotools"]
        assert client.get("/api/health?mode=other").status_code == 422
        assert client.get("/api/health?mode=text&refs=6").status_code == 422
