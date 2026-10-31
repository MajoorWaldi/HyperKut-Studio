from pathlib import Path

import pytest
from backend.jobs import Job
from backend.models import JobRequest, Settings
from backend.runner import ComfyRunner
from backend.templates import load_templates
from test_backend import _settings

ROOT = Path(__file__).resolve().parents[1]


def _fill(tmp_path, casting):
    request = JobRequest(mode='music', settings={'prompt': 'Six monsters rap in six places', 'casting': casting})
    runner = ComfyRunner(_settings(tmp_path), {})
    job = Job(request)
    template = load_templates(ROOT / 'workflows', 'music')['stage1']
    return template.fill({}, tuple(n for n in runner._absent(job) if n in template.slots))


def test_casting_is_off_by_default_and_unknown_modes_are_refused():
    assert Settings().casting is False
    assert Settings(music_edit_mode='phrases').music_edit_mode == 'phrases'
    with pytest.raises(ValueError):
        Settings(music_edit_mode='nope')


def test_casting_off_drops_the_planner_and_keeps_the_saved_shot_list(tmp_path):
    graph = _fill(tmp_path, False)
    assert not {'85', '86', '88', '89'} & set(graph)
    assert graph['87']['class_type'] == 'MajoorApplyCasting' and 'casting_json' not in graph['87']['inputs']
    assert graph['p1']['inputs']['shot_list'] == ['87', 0]


def test_casting_on_feeds_the_planner_answer_to_the_cast(tmp_path):
    graph = _fill(tmp_path, True)
    assert graph['85']['inputs']['skill'] == 'casting_planner'
    assert graph['85']['inputs']['brief'] == ['89', 0] and graph['89']['inputs']['string_b'] == ['88', 2] and graph['88']['class_type'] == 'MajoorMusicWords'
    assert graph['87']['inputs']['casting_json'] == ['86', 0] and graph['87']['inputs']['shot_list'] == ['84', 0]


def test_finishing_accepts_templates_and_the_new_layer_kinds():
    import json
    from backend.unified_motion import finishing_layers, needs_subject_mask, validate_finishing
    rows = [{"template": "end_card", "start": 5, "end": 8, "title": "NIGHT"}, {"template": "particles", "start": 0, "end": 4, "count": 30},
            {"template": "sticker", "start": 0, "end": 2, "name": "burst"}, {"template": "split_diagonal", "start": 1, "end": 2}]
    validate_finishing({"motion_layers": json.dumps(rows)}, 9)
    assert not needs_subject_mask(json.dumps(rows))
    assert needs_subject_mask(json.dumps([{"template": "title_behind", "start": 0, "end": 2, "title": "x"}]))
    assert needs_subject_mask(json.dumps([{"template": "cutout_echo", "start": 0, "end": 2}]))
    out = json.loads(finishing_layers({"shots": []}, [], json.dumps(rows)))
    assert [r["type"] for r in out] == ["text", "effect", "lottie", "effect"] and out[1]["kind"] == "particles"
    with pytest.raises(ValueError):
        validate_finishing({"motion_layers": json.dumps([{"template": "nope"}])}, 9)
