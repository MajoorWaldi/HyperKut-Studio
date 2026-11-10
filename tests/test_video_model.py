from pathlib import Path

import pytest
from backend import api_cost
from backend.jobs import Job
from backend.models import JobRequest, Settings
from backend.runner import ComfyRunner
from backend.templates import load_templates
from test_backend import _settings

ROOT = Path(__file__).resolve().parents[1]
MODES = ('text', 'music')


def _job(mode='text', **settings):
    return Job(JobRequest(mode=mode, settings={'prompt': 'A bottle on obsidian', **settings}))


def test_h3_is_the_default_model_and_unknown_models_are_refused():
    s = Settings()
    assert (s.video_model, s.api_budget_seconds, s.api_budget_usd, s.api_resolution) == ('minimax_h3', 120, 0.0, '720p')
    assert Settings(video_model='seedance_2_5').video_model == 'seedance_2_5'
    for bad in ({'video_model': 'nope'}, {'api_resolution': '4k'}, {'api_budget_seconds': -1}, {'api_budget_usd': -0.5}):
        with pytest.raises(ValueError):
            Settings(**bad)


def test_the_models_are_the_ones_of_the_pack():
    assert {'minimax_h3', 'seedance_2_5', 'wan_3_0', 'ltx_2_5_fast', 'ltx_2_5_pro'} <= set(api_cost.video_models())
    assert api_cost.is_api('seedance_2_5') and not api_cost.is_api('minimax_h3')
    assert {m['id']: m['source'] for m in api_cost.describe_models()}['wan_3_0'] == 'api'


@pytest.mark.parametrize('mode', MODES)
def test_the_templates_have_slots_for_the_model_and_its_budgets(mode):
    templates = load_templates(ROOT / 'workflows', mode)
    for phase in ('stage1', 'shot'):
        assert {'video_model', 'api_budget_seconds', 'api_budget_usd'} <= set(templates[phase].slots), phase
    assert {'api_resolution', 'api_ratio'} <= set(templates['shot'].slots)
    assert 'video_model' not in templates['final'].slots  # the edit assembles the takes whatever made them


@pytest.mark.parametrize('mode', MODES)
def test_the_values_of_a_job_reach_the_nodes_of_the_model(tmp_path, mode):
    runner = ComfyRunner(_settings(tmp_path), {})
    job = _job(mode, video_model='wan_3_0', api_resolution='1080p', api_budget_seconds=30, api_budget_usd=5.0, ratio='16:9')
    values = runner._values(job)
    assert (values['video_model'], values['api_resolution'], values['api_ratio'], values['api_budget_seconds'], values['api_budget_usd']) == ('wan_3_0', '1080p', '16:9', 30, 5.0)
    templates = load_templates(ROOT / 'workflows', mode)
    shot = templates['shot'].fill({k: v for k, v in values.items() if k in templates['shot'].slots and not isinstance(v, Path)}, ())
    assert shot['GS']['inputs'] == {'generator': 'wan_3_0', 'max_api_seconds': 30, 'max_api_usd': 5.0, 'budget_key': job.id}  # one budget for every shot prompt of the job
    takes = [n['inputs'] for n in shot.values() if n['class_type'] == 'MajoorGenerateShot']
    assert len(takes) == 2 and all((t['resolution'], t['aspect_ratio']) == ('1080p', '16:9') for t in takes)
    plan = templates['stage1'].fill({k: v for k, v in values.items() if k in templates['stage1'].slots and not isinstance(v, Path)}, ())
    assert plan['GS']['inputs']['generator'] == 'wan_3_0'
    assert all(n['inputs']['generator'] == ['GS', 0] for n in plan.values() if n['class_type'] == 'MajoorCreateTimeline')  # the plan is made for the model


@pytest.mark.parametrize('mode', MODES)
def test_the_retry_has_its_own_seed(mode):
    slots = {k: [tuple(t) for t in v] for k, v in load_templates(ROOT / 'workflows', mode)['shot'].slots.items()}
    assert ('AG1', 'seed') in slots['seed'] and ('AG2', 'seed') in slots['seed_b']  # the take and the retry of an API model do not share a seed, as the two H3 samplers do not


