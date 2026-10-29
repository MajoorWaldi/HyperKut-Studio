from pathlib import Path
import pytest

from backend.jobs import Job
from backend.models import JobRequest, EditStyle
from backend.runner import ComfyRunner
from backend.templates import load_templates
from test_backend import _settings

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('mode',['text','music','remix'])
def test_disabled_finishing_is_removed_before_comfy_validation(mode):
    template=load_templates(ROOT/'workflows',mode)['final']
    graph=template.fill({'motion_design':False})
    assert not any(n['class_type']=='MajoorHyperFrames' for n in graph.values())
    save=next(n for n in graph.values() if n['class_type']=='SaveVideo')
    assert save['inputs']['video'][0]!='hyperframes'
    assert template.prompt['hyperframes']['inputs']['enabled'] is True
    graph=template.fill({'motion_design':True,'hyperframes_direction':'minimal'})
    assert graph['hyperframes']['inputs']['enabled'] is True
    assert graph['hyperframes']['inputs']['direction']=='minimal'


def test_finishing_is_off_by_default_and_reedit_overrides_without_new_generation(tmp_path):
    runner=ComfyRunner(_settings(tmp_path),{})
    job=Job(JobRequest(mode='text'))
    assert runner._values(job)['motion_design'] is False
    values=runner._values(job,EditStyle(motion_design=True,motion_direction='minimal',motion_title='NEW DROP'))
    assert values['motion_design'] is True and values['motion_title']=='NEW DROP'
    assert values['motion_direction']=='minimal' and 'edit_motion_design' not in values
