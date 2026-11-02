from pathlib import Path

import pytest
from backend.jobs import Job
from backend.models import JobRequest, Settings
from backend.runner import ComfyRunner
from backend.templates import load_templates
from test_backend import _settings

ROOT = Path(__file__).resolve().parents[1]


def _fill(tmp_path, casting, mode='music'):
    request = JobRequest(mode=mode, settings={'prompt': 'Six monsters rap in six places', 'casting': casting})
    runner = ComfyRunner(_settings(tmp_path), {})
    job = Job(request)
    template = load_templates(ROOT / 'workflows', mode)['stage1']
    return template.fill({}, tuple(n for n in runner._absent(job) if n in template.slots))


def test_casting_is_off_by_default_and_unknown_modes_are_refused():
    assert Settings().casting is False
    assert Settings(music_edit_mode='phrases').music_edit_mode == 'phrases'
    with pytest.raises(ValueError):
        Settings(music_edit_mode='nope')


def test_casting_off_drops_the_planner_and_keeps_the_saved_shot_list(tmp_path):
    graph = _fill(tmp_path, False)
    assert not {'85', '86', '88', '89', 'T3', 'T4'} & set(graph)
    assert graph['87']['class_type'] == 'MajoorApplyCasting' and 'casting_json' not in graph['87']['inputs']
    assert graph['p1']['inputs']['shot_list'] == ['CV', 0] and graph['CV']['inputs']['shot_list'] == ['87', 0]     # the camera moves come after the casting


def test_casting_on_feeds_the_planner_answer_to_the_cast(tmp_path):
    graph = _fill(tmp_path, True)
    assert graph['85']['inputs']['skill'] == 'casting_planner'
    assert graph['85']['inputs']['brief'] == ['T4', 0] and graph['89']['inputs']['string_b'] == ['88', 2] and graph['88']['class_type'] == 'MajoorMusicWords'
    assert graph['T3']['inputs']['string_a'] == ['89', 0] and graph['T3']['inputs']['string_b'] == ['84', 2]    # the casting reads the times and the subjects of the shots the planner made
    assert graph['T4']['inputs']['string_a'] == ['T3', 0] and graph['T4']['inputs']['string_b'] == ['84', 1]
    assert graph['87']['inputs']['casting_json'] == ['86', 0] and graph['87']['inputs']['shot_list'] == ['84', 0]


def test_the_words_of_the_voice_reach_the_cuts_and_the_planners(tmp_path):
    for casting in (True, False):
        graph = _fill(tmp_path, casting)
        assert graph['T1']['class_type'] == 'MajoorTranscribeVoice' and graph['T1']['inputs']['audio'] == ['70', 0]
        assert graph['78']['inputs']['words_json'] == ['T1', 0] and graph['T2']['inputs']['string_a'] == ['81', 0]
        assert graph['T2']['inputs']['string_b'] == ['T1', 1]
    assert _fill(tmp_path, True)['88']['inputs']['words_json'] == ['T1', 0] and _fill(tmp_path, True)['89']['inputs']['string_a'] == ['ST5', 0]


def test_the_shot_graphs_carry_the_visual_memory_of_the_character():
    import json
    from pathlib import Path
    for mode, first_reference in (("music", "27"), ("text", "28")):
        graph = json.loads((Path(__file__).parents[1] / "workflows" / mode / "shot.api.json").read_text(encoding="utf-8"))
        assert graph["M1"]["class_type"] == "MajoorShotMemory" and graph["M1"]["inputs"]["references"] == [first_reference, 0]
        assert graph["M2"]["inputs"] == {"switch": ["M1", 1], "on_true": ["M1", 0]}              # no memory, no picture
        assert graph["M3"]["inputs"]["string_b"] == ["M1", 2] and graph["M4"]["class_type"] == "MajoorSaveShotMemory"
        for prefix in ("109", "127"):
            assert graph[f"{prefix}:155"]["inputs"]["ref_images.ref_image_6"] == ["M2", 0]
            assert graph[f"{prefix}:165"]["inputs"]["value"] == ["M3", 0]


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