@pytest.mark.parametrize('mode', MODES)
def test_h3_is_still_the_default_path_of_every_take(mode):
    shot = load_templates(ROOT / 'workflows', mode)['shot'].prompt
    assert shot['GS']['inputs']['generator'] == 'minimax_h3' and shot['GIS']['inputs'] == {'generator': ['GS', 0], 'is': 'minimax_h3'}
    for take in (n for n in shot.values() if n['class_type'] == 'CreateVideo'):
        for field in ('images', 'audio', 'fps'):
            switch = shot[str(take['inputs'][field][0])]
            assert switch['class_type'] == 'ComfySwitchNode' and switch['inputs']['switch'] == ['GIS', 0]  # H3 when the model is H3, lazily
    writer = next(n for n in shot.values() if n['class_type'] == 'MajoorEditSkills' and n['inputs'].get('skill') == 'h3_shot_prompt_from_plan')
    assert writer['inputs']['generator'] == ['GS', 0]  # the prompt is written in the style of the model


def test_an_approved_plan_runs_with_the_approved_amounts_as_its_cap(tmp_path):
    runner = ComfyRunner(_settings(tmp_path), {})
    job = _job(video_model='seedance_2_5', api_budget_seconds=10, api_budget_usd=2.0)
    assert (runner._values(job)['api_budget_seconds'], runner._values(job)['api_budget_usd']) == (10, 2.0)
    job.update(api_cost=api_cost.approve({'over_budget': True, 'seconds_high': 40, 'usd_high': 12.0}))
    assert (runner._values(job)['api_budget_seconds'], runner._values(job)['api_budget_usd']) == (43, 12.6)  # never 0 (no limit): what was approved, and 5 % for rounding
    job.update(api_cost=api_cost.approve({'over_budget': True, 'seconds_high': 4, 'usd_high': 0.5}))
    assert (runner._values(job)['api_budget_seconds'], runner._values(job)['api_budget_usd']) == (10, 2.0)  # never below the settings
    job.update(api_cost=api_cost.approve({'over_budget': True, 'seconds_high': 40, 'usd_high': None}))
    assert (runner._values(job)['api_budget_seconds'], runner._values(job)['api_budget_usd']) == (43, 0.0)  # no price was known: the seconds hold the cap
    free = _job(video_model='seedance_2_5', api_budget_seconds=0, api_budget_usd=0.0)
    free.update(api_cost=api_cost.approve({'over_budget': True, 'seconds_high': 40, 'usd_high': 12.0}))
    assert (runner._values(free)['api_budget_seconds'], runner._values(free)['api_budget_usd']) == (0, 0.0)  # no limit was the choice of the user


def test_a_plan_made_again_keeps_its_approval_only_when_it_costs_no_more():
    approved = api_cost.approve({'seconds_high': 40, 'usd_high': 12.0})
    assert api_cost.still_approved(approved, {'seconds_high': 40, 'usd_high': 11.0})
    assert not api_cost.still_approved(approved, {'seconds_high': 120, 'usd_high': 11.0})  # three times the shots
    assert not api_cost.still_approved(approved, {'seconds_high': 40, 'usd_high': 30.0})
    assert not api_cost.still_approved({'seconds_high': 40}, {'seconds_high': 10})  # never approved
    assert api_cost.still_approved(api_cost.approve({'unknown': True, 'seconds_high': None}), {'unknown': True})  # still no estimate: approved knowing it


def test_the_estimate_counts_the_second_take_and_the_retry():
    base = {'prompt': 'x', 'video_model': 'seedance_2_5', 'api_budget_seconds': 20}
    one = api_cost.plan_cost(JobRequest(mode='text', settings={**base, 'retry_bad_takes': False}), [72, 130, 48], {})
    retry = api_cost.plan_cost(JobRequest(mode='text', settings=base), [72, 130, 48], {})  # a bad take is made again: up to 2 a shot
    assert (one['takes'], one['seconds_high'], one['over_budget']) == (1, 14, False)
    assert (retry['takes'], retry['seconds_high'], retry['stops_at']) == (2, 28, 3)
    assert api_cost.takes_of(JobRequest(mode='text', settings={**base, 'best_of_two': True})) == (2, 2)
    assert api_cost.takes_of(JobRequest(mode='remix', settings={**base, 'quality_check': True})) == (1, 2)


def test_a_plan_the_pack_cannot_price_waits_for_an_approval(monkeypatch):
    monkeypatch.setattr(api_cost, '_module', lambda name: (_ for _ in ()).throw(ImportError('pack not found')))
    cost = api_cost.plan_cost(JobRequest(mode='text', settings={'prompt': 'x', 'video_model': 'seedance_2_5'}), [72], {})
    assert cost['unknown'] and cost['over_budget'] and not cost['approved'] and 'could not be estimated' in cost['text']


def test_a_local_model_has_no_api_cost():
    request = JobRequest(mode='text', settings={'prompt': 'x'})
    assert api_cost.plan_cost(request, [124, 124], {}) is None


