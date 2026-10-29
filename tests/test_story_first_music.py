import json
from pathlib import Path
from backend.templates import load_templates

ROOT = Path(__file__).parents[1]


def ancestors(graph, key, visiting=None):
    visiting = set() if visiting is None else visiting
    assert key not in visiting, 'Workflow dependency cycle'
    visiting.add(key)
    result = {key}
    for value in graph[key]['inputs'].values():
        if isinstance(value, list) and len(value)==2 and str(value[0]) in graph:
            result |= ancestors(graph, str(value[0]), visiting)
    visiting.remove(key)
    return result


def test_text_music_waits_for_visual_plan_without_a_feedback_cycle():
    graph = load_templates(ROOT/'workflows','text')['stage1'].prompt
    planner = graph['music_story_context']['inputs']['string_b'][0]
    assert planner in ancestors(graph,'music_vision')
    assert 'music_vision' not in ancestors(graph,planner)
    for key in graph:
        ancestors(graph,key)
    assert sum(x['class_type']=='TextGenerate' for x in graph.values()) == 3
    assert sum(x['class_type']=='YuE2GenerateABC' for x in graph.values()) == 1
    assert sum(x['class_type']=='YuE2GenerateMusic' for x in graph.values()) == 1


def test_user_genre_and_visual_plan_share_the_directors_user_input():
    template = load_templates(ROOT/'workflows','text')['stage1']
    context = json.dumps({'user_music_preference':'raw trap, no jazz','duration_seconds':10})
    graph = template.fill({'music_context':context},())
    assert graph['music_story_context']['inputs']['string_a'] == context
    assert graph['music_vision']['inputs']['prompt'] == ['music_story_context',0]
    assert 'guaranteed generated musical attacks' in graph['music_vision']['inputs']['system_prompt']


def test_other_modes_keep_their_existing_music_flow():
    for mode in ('music','remix'):
        for template in load_templates(ROOT/'workflows',mode).values():
            assert 'music_story_context' not in template.prompt
    source = (ROOT/'scripts/export_templates.js').read_text(encoding='utf-8')
    assert "mode === 'text' && files.stage1.music_vision" in source
