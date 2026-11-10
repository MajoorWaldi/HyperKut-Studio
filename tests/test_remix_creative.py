import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.brief_preview import REMIX_TREATMENTS, prepare_treatments
from backend.capacity import reservation_bytes
from backend.jobs import Job
from backend.models import JobRequest
from backend.optional_deps import prune_unavailable
from backend.runner import ComfyRunner, MockRunner
from backend.server import create_app
from backend.templates import load_templates
from test_backend import _finished_job, _project_on_disk, _settings

ROOT = Path(__file__).resolve().parents[1]


def _values(tmp_path, **settings):
    request = JobRequest.model_validate({'mode': 'remix', 'source': 'a' * 12, 'refs': ['b' * 12, 'c' * 12], 'settings': settings})
    uploads = {key: tmp_path / f'{key}.bin' for key in ('a' * 12, 'b' * 12, 'c' * 12)}
    return ComfyRunner(_settings(tmp_path), uploads)._values(Job(request))


def test_the_remix_is_planned_when_its_strategy_rewrites_the_source_or_people_are_cast(tmp_path):
    preserve = _values(tmp_path, remix_strategy='preserve')
    assert not preserve['remix_plan'] and not preserve['source_words'] and not preserve['remix_camera']
    assert preserve['pictures_before'] == 2 and 'STRATEGY: preserve' in preserve['planning_instructions']
    creative = _values(tmp_path, remix_strategy='creative')
    assert creative['remix_plan'] and creative['remix_cast'] and creative['source_words'] and creative['remix_camera']
    transfer = _values(tmp_path, remix_strategy='transfer', art_direction={'camera': 'steady'})
    assert transfer['remix_plan'] and not transfer['remix_camera']  # the camera of the source stays outside a creative remix
    assert _values(tmp_path, casting=True)['remix_plan'] and _values(tmp_path, kinetic_lyrics=True)['source_words']
    replaced = _values(tmp_path, kinetic_lyrics=True, audio='new')  # a new sound has other words than the source
    assert not replaced['kinetic_lyrics'] and not replaced['source_words']


def test_best_of_two_doubles_the_remix_budget():
    one = JobRequest.model_validate({'mode': 'remix', 'source': 'a' * 12, 'settings': {'duration': 10}})
    two = JobRequest.model_validate({'mode': 'remix', 'source': 'a' * 12, 'settings': {'duration': 10, 'best_of_two': True}})
    assert reservation_bytes(two) > reservation_bytes(one)


def test_the_remix_graphs_fill_with_the_new_slots(tmp_path):
    templates = load_templates(ROOT / 'workflows', 'remix')
    values = {**_values(tmp_path, remix_strategy='creative', best_of_two=True), 'shot_id': 'SHOT_001', 'project_id': 'p_0123456789ab', 'seed_b': 7}
    stage1 = templates['stage1'].fill({k: v for k, v in values.items() if k in templates['stage1'].slots and not isinstance(v, Path)})
    assert stage1['RB']['inputs']['value'] is True and stage1['CV']['inputs']['enabled'] is True and stage1['VT']['inputs']['value'] is True
    assert 'STRATEGY: creative' in stage1['PI']['inputs']['value'] and stage1['RM']['inputs']['pictures'] == 2
    shot = templates['shot'].fill({k: v for k, v in values.items() if k in templates['shot'].slots and not isinstance(v, Path)})
    assert shot['JBOOL']['inputs']['value'] is True and shot['108:155']['inputs']['noise_seed'] == 7 and shot['M1']['inputs']['pictures_before'] == 2
    assert 'local' in templates


def test_an_older_comfyui_makes_the_remix_without_its_plan():
    graph = json.loads((ROOT / 'workflows/remix/stage1.api.json').read_text(encoding='utf-8'))
    notes = prune_unavailable(graph, {'MajoorSceneDetectSplit': {}, 'MajoorCameraMoves': {}})
    assert 'RM' not in graph and graph['CV']['inputs']['shot_list'] == ['68', 0] and 'Remix Plan' in notes[0]


