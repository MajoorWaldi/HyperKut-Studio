import json
from pathlib import Path
from backend.runner import ComfyRunner
from backend.models import JobRequest
from backend.jobs import Job
from backend.templates import load_templates
from test_backend import _settings

ROOT=Path(__file__).parents[1]

def test_direction_uses_existing_settings_without_model_selection(tmp_path):
    runner=ComfyRunner(_settings(tmp_path),{})
    job=Job(JobRequest(mode='text',settings={'prompt':'slow lagoon, glass bottle','mood':'quiet piano, no drop','bpm':84,'seed':93}))
    values=runner._values(job)
    assert values['music_mood']=='quiet piano, no drop'
    assert 'quiet piano, no drop' in values['planning_instructions']
    assert values['music_bpm']==84 and values['music_seed']==93
    assert json.loads(values['music_context'])['creative_brief']=='slow lagoon, glass bottle'
    assert not hasattr(job.request.settings,'music_model')


def _of(graph,class_type):
    return {k:n for k,n in graph.items() if n['class_type']==class_type}


def test_one_existing_model_receives_one_audiovisual_brief():
    templates=load_templates(ROOT/'workflows','text')
    graph=templates['stage1'].prompt  # the only prompt that makes the music: the shots and the edit read it back from the project
    (_,encoder),=_of(graph,'YuE2GenerateMusic').items()
    (_,style),=_of(graph,'MajoorYuE2Style').items()
    (score_id,score),=_of(graph,'MajoorYuE2Score').items()
    (plan_id,_),=_of(graph,'YuE2GenerateABC').items()
    assert style['inputs']['prompt']==['music_direction',0]
    assert encoder['inputs']['abc']==[score_id,0]
    assert score['inputs']['abc']==[plan_id,0]
    assert 'variations' not in graph['music_vision']['inputs']['system_prompt']
    assert not _of(graph,'MajoorSaveMusicReport')
    fits=_of(graph,'MajoorMusicFit')
    assert fits and all(n['inputs']['energy_goal']==['music_direction',2] for n in fits.values())
    assert [n['inputs']['ckpt_name'] for n in _of(graph,'CheckpointLoaderSimple').values()]==['yue2_3b_int8_convrot.safetensors']
    assert _of(graph,'MajoorSaveProjectMusic')
    for phase in ('shot','final'):
        graph=templates[phase].prompt
        assert not _of(graph,'YuE2GenerateMusic') and not _of(graph,'MajoorMusicFit') and _of(graph,'MajoorLoadProjectMusic')
    for template in templates.values():
        assert all(field in template.prompt[node]['inputs'] for targets in template.slots.values() for node,field in targets)


def test_music_mood_reaches_its_planner_without_new_ui_controls(tmp_path):
    runner=ComfyRunner(_settings(tmp_path),{})
    values=runner._values(Job(JobRequest(mode='music',settings={'mood':'calm and intimate'})))
    assert 'calm and intimate' in values['planning_instructions']
    assert 'planning_instructions' in load_templates(ROOT/'workflows','music')['stage1'].slots


def test_remix_keeps_the_original_audio_switch_and_music_mode_keeps_uploaded_audio():
    remix=load_templates(ROOT/'workflows','remix')['final']
    assert any(n['class_type']=='YuE2GenerateMusic' for n in remix.prompt.values())
    assert any(n['class_type']=='ComfyMathExpression' and n['inputs'].get('expression')=='max(a, 1 - b) > 0' for n in remix.prompt.values())
    for phase in ('stage1','shot','final'):
        graph=load_templates(ROOT/'workflows','music')[phase].prompt
        assert not any(n['class_type']=='YuE2GenerateMusic' for n in graph.values())


def test_remix_new_music_without_mood_uses_brief_without_selecting_a_genre(tmp_path):
    from backend.jobs import Job
    from backend.models import JobRequest
    from backend.runner import ComfyRunner
    from test_backend import _settings
    runner=ComfyRunner(_settings(tmp_path),{'source':tmp_path/'source.mp4'})
    request=JobRequest(mode='remix',source='source',settings={'audio':'new','mood':'','prompt':'Dark trap, neon sneaker reveal'})
    values=runner._values(Job(request))
    assert values['mood'].strip() and 'Dark trap' in values['mood']
    assert 'jazz' not in values['mood'].lower()
    explicit=JobRequest(mode='remix',source='source',settings={'audio':'new','mood':'industrial techno'})
    assert runner._values(Job(explicit))['mood']=='industrial techno'
