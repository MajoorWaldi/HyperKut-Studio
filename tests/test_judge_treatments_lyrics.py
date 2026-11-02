"""Best of two takes (a vision model judges), three treatments of a brief, kinetic lyrics on the finishing pass."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.jobs import Job
from backend.models import JobRequest, Settings
from backend.runner import ComfyRunner
from backend.server import create_app
from backend.templates import load_templates
from test_backend import _settings

ROOT = Path(__file__).resolve().parents[1]


def _links_resolve(graph):
    for key, node in graph.items():
        for field, value in node['inputs'].items():
            if isinstance(value, list):
                assert str(value[0]) in graph, f'{key}.{field} points at the missing node {value[0]}'


def test_best_of_two_is_off_by_default_and_costs_a_second_take_in_the_budget(tmp_path):
    assert Settings().best_of_two is False and Settings().kinetic_lyrics is False
    values = ComfyRunner(_settings(tmp_path), {})._values(Job(JobRequest(mode='music', settings={'prompt': 'x', 'best_of_two': True, 'retry_bad_takes': False, 'kinetic_lyrics': True})))
    assert values['judge'] is True and values['kinetic_lyrics'] is True and values['retry_bad'] is False


def test_the_judge_compares_the_frames_of_both_takes_and_replaces_the_rule_of_the_first_take():
    for mode in ('music', 'text'):
        template = load_templates(ROOT / 'workflows', mode)['shot']
        graph = template.fill({'judge': True, 'seed': 5, 'seed_b': 9}, ())
        _links_resolve(graph)
        assert graph['JBOOL']['inputs']['value'] is True
        assert graph['JA']['inputs']['video'] == ['123', 0] and graph['JB2']['inputs']['video'] == ['128', 0]          # the first take, then the one with the other seed
        assert graph['JS']['inputs']['skill'] == 'take_judge' and graph['JS']['inputs']['video_1'] == ['JA', 6] and graph['JS']['inputs']['video_2'] == ['JB2', 6]
        assert graph['JT']['inputs']['system_prompt'] == ['JS', 0] and graph['JC']['inputs']['substring'] == 'BETTER: B'
        assert graph['JN']['inputs']['values.a'] == ['124', 0]                                                         # a take that is black loses even when the judge likes it
        assert graph['JW']['inputs'] == {'switch': ['JBOOL', 0], 'on_true': ['JN', 2], 'on_false': ['125', 2]}         # lazy: off, the second take is still made only when the first is bad
        assert graph['129']['inputs']['switch'] == ['JW', 0]
        assert graph['109:171']['inputs']['noise_seed'] == 5 and graph['127:171']['inputs']['noise_seed'] == 9


def test_the_second_take_gets_its_own_seed():
    from backend.runner import second_seed
    template = load_templates(ROOT / 'workflows', 'music')['shot']
    graph = template.fill({'seed': 42, 'seed_b': second_seed(42)}, ())
    assert graph['109:171']['inputs']['noise_seed'] == 42 and graph['127:171']['inputs']['noise_seed'] == second_seed(42) != 42


def test_kinetic_lyrics_keep_the_words_in_the_first_step(tmp_path):
    template = load_templates(ROOT / 'workflows', 'music')
    stage1 = template['stage1'].fill({}, ())
    assert stage1['p7']['class_type'] == 'MajoorSaveProjectLyrics' and stage1['p7']['inputs']['shot_list'] == ['CV', 0]
    assert stage1['p7']['inputs']['words_json'] == ['ST1', 0] and stage1['ST1']['class_type'] == 'MajoorMusicWords'      # the words with the accents that land on a beat
    assert 'kinetic_lyrics' not in template['final'].slots and template['final'].fill({}, ())['hyperframes']['inputs']['shot_cues'] == '[]'


def test_the_words_of_the_project_become_one_kinetic_layer_that_leaves_room_for_the_users_own(tmp_path):
    from backend.lyrics_layer import MAX_LAYERS, lyrics_layer
    (tmp_path / 'music').mkdir()
    words = [{'word': 'fangs', 'start': 0.0, 'end': 0.3, 'accent': True}, {'word': 'bones', 'start': 1.0, 'end': 1.4}, {'word': 'late', 'start': 30.0, 'end': 30.4}, {'word': ' ', 'start': 2.0, 'end': 2.1}]
    (tmp_path / 'music' / 'lyrics.json').write_text(json.dumps(words), encoding='utf-8')
    layer = lyrics_layer(tmp_path, 12.0, [])
    assert layer['template'] == 'kinetic_lyrics' and layer['end'] == 12.0 and layer['position'] == 'bottom'
    assert [w['word'] for w in layer['words']] == ['fangs', 'bones'] and layer['words'][0]['accent'] is True and 'accent' not in layer['words'][1]
    assert lyrics_layer(tmp_path, 12.0, [], [layer]) is None                                                           # an edit made again does not get a second one
    many = [{'word': f'w{i}', 'start': i * 0.1, 'end': i * 0.1 + 0.05} for i in range(300)]
    (tmp_path / 'music' / 'lyrics.json').write_text(json.dumps(many), encoding='utf-8')
    assert len(lyrics_layer(tmp_path, 60.0, [{'type': 'effect'}] * 10)['words']) == MAX_LAYERS - 4 - 10
    assert lyrics_layer(tmp_path / 'nothing', 12.0, []) is None


def test_three_treatments_are_three_briefs_of_the_same_request(tmp_path):
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        request = {'mode': 'text', 'settings': {'prompt': 'A runner crosses the city at night'}}
        response = client.post('/api/brief-treatments', json=request)
        assert response.status_code == 200, response.text
        found = response.json()['treatments']
        assert [item['name'] for item in found] == ['direct', 'twist', 'visual']
        assert len({item['brief'] for item in found}) == 3 and all(item['context'] for item in found)
        assert client.get('/api/jobs').json() == []                                                                    # text only: no video starts
        request['settings']['art_direction'] = {'look': 'bad'}
        assert client.post('/api/brief-treatments', json=request).status_code == 422
