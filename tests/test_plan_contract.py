import json

from backend.direction import apply_plan_contract
from backend.models import JobRequest


def test_literal_settings_reach_only_planner():
    settings = JobRequest(mode='text', settings={'prompt': 'Product launch', 'duration': 10, 'text': True, 'text_allowed': 'NEW DROP'}).settings
    graph = {
        'planner': {'class_type': 'MajoorEditSkills', 'inputs': {'skill': 'timeline_planner', 'extra_instructions': 'Existing direction'}},
        'enhancer': {'class_type': 'MajoorEditSkills', 'inputs': {'skill': 'prompt_enhancer'}},
    }
    apply_plan_contract(graph, settings)
    instructions = graph['planner']['inputs']['extra_instructions']
    contract = json.loads(instructions.split('FINAL PLAN INPUT CONTRACT (literal settings, not a style example):\n')[1].split('\n')[0])
    assert contract['approved_text'] == ['NEW DROP']
    assert contract['target_frames'] == 240
    assert instructions.startswith('Existing direction')
    assert 'extra_instructions' not in graph['enhancer']['inputs']


def test_disabled_text_overrides_stale_allowed_text():
    settings = JobRequest(mode='text', settings={'prompt': 'Product launch', 'text': False, 'text_allowed': 'OLD TITLE'}).settings
    graph = {'p': {'class_type': 'MajoorEditSkills', 'inputs': {'skill': 'timeline_planner'}}}
    apply_plan_contract(graph, settings)
    assert '"approved_text": []' in graph['p']['inputs']['extra_instructions']