def test_the_cost_of_a_plan_counts_the_seconds_and_says_when_it_goes_over_the_budget():
    request = JobRequest(mode='text', settings={'prompt': 'x', 'video_model': 'seedance_2_5', 'api_budget_seconds': 10, 'retry_bad_takes': False})
    cost = api_cost.plan_cost(request, [72, 130, 48], {})  # 3 s, 5.4 s, 2 s at 24 fps: Seedance asks for 4 + 6 + 4 s
    assert cost['generator'] == 'seedance_2_5' and cost['seconds'] == 14 and cost['over_budget'] and cost['stops_at'] == 3
    assert 'stops before shot 3' in cost['text'] and cost['approved'] is False
    within = api_cost.plan_cost(JobRequest(mode='text', settings={'prompt': 'x', 'video_model': 'seedance_2_5', 'api_budget_seconds': 120, 'retry_bad_takes': False}), [72, 130, 48], {})
    assert within['over_budget'] is False and within['stops_at'] is None


def test_the_price_comes_from_the_badges_of_the_comfyui_of_the_studio():
    pytest.importorskip('jsonata')
    import json
    badges = json.loads((ROOT.parent / 'tests' / 'fixtures' / 'price_badges.json').read_text(encoding='utf-8'))
    schemas = {name: {'price_badge': badge} for name, badge in badges.items()}
    request = JobRequest(mode='text', settings={'prompt': 'x', 'video_model': 'seedance_2_5', 'api_budget_usd': 3.0}, refs=['r1'])
    cost = api_cost.plan_cost(request, [144, 144], schemas)  # two 6 s takes
    assert cost['usd_low'] is not None and cost['usd_high'] >= cost['usd_low'] > 0 and cost['over_budget'] and '$' in cost['text']


from backend.runner import MockRunner  # noqa: E402
from test_backend import FakeClient, _templates  # noqa: E402


async def test_the_mock_runner_waits_for_a_plan_over_the_budget_then_runs_it():
    job = _job(video_model='seedance_2_5', api_budget_seconds=10)
    runner = MockRunner(pace=0, shots=7)
    await runner.run(job)
    assert job.state.status == 'review' and job.state.api_cost['over_budget'] and job.state.api_cost['approved'] is False  # 7 takes of at least 4 s: 28 s asked, 10 s allowed
    runner.approved(job, runner.approve_prompts(job, {}))
    assert job.state.api_cost['approved'] is True
    job.update(status='running')
    await runner.run(job)
    assert job.state.status == 'succeeded'


async def test_a_local_model_never_waits_for_a_cost_approval():
    job = _job(video_model='minimax_h3', api_budget_seconds=1)
    await MockRunner(pace=0, shots=3).run(job)
    assert job.state.status == 'succeeded' and job.state.api_cost is None


async def test_the_real_runner_stops_after_the_plan_when_the_api_cost_is_over_the_budget(tmp_path):
    _templates(tmp_path / 'workflows')
    settings = _settings(tmp_path, mock=False)
    picture = tmp_path / 'ref.png'
    picture.write_bytes(b'png')
    job = Job(JobRequest(mode='text', settings={'prompt': 'a fashion film', 'video_model': 'seedance_2_5', 'api_budget_seconds': 1}, refs=['r1']))
    client = FakeClient(settings.output_dir / 'MajoorVideoTools' / '_jobs' / f'{job.id}.json')
    runner = ComfyRunner(settings, {'r1': picture}, lambda: client)
    await runner.run(job)
    assert job.state.status == 'review' and job.state.api_cost['over_budget'] and len(client.submitted) == 1  # the plan only: no shot was asked of the model
    runner.approved(job, runner.approve_prompts(job, {}))
    job.update(status='running')
    await runner.run(job)
    assert job.state.status == 'succeeded', job.state.error
    assert job.state.api_cost['approved']


def test_a_remix_is_offered_only_the_models_that_can_edit_a_source_video():
    assert {m['id'] for m in api_cost.describe_models('remix')} == {'minimax_h3', 'seedance_2_5'}
    assert {'wan_3_0', 'ltx_2_5_pro'} <= {m['id'] for m in api_cost.describe_models()}  # Text and Music have them all
    assert api_cost.can_remix('seedance_2_5') and not api_cost.can_remix('wan_3_0')