def test_the_audio_of_the_shot_is_anchored_for_h3_when_music_sync_is_on():
    import json
    from pathlib import Path
    from backend.models import Settings
    assert Settings().music_sync is True
    for mode in ("music", "text"):
        graph = json.loads((Path(__file__).parents[1] / "workflows" / mode / "shot.api.json").read_text(encoding="utf-8"))
        assert "on_true" not in graph["106"]["inputs"]                                   # the music is no longer a loose reference
        assert graph["108"]["inputs"]["on_true"] == graph["108"]["inputs"]["on_false"]    # and the prompt does not call it <Audio 1>
        for prefix in ("109", "127"):
            guide, switch = graph["G" + prefix], graph["S" + prefix]
            assert guide["class_type"] == "MiniMaxH3AddGuide" and guide["inputs"]["audio"] == ["101", 0] and guide["inputs"]["frame_idx"] == 0
            assert guide["inputs"]["positive"] == [prefix + ":155", 0] and guide["inputs"]["latent"] == [prefix + ":155", 1]
            assert switch["inputs"] == {"switch": ["103", 2], "on_true": ["G" + prefix, 0], "on_false": [prefix + ":155", 0]}
            assert graph[prefix + ":170"]["inputs"]["conditioning"] == ["S" + prefix, 0]


def test_the_story_of_the_edit_is_written_before_the_shots_and_the_cast(tmp_path):
    for casting in (True, False):
        graph = _fill(tmp_path, casting)
        assert graph['ST1']['class_type'] == 'MajoorMusicWords' and graph['ST1']['inputs']['words_json'] == ['T1', 0]
        assert graph['ST2']['inputs']['string_a'] == ['T2', 0] and graph['ST2']['inputs']['string_b'] == ['ST1', 3]   # brief, lyrics and the sections of the music
        assert graph['ST3']['inputs']['skill'] == 'story_planner' and graph['ST3']['inputs']['brief'] == ['ST2', 0]
        assert graph['ST4']['class_type'] == 'TextGenerate' and graph['ST4']['inputs']['system_prompt'] == ['ST3', 0] and graph['ST4']['inputs']['prompt'] == ['ST3', 1]
        assert graph['ST5']['inputs']['string_a'] == ['T2', 0] and graph['ST5']['inputs']['string_b'] == ['ST4', 0]
        assert graph['82']['inputs']['brief'] == ['ST5', 0]                                                          # the shots follow it
    assert _fill(tmp_path, True)['89']['inputs']['string_a'] == ['ST5', 0]                                          # and so does the cast


def test_text_mode_writes_the_story_and_casts_the_shots_it_planned(tmp_path):
    graph = _fill(tmp_path, True, 'text')
    assert graph['ST3']['inputs']['skill'] == 'story_planner' and graph['ST4']['inputs']['system_prompt'] == ['ST3', 0]
    assert graph['ST5']['inputs']['string_a'] == ['VX2', 0] and graph['82']['inputs']['brief'] == ['ST5', 0]         # the shots follow the story
    assert graph['85']['inputs']['skill'] == 'casting_planner' and graph['85']['inputs']['brief'] == ['T4', 0]
    assert graph['T3']['inputs']['string_b'] == ['84', 2] and graph['T4']['inputs']['string_b'] == ['84', 1]               # the cast reads the final timeline
    assert graph['87']['inputs']['casting_json'] == ['86', 0] and graph['87']['inputs']['shot_list'] == ['84', 0]
    assert graph['p1']['inputs']['shot_list'] == ['CV', 0] and graph['p5']['inputs']['shot_list'] == ['CV', 0] and graph['CV']['inputs']['shot_list'] == ['87', 0]
    off = _fill(tmp_path, False, 'text')
    assert not {'85', '86', 'T3', 'T4'} & set(off) and 'casting_json' not in off['87']['inputs'] and off['82']['inputs']['brief'] == ['ST5', 0]


def _fill_voice(tmp_path, voice):
    request = JobRequest(mode='text', settings={'prompt': 'A night ad for an energy drink', 'audio': 'voice' if voice else 'original', 'casting': True})
    runner = ComfyRunner(_settings(tmp_path), {})
    job = Job(request)
    template = load_templates(ROOT / 'workflows', 'text')['stage1']
    absent = tuple(n for n in runner._absent(job) if n in template.slots) + (() if voice else ('voice',))
    return runner, job, template.fill({'voice_lines': True} if voice else {}, absent)