def test_the_control_frames_play_at_the_24_fps_of_the_take_and_an_older_pack_passes_them_as_they_are():
    graph = json.loads((ROOT / 'workflows/remix/shot.api.json').read_text(encoding='utf-8'))
    for take in ('91', '108'):
        assert graph[f'{take}:RT']['inputs'] == {'images': [f'{take}:151', 0], 'fps_in': ['87', 2], 'fps_out': 24.0}
        assert graph[f'{take}:160']['inputs']['image'] == graph[f'{take}:1229']['inputs']['image'] == [f'{take}:RT', 0]
    for take in ('107', '109'):  # the take is written at the rate the frames were retimed to: 24 fps on the H3 side of the model switch (an API take brings its own fps)
        switch = graph[str(graph[take]['inputs']['fps'][0])]
        assert switch['inputs']['switch'] == ['GIS', 0] and graph[str(switch['inputs']['on_true'][0])]['inputs']['value'] == 24
    assert graph['short_reference_switch']['inputs']['on_false'] == ['RV', 0] and graph['RV']['inputs']['fps_out'] == 24.0  # H3 reads its reference video at 24 fps
    assert graph['119']['inputs']['skip_copied_lead'] is True  # a take opening on a copy of the source starts after it
    # the judge sees, and Source Copy measures, the part of each take the edit keeps
    assert graph['SC']['inputs'] == {'take_a': ['107', 0], 'take_b': ['109', 0], 'source': ['75', 0], 'max_seconds': ['89', 0]}
    assert graph['JA']['inputs']['max_seconds'] == graph['JB2']['inputs']['max_seconds'] == ['89', 0]
    notes = prune_unavailable(graph, {'MajoorSelectShot': {}})  # a pack without the node
    assert '91:RT' not in graph and graph['91:160']['inputs']['image'] == ['91:151', 0] and any('Retime Frames' in note for note in notes)
    assert 'SC' not in graph and graph['JN']['inputs']['values.c'] is False is graph['JN']['inputs']['values.d'] and any('Source Copy' in note for note in notes)


def test_a_take_that_repeats_the_source_is_never_kept_over_one_that_does_not():
    graph = json.loads((ROOT / 'workflows/remix/shot.api.json').read_text(encoding='utf-8'))
    node = graph['JN']['inputs']
    assert (node['values.a'], node['values.b'], node['values.c'], node['values.d']) == (['TA', 0], ['JC', 0], ['SC', 0], ['SC', 1])
    keep_a = lambda a, b, c, d: eval(node['expression'], {}, dict(a=a, b=b, c=c, d=d))
    for a in (0, 1):
        for b in (0, 1):  # take A passes its check (a), the judge prefers B (b)
            assert keep_a(a, b, 0, 1) and not keep_a(a, b, 1, 0)  # only one take repeats the source: the other one
            for same in (0, 1):
                assert keep_a(a, b, same, same) == ((1 - b) * a > 0)  # both or neither: the judge and the check of A, as before


def test_remix_has_three_treatments_of_its_own(tmp_path):
    request = JobRequest.model_validate({'mode': 'remix', 'source': 'a' * 12, 'settings': {'prompt': 'a courier at night'}})
    treatments = asyncio.run(prepare_treatments(request, _settings(tmp_path), {}, 'en'))  # mock settings: text only, no model
    assert [t['name'] for t in treatments] == [name for name, _ in REMIX_TREATMENTS] == ['faithful', 'twist', 'transfer']


def test_a_remix_shot_can_be_kept_as_in_the_source(tmp_path):
    settings = _settings(tmp_path)
    folder = _project_on_disk(settings)
    index = settings.output_dir / 'MajoorVideoTools' / '_jobs'
    runner = MockRunner(pace=0.01)
    original = runner.run

    async def with_project(job):
        await original(job)
        job.update(project_id='p_0123456789ab')
        index.mkdir(parents=True, exist_ok=True)
        (index / f'{job.id}.json').write_text(json.dumps({'project_id': 'p_0123456789ab', 'shots': [{'id': 'SHOT_001', 'render_source': 'generated'}]}))

    runner.run = with_project
    with TestClient(create_app(settings, runner)) as client:
        job = _finished_job(client)
        state = client.post(f'/api/jobs/{job}/shots/SHOT_001/source', json={'kind': 'original'}).json()
        assert state['shots'][0]['render_source'] == 'original'
        assert json.loads((folder / 'manifest.json').read_text())['shots'][0]['plan']['render_source'] == {'kind': 'original'}
        assert json.loads((index / f'{job}.json').read_text())['shots'][0]['render_source'] == 'original'
        back = client.post(f'/api/jobs/{job}/shots/SHOT_001/source', json={'kind': 'generated'}).json()
        assert back['shots'][0]['render_source'] == 'generated' and 'render_source' not in json.loads((folder / 'manifest.json').read_text())['shots'][0]['plan']
        assert client.post(f'/api/jobs/{job}/shots/SHOT_404/source', json={'kind': 'original'}).status_code == 404
        assert client.post(f'/api/jobs/{job}/shots/SHOT_001/source', json={'kind': 'graphic'}).status_code == 422
