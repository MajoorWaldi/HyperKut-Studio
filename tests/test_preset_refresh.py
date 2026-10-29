import json
import pytest
from pathlib import Path

from backend.jobs import Job
from backend.models import EditStyle, JobRequest, Settings
from backend.runner import ComfyRunner
from test_backend import _settings


@pytest.mark.parametrize('path',list((Path(__file__).resolve().parents[1]/'presets').glob('*.json')),ids=lambda path:path.stem)
def test_every_builtin_preset_has_current_defaults_and_valid_settings(path):
    for path in [path]:
        data=json.loads(path.read_text(encoding='utf-8'))
        settings=Settings.model_validate({**data['settings'],'seed':42})
        assert settings.motion_design is False,path.name
        assert settings.music_volume == 1,path.name
        # Named presets and structured JSON are both supported by the renderer.
        if settings.motion_direction.lstrip().startswith('{'):
            direction=json.loads(settings.motion_direction)
            assert direction['preset'] in ('minimal','editorial','energetic')
            assert 0 <= direction.get('intensity', .6) <= 1
        else:
            assert settings.motion_direction in ('minimal','editorial','energetic')
        from backend.unified_motion import validate_finishing
        validate_finishing(settings.model_dump(), settings.duration)
        assert set(data['translations']) == {'en','fr'}
        for lang in ('en','fr'):
            assert all(data['translations'][lang][key] for key in ('name','description','prompt'))
            assert set(data['translations'][lang]['settings']) == {'mood','camera'}
        assert json.loads(settings.motion_layers)==[] and json.loads(settings.motion_cues)==[]


def test_new_job_and_reedit_preserve_the_right_layer_json_and_explicit_audio_mix(tmp_path):
    layers='[{"type":"text","content":"LEGACY"}]'
    cues='[{"start":1,"end":2,"text":"NEW"}]'
    request=JobRequest(mode='text',settings={'motion_layers':layers,'motion_cues':cues})
    job=Job(request)
    runner=ComfyRunner(_settings(tmp_path),{})
    values=runner._values(job)
    assert values['motion_design'] is False and values['edit_music_volume']==1
    assert values['motion_layers']==layers and values['motion_cues']==cues
    assert job.state.style.motion_layers==layers and job.state.style.motion_cues==cues
    values=runner._values(job,EditStyle(music_volume=.7,motion_design=False,motion_cues='[]'))
    assert values['edit_music_volume']==.7 and values['motion_design'] is False
    assert values['motion_cues']=='[]'


def test_older_job_restores_missing_layer_json_without_overwriting_explicit_edits():
    from backend.models import JobState
    request=JobRequest(mode='text',settings={'motion_layers':'[{"type":"text","content":"SAVED"}]'})
    state=JobState(id='old',mode='text',created_at=0,style=EditStyle(motion_design=False,music_volume=.3))
    restored=Job(request,state)
    assert restored.state.style.motion_layers==request.settings.motion_layers
    assert restored.state.style.motion_design is False
    assert restored.state.style.music_volume==.3


def test_calm_music_preset_reaches_musicfit_and_keeps_auto_bpm(tmp_path):
    from backend.templates import load_templates
    root=Path(__file__).resolve().parents[1]
    phase=load_templates(root/'workflows','music')['stage1']
    runner=ComfyRunner(_settings(tmp_path),{})
    for energy in ('calm','peak'):
        values=runner._values(Job(JobRequest(mode='music',settings={'music_energy':energy,'music_start':-1,'seed':42})))
        graph=phase.fill({key:value for key,value in values.items() if key in phase.slots})
        fit=graph['70']['inputs']
        assert fit['energy_goal']==energy and fit['bpm']==0
        assert fit['start']==['3',0]