def test_text_mode_reads_the_lines_of_a_voice_and_gives_each_shot_its_own(tmp_path):
    _, job, graph = _fill_voice(tmp_path, True)
    assert graph['VX1']['class_type'] == 'MajoorTranscribeVoice' and graph['VX1']['inputs']['spoken'] is True and graph['VX1']['inputs']['enabled'] == ['VT', 0]
    assert graph['VX2']['inputs']['string_b'] == ['VX1', 1] and graph['ST3']['inputs']['brief'] == ['VX2', 0] and graph['ST5']['inputs']['string_a'] == ['VX2', 0]
    assert graph['87']['inputs']['words_json'] == ['VX1', 0] and graph['87']['inputs']['spoken'] is True        # the shots say them
    assert ComfyRunner(_settings(tmp_path), {})._values(job)['voice_lines'] is True
    _, job, graph = _fill_voice(tmp_path, False)
    assert 'VX0' not in graph and 'audio' not in graph['VX1']['inputs']                                         # no voice file: nothing to read
    typed = Job(JobRequest(mode='text', settings={'prompt': 'x', 'audio': 'voice', 'dialogue': '0-2 s: "Hello."'}))
    assert ComfyRunner(_settings(tmp_path), {})._values(typed)['voice_lines'] is False                           # typed lines win


def test_pika_h3_flex_replaces_the_turbo_lora_the_sampler_and_the_sigmas_of_both_passes():
    import json
    from pathlib import Path
    from backend.models import Settings
    assert Settings().flex is False
    for mode in ("music", "text"):
        graph = json.loads((Path(__file__).parents[1] / "workflows" / mode / "shot.api.json").read_text(encoding="utf-8"))
        assert graph["FXL"]["inputs"]["model"] == ["51", 0] and graph["FXL"]["inputs"]["lora_name"].startswith("pika_h3_flex_ref2va")   # on the base model: never stacked on the turbo LoRA
        assert graph["FXG"]["inputs"]["sigmas"].count(",") == 6 and graph["FXS"]["inputs"]["sampler_name"] == "lcm"                  # six steps
        for prefix in ("109", "127"):
            assert graph[prefix + ":166"]["inputs"]["model"] == [prefix + "F1", 0]
            assert graph[prefix + ":172"]["inputs"]["sigmas"] == [prefix + "F2", 0] and graph[prefix + ":172"]["inputs"]["sampler"] == [prefix + "F3", 0]
            assert graph[prefix + "F1"]["inputs"] == {"switch": ["FXB", 0], "on_true": ["FXL", 0], "on_false": [prefix + ":158", 0]}   # off: the turbo path as before
            assert graph[prefix + "F2"]["inputs"]["on_false"] == [prefix + ":169", 0] and graph[prefix + "F3"]["inputs"]["on_false"] == [prefix + ":168", 0]


def test_the_idea_seed_reaches_every_text_model_and_the_camera_moves_follow_the_art_direction(tmp_path):
    request = JobRequest(mode='music', settings={'prompt': 'x', 'idea_seed': 7, 'art_direction': {'camera': 'steady'}})
    runner = ComfyRunner(_settings(tmp_path), {})
    job = Job(request)
    values = runner._values(job)
    assert values['idea_seed'] == 7 and values['camera_moves'] is False                                       # a steady camera turns the moves off
    assert ComfyRunner(_settings(tmp_path), {})._values(Job(JobRequest(mode='music', settings={'prompt': 'x'})))['camera_moves'] is True
    for mode in ('music', 'text'):
        template = load_templates(ROOT / 'workflows', mode)['stage1']
        graph = template.fill({'idea_seed': 7}, ())
        texts = [node for node in graph.values() if node['class_type'] == 'TextGenerate']
        assert texts and all(node['inputs']['sampling_mode.seed'] == 7 for node in texts)
        assert graph['CV']['inputs']['seed'] == 7 and graph['p1']['inputs']['shot_list'] == ['CV', 0]
        assert template.fill({}, ())['83']['inputs']['sampling_mode.seed'] == 0                                  # the first idea is the one there always was
    assert Settings().idea_seed == 0