def test_a_remix_request_with_a_model_that_cannot_edit_is_refused():
    assert JobRequest(mode='remix', settings={'prompt': 'x', 'video_model': 'seedance_2_5'}).settings.video_model == 'seedance_2_5'
    for model in ('wan_3_0', 'ltx_2_5_fast'):
        with pytest.raises(ValueError, match='cannot replace the subject'):
            JobRequest(mode='remix', settings={'prompt': 'x', 'video_model': model})
    assert JobRequest(mode='text', settings={'prompt': 'x', 'video_model': 'wan_3_0'}).settings.video_model == 'wan_3_0'  # a creation can use them


def test_the_remix_template_has_the_choice_and_edits_the_source_shot(tmp_path):
    templates = load_templates(ROOT / 'workflows', 'remix')
    assert {'video_model', 'api_budget_seconds', 'api_budget_usd', 'api_resolution'} <= set(templates['shot'].slots)
    assert 'video_model' not in templates['stage1'].slots  # nothing to plan for a model: the shots are cut from the source
    shot = templates['shot'].prompt
    takes = [n['inputs'] for n in shot.values() if n['class_type'] == 'MajoorGenerateShot']
    assert len(takes) == 2 and all(t['task'] == 'edit' and shot[str(t['source_video'][0])]['class_type'] == 'MajoorSelectShot' for t in takes)
    assert not any('reference_frames' in t for t in takes)
    writer = next(n for n in shot.values() if n['class_type'] == 'MajoorEditSkills' and n['inputs'].get('skill') == 'remix_shot_prompt')
    assert writer['inputs']['generator'] == ['GS', 0]
    for take in (n for n in shot.values() if n['class_type'] == 'CreateVideo'):
        assert all(shot[str(take['inputs'][f][0])]['inputs']['switch'] == ['GIS', 0] for f in ('images', 'audio', 'fps'))


def test_the_cost_of_a_remix_is_the_cost_of_editing_the_source():
    request = JobRequest(mode='remix', settings={'prompt': 'x', 'video_model': 'seedance_2_5', 'api_budget_seconds': 10})
    cost = api_cost.plan_cost(request, [72, 130, 48], {})
    assert cost['generator'] == 'seedance_2_5' and cost['over_budget'] and cost['stops_at'] == 3


def test_the_picker_prices_every_model_for_the_length_of_the_edit():
    pytest.importorskip('jsonata')
    import json
    badges = json.loads((ROOT.parent / 'tests' / 'fixtures' / 'price_badges.json').read_text(encoding='utf-8'))
    schemas = {name: {'price_badge': badge} for name, badge in badges.items()}
    rows = {row['id']: row for row in api_cost.estimate_models('text', 15, schemas, refs=1)}
    assert rows['minimax_h3']['source'] == 'local' and rows['minimax_h3']['usd_low'] is None and rows['minimax_h3']['seconds'] is None  # nothing to pay here
    assert rows['seedance_2_5']['seconds'] >= 15 and rows['seedance_2_5']['usd_high'] >= rows['seedance_2_5']['usd_low'] > 0
    longer = {row['id']: row for row in api_cost.estimate_models('text', 60, schemas, refs=1)}
    assert longer['seedance_2_5']['usd_low'] > rows['seedance_2_5']['usd_low']  # a longer edit costs more


def test_the_picker_without_price_badges_still_says_how_many_seconds_are_asked():
    rows = {row['id']: row for row in api_cost.estimate_models('music', 12, {}, music=True)}
    assert rows['wan_3_0']['seconds'] == 12 and rows['wan_3_0']['usd_low'] is None


def test_a_remix_is_priced_for_the_models_that_edit():
    assert {row['id'] for row in api_cost.estimate_models('remix', 15, {})} == {'minimax_h3', 'seedance_2_5'}


def test_the_estimate_endpoint_answers_for_every_model_and_refuses_a_bad_question(tmp_path):
    from fastapi.testclient import TestClient
    from backend.server import create_app
    client = TestClient(create_app(_settings(tmp_path)))
    body = client.get('/api/video-models/estimate', params={'mode': 'text', 'seconds': 15, 'ratio': '9:16', 'resolution': '720p', 'refs': 2}).json()
    assert {'minimax_h3', 'seedance_2_5', 'wan_3_0'} <= {row['id'] for row in body['models']}
    assert all({'source', 'seconds', 'usd_low', 'usd_high'} <= set(row) for row in body['models'])
    assert client.get('/api/video-models/estimate', params={'seconds': 0}).status_code == 422
    assert client.get('/api/video-models/estimate', params={'resolution': '8k'}).status_code == 422
    assert client.get('/api/video-models/estimate', params={'mode': 'nope'}).status_code == 422
