"""An optional model or node that is not installed must not stop a generation: its branch is cut out of the prompt."""
import copy
from pathlib import Path

import pytest

from backend.jobs import Job
from backend.models import JobRequest
from backend.optional_deps import prune_unavailable
from backend.runner import ComfyRunner
from backend.templates import load_templates, reachable_graph
from test_backend import _settings

ROOT = Path(__file__).resolve().parents[1]
FILE_FIELDS = ('unet_name', 'lora_name', 'clip_name', 'vae_name', 'name', 'ckpt_name', 'bbox_detector', 'pose_estimator')


def _shot_graph(tmp_path, mode, **settings):
    request = JobRequest(mode=mode, settings={'prompt': 'x', 'duration': 10, **settings})
    runner = ComfyRunner(_settings(tmp_path), {})
    job = Job(request)
    template = load_templates(ROOT / 'workflows', mode)['shot']
    values = runner._values(job)
    values['shot_id'] = 'SHOT_001'
    given = {k: v for k, v in values.items() if k in template.slots and not isinstance(v, Path)}
    return reachable_graph(template.fill(given, tuple(n for n in runner._absent(job) if n in template.slots)), {})


def _schemas(graph, absent_files=(), absent_classes=()):
    """What ComfyUI would list: every file the graph names, except the ones that are absent, and every node type, except the absent ones."""
    schemas = {}
    for node in graph.values():
        if node['class_type'] in absent_classes:
            continue
        required = schemas.setdefault(node['class_type'], {'input': {'required': {}}})['input']['required']
        for field in FILE_FIELDS:
            value = node['inputs'].get(field)
            if isinstance(value, str):
                required.setdefault(field, [[]])[0].append(value) if value not in absent_files else required.setdefault(field, [[]])
    return schemas


def _classes(graph):
    return {n['class_type'] for n in graph.values()}


@pytest.mark.parametrize('mode', ['music', 'text'])
def test_nothing_is_cut_when_everything_is_installed(tmp_path, mode):
    graph = _shot_graph(tmp_path, mode)
    before = copy.deepcopy(graph)
    assert prune_unavailable(graph, _schemas(graph), flex=True, places=True) == []
    assert graph == before
    assert prune_unavailable(graph, {}, flex=True, places=True) == [] and graph == before     # ComfyUI could not be asked: nothing is cut


@pytest.mark.parametrize('mode', ['music', 'text'])
def test_without_the_flex_lora_the_shots_use_the_turbo_lora_and_say_so(tmp_path, mode):
    graph = _shot_graph(tmp_path, mode, flex=True)
    schemas = _schemas(graph, absent_files={'pika_h3_flex_ref2va_v1_bf16.safetensors'})
    notes = prune_unavailable(graph, schemas, flex=True)
    assert notes and 'turbo' in notes[0]
    graph = reachable_graph(graph, {})
    assert all(str(n['inputs'].get('lora_name', '')).startswith('minimax_h3_ref2v_turbo') for n in graph.values() if n['class_type'] == 'LoraLoaderModelOnly')
    assert graph['FXB']['inputs']['value'] is False and 'on_true' not in graph['109F1']['inputs'] and 'on_true' not in graph['127F1']['inputs']
    quiet = _shot_graph(tmp_path, mode)
    assert prune_unavailable(quiet, schemas, flex=False) == []                                   # the option is off: nothing to tell, the branch is still cut


@pytest.mark.parametrize('mode', ['music', 'text'])
@pytest.mark.parametrize('absent', [{'classes': ('DWPreprocessor',)}, {'classes': ('MarigoldV2PostProcess',)}, {'files': ('minimax_h3_fun_controlnet_union_pruned_int8_convrot.safetensors',)}, {'files': ('yolox_l.onnx',)}])
def test_without_the_pose_tools_the_shots_are_made_without_the_control_that_has_no_strength(tmp_path, mode, absent):
    graph = _shot_graph(tmp_path, mode)
    assert prune_unavailable(graph, _schemas(graph, absent.get('files', ()), absent.get('classes', ()))) == []
    graph = reachable_graph(graph, {})
    assert not {'MiniMaxH3FunControlNetApply', 'DWPreprocessor', 'ModelPatchLoader', 'MarigoldV2PostProcess'} & _classes(graph)
    assert graph['109:170']['inputs']['model'] == ['109F1', 0] and graph['127:169']['inputs']['model'] == ['127F1', 0]


@pytest.mark.parametrize('mode', ['music', 'text'])
def test_without_the_h3_image_files_the_shots_go_on_without_location_images(tmp_path, mode):
    graph = _shot_graph(tmp_path, mode, places=True)
    notes = prune_unavailable(graph, _schemas(graph, absent_files={'minimax_h3_image_pruned_int8_convrot.safetensors'}), places=True)
    assert notes and 'minimax_h3_image_pruned_int8_convrot.safetensors' in notes[0]
    graph = reachable_graph(graph, {})
    assert 'MajoorCheckPlate' not in _classes(graph) and not any(n['inputs'].get('unet_name', '').startswith('minimax_h3_image') for n in graph.values())
    assert prune_unavailable(_shot_graph(tmp_path, mode), _schemas(graph), places=False) == []


def test_without_the_music_model_a_text_edit_is_cut_on_silence_and_says_so(tmp_path):
    request = JobRequest(mode='text', settings={'prompt': 'x', 'duration': 10})
    runner = ComfyRunner(_settings(tmp_path), {})
    job = Job(request)
    template = load_templates(ROOT / 'workflows', 'text')['stage1']
    given = {k: v for k, v in runner._values(job).items() if k in template.slots and not isinstance(v, Path)}
    graph = reachable_graph(template.fill(given, tuple(n for n in runner._absent(job) if n in template.slots)), {})
    schemas = _schemas(graph, absent_files={'yue2_3b_int8_convrot.safetensors'})
    schemas['EmptyAudio'] = {'input': {'required': {}}}
    notes = prune_unavailable(graph, schemas)
    assert notes and 'music model' in notes[0]
    graph = reachable_graph(graph, {})
    assert graph['73:9010']['inputs']['music'] == ['OPT_SILENCE', 0] and graph['OPT_SILENCE']['inputs']['duration'] == ['2', 0]
    assert not any(n['class_type'] in ('CheckpointLoaderSimple', 'YuE2GenerateMusic', 'KSampler') for n in graph.values())
    assert prune_unavailable(*(lambda g: (g, _schemas(g)))(copy.deepcopy(graph))) == []
