from backend.config import ROOT
from backend.runner import OPTIONAL_MUSIC_NODES, _is_optional_music_failure, _without_nodes
from backend.templates import load_templates


def test_text_plan_keeps_its_visual_project_sink_when_optional_music_is_removed():
    templates = load_templates(ROOT / 'workflows', 'text')
    fallback = _without_nodes(templates['stage1'], OPTIONAL_MUSIC_NODES)
    assert fallback is not None
    classes = {node['class_type'] for node in fallback.prompt.values()}
    assert 'MajoorSaveProjectInfo' in classes
    assert 'MajoorSaveProjectMusic' not in classes
    assert not classes.intersection(OPTIONAL_MUSIC_NODES)
    assert all(node in fallback.prompt for targets in fallback.slots.values() for node, _ in targets)


def test_text_final_graph_does_not_require_a_missing_optional_music_file():
    templates = load_templates(ROOT / 'workflows', 'text')
    fallback = _without_nodes(templates['final'], {'MajoorLoadProjectMusic'})
    assert fallback is not None
    classes = {node['class_type'] for node in fallback.prompt.values()}
    assert 'SaveVideo' in classes
    assert 'MajoorLoadProjectMusic' not in classes


def test_yue2_failure_messages_trigger_optional_music_recovery_only_for_music_nodes():
    assert _is_optional_music_failure(RuntimeError('YuE2 needs a musical direction'))
    assert _is_optional_music_failure(RuntimeError('voices have different measure counts (MajoorYuE2Score)'))
    assert not _is_optional_music_failure(RuntimeError('planner returned an invalid shot list'))
