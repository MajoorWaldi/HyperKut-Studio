from pathlib import Path
import pytest
from backend.templates import load_templates

@pytest.mark.parametrize("mode", ["text", "music", "remix"])
def test_finishing_without_mask_has_no_background_model_dependency(mode):
    template=load_templates(Path(__file__).parents[1]/"workflows",mode)["final"]
    values={k:v for k,v in {"subject_mask":False,"motion_design":True,"unified_layers":"[{\"type\":\"text\",\"content\":\"TEST\"}]"}.items() if k in template.slots}
    graph=template.fill(values)
    finishing=[n for n in graph.values() if n["class_type"]=="MajoorHyperFrames"]
    assert finishing and all("mask" not in n["inputs"] for n in finishing)
    assert not any(n["class_type"]=="LoadBackgroundRemovalModel" for n in graph.values())

@pytest.mark.parametrize("mode", ["text", "music", "remix"])
def test_requested_mask_keeps_background_model_dependency(mode):
    template=load_templates(Path(__file__).parents[1]/"workflows",mode)["final"]
    graph=template.fill({"subject_mask":True,"motion_design":True})
    assert any(n["class_type"]=="LoadBackgroundRemovalModel" for n in graph.values())
    assert any("mask" in n["inputs"] for n in graph.values() if n["class_type"]=="MajoorHyperFrames")


@pytest.mark.parametrize("mode", ["text", "music", "remix"])
def test_disabled_finishing_also_drops_unused_mask_branch(mode):
    template=load_templates(Path(__file__).parents[1]/"workflows",mode)["final"]
    graph=template.fill({"subject_mask":False,"motion_design":False,"unified_layers":"[]"})
    assert not any(n["class_type"] in ("MajoorHyperFrames","LoadBackgroundRemovalModel") for n in graph.values())
