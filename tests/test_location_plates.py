"""The empty place picture (the plate) of a shot is a reference of the video model: whatever it shows comes back in the shot.
Its prompt must not ask for paintings or posters, its check must not let them pass, and it must not be painted from the same noise in every job."""
import json
from pathlib import Path

import pytest

from backend.jobs import Job
from backend.models import JobRequest
from backend.runner import ComfyRunner, load_templates
from test_backend import _settings

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT.parent / 'workflows'  # the HyperKut graphs, when the Studio sits in the pack
MODES = ('text', 'music', 'remix')


def _shot(mode):
    return json.loads((ROOT / 'workflows' / mode / 'shot.api.json').read_text(encoding='utf-8'))


def _strings(graph):
    return [value for node in graph.values() for value in node['inputs'].values() if isinstance(value, str)]


@pytest.mark.parametrize('mode', MODES)
def test_the_plate_asks_for_plain_walls_and_its_check_lets_no_hung_art_pass(mode):
    texts = _strings(_shot(mode))
    prompt = next(t for t in texts if t.startswith('. Location reference photograph'))
    check = next(t for t in texts if t.startswith('Inspect only the attached image'))
    assert 'nothing hung on them' in prompt
    for text in (prompt, check):
        assert 'poster' not in text.lower() and 'artwork' not in text.lower(), text  # a picture model paints what its prompt names, even to allow it
    assert not any('set-dressed' in t for t in texts)


@pytest.mark.skipif(not (PACK / 'HyperKut Creative Text.json').exists(), reason='the pack graphs are not next to HyperKut')
@pytest.mark.parametrize('mode', ('text', 'music'))
def test_the_plate_texts_are_those_of_the_pack_graph(mode):
    graph = json.loads((PACK / f'HyperKut Creative {mode.title()}.json').read_text(encoding='utf-8'))
    nodes = graph['nodes'] + [n for sg in graph.get('definitions', {}).get('subgraphs', []) for n in sg['nodes']]
    pack = {v for n in nodes for v in (n.get('widgets_values') or []) if isinstance(v, str) and v.startswith(('Inspect only the attached image', '. Location reference photograph'))}
    ours = {t for t in _strings(_shot(mode)) if t.startswith(('Inspect only the attached image', '. Location reference photograph'))}
    assert ours == pack


@pytest.mark.parametrize('mode', MODES)
def test_the_plate_is_painted_by_minimax_h3_image_with_the_text_encoder_of_the_shot(mode):
    graph = _shot(mode)
    title = {n['_meta']['title']: k for k, n in graph.items() if '_meta' in n}
    prompt = graph[title['Plate · prompt']]
    assert prompt['class_type'] == 'MiniMaxH3ImageConditioning' and prompt['inputs']['clip'] == [title['H3 · text encoder'], 0]
    assert graph[title['Plate · MiniMax H3 Image']]['inputs']['unet_name'] == 'minimax_h3_image_pruned_int8_convrot.safetensors'
    assert graph[title['Plate · 6 steps']]['inputs']['steps'] == 6  # the distilled grid of the checkpoint (pdd_steps)
    sampler = graph[title['Plate · sampler']]['inputs']
    assert sampler['latent_image'] == [title['Plate · prompt'], 1] and sampler['sigmas'] == [title['Plate · 6 steps'], 0]
    assert not any(n['class_type'].startswith(('Flux2', 'EmptyFlux2')) or str(n['inputs'].get('unet_name', '')).startswith('flux') for n in graph.values())


@pytest.mark.parametrize('mode', MODES)
def test_the_plate_is_painted_from_the_seed_of_the_job(mode, tmp_path):
    template = load_templates(ROOT / 'workflows', mode)['shot']
    (node, field), = template.slots['plate_seed']
    assert template.prompt[node]['class_type'] == 'RandomNoise' and field == 'noise_seed'
    job = Job(JobRequest(mode=mode, settings={'prompt': 'x', 'seed': 1834168828}))
    assert ComfyRunner(_settings(tmp_path), {})._values(job)['plate_seed'] == 1834168828  # one plate per place in a job, another in the next job


def _shot_prompt(tmp_path, mode, place):
    """The shot prompt the runner sends, filled and cut the way _run does it."""
    from backend.templates import reachable_graph
    uploads = {'pl': tmp_path / 'room.png'} if place else {}
    job = Job(JobRequest(mode=mode, settings={'prompt': 'x', 'places': True}, place='pl' if place else None))
    runner = ComfyRunner(_settings(tmp_path), uploads)
    template = load_templates(ROOT / 'workflows', mode)['shot']
    values = {k: v for k, v in runner._values(job).items() if k in template.slots}
    prompt = template.fill({k: v for k, v in values.items() if not isinstance(v, Path)}, tuple(n for n in runner._absent(job) if n in template.slots))
    return reachable_graph(prompt, {}), values


@pytest.mark.parametrize('mode', MODES)
def test_a_picture_of_the_place_replaces_the_generated_plate_in_every_shot(mode, tmp_path):
    prompt, values = _shot_prompt(tmp_path, mode, place=True)
    assert values['place_on'] is True and values['place_image'] == tmp_path / 'room.png'  # the file goes to the LoadImage of the place
    assert prompt['PIS']['inputs']['on_true'] == ['PI', 0] and prompt['PIO']['inputs']['value'] is True
    assert prompt['PIS']['class_type'] == 'ComfySwitchNode' and prompt['PIS']['inputs']['switch'] == ['PIO', 0]  # a lazy switch: the plate branch is not run
    readers = [k for k, n in prompt.items() if ['PIS', 0] in n['inputs'].values()]
    assert any(prompt[k]['class_type'] == 'MajoorEditSkills' for k in readers) and any(prompt[k]['class_type'] == 'MajoorShotMemory' for k in readers)


@pytest.mark.parametrize('mode', MODES)
def test_without_a_picture_of_the_place_the_shots_get_the_generated_plate(mode, tmp_path):
    prompt, values = _shot_prompt(tmp_path, mode, place=False)
    assert values['place_on'] is False and 'PI' not in prompt  # the LoadImage of an absent picture is taken out
    assert any(n['class_type'] == 'MiniMaxH3ImageConditioning' for n in prompt.values())
