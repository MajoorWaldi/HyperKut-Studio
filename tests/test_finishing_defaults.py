from backend.jobs import Job
from backend.models import JobRequest, EditStyle
from backend.runner import ComfyRunner
from test_backend import _settings
import pytest

@pytest.mark.parametrize("mode", ["text", "music", "remix"])
def test_finishing_is_opt_in_for_each_mode(tmp_path, mode):
    job = Job(JobRequest(mode=mode))
    runner = ComfyRunner(_settings(tmp_path), {})
    values = runner._values(job)
    for key in ("effects", "text", "sound_design", "sound_effects", "motion_design", "edit_sub_cuts", "edit_effects", "edit_text", "edit_auto_sfx"):
        assert values[key] is False, key
    enabled = runner._values(job, EditStyle(effects=True, text=True, sub_cuts=True, auto_sfx=True, motion_design=True))
    for key in ("edit_effects", "edit_text", "edit_sub_cuts", "edit_auto_sfx", "motion_design"):
        assert enabled[key] is True, key


def test_explicit_saved_finishing_stays_enabled(tmp_path):
    request = JobRequest(mode="text", settings={"effects":True, "text":True, "sound_design":True, "sound_effects":True, "motion_design":True, "sub_cuts":True})
    job = Job(request)
    values = ComfyRunner(_settings(tmp_path), {})._values(job)
    assert all(values[k] for k in ("edit_effects", "edit_text", "edit_auto_sfx", "motion_design", "edit_sub_cuts"))
