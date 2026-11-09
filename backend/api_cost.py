"""The video model of a job, and what a plan will cost when an API model makes its shots.

The models are the files of the `generators/` folder of the ComfyUI-Majoor-VideoTools pack (one per model: H3 runs on this computer, Seedance, Wan and
LTX are partner API nodes that are paid per take). The estimate is the one of the pack (core/cost_guard.py): the price badges of the API nodes, which
come from the object_info of the ComfyUI of the Studio, added up for the shots of the plan. It needs `jsonata-python` to read the badges; without it
the estimate keeps the seconds only."""
import importlib
import math
from functools import lru_cache

from .manual_timeline import PACK, core

PACKAGE = 'openkatana_videotools_core'  # how manual_timeline.core() names the pure core of the pack
LOCAL_MODEL = 'minimax_h3'
KNOWN = ('minimax_h3', 'seedance_2_5', 'wan_3_0', 'ltx_2_5_fast', 'ltx_2_5_pro')  # when the pack cannot be read: the models of its first release


def _module(name: str):
    core()  # loads the package once
    return importlib.import_module(f'{PACKAGE}.{name}')


@lru_cache(maxsize=1)
def video_models() -> tuple[str, ...]:
    """The ids of the video models the pack offers."""
    try:
        return tuple(_module('generators').list_generators('video')) or KNOWN
    except Exception:  # the pack cannot be read: the interface still offers the models it shipped with
        return KNOWN


def is_api(model: str) -> bool:
    try:
        return _module('generators').load_generator(model).source == 'api'
    except Exception:
        return model != LOCAL_MODEL


def describe_models() -> list[dict]:
    """For the interface: id, title, local or API."""
    try:
        generators = _module('generators')
        rows = [{'id': g, 'title': generators.load_generator(g).title, 'source': generators.load_generator(g).source} for g in video_models()]
        return sorted(rows, key=lambda row: (row['source'] != 'local', row['title']))  # the model that runs here first
    except Exception:
        return [{'id': g, 'title': g, 'source': 'local' if g == LOCAL_MODEL else 'api'} for g in video_models()]


def plan_cost(request, shot_frames: list[int], schemas: dict, fps: float = 24.0) -> dict | None:
    """The cost of the shots of a plan with the model of the job, None when the model runs here. shot_frames: the length of each shot that is generated."""
    s = request.settings
    if not is_api(s.video_model) or not shot_frames:
        return None
    guard = _module('cost_guard')
    settings = guard.Settings(
        aspect=s.ratio, resolution=s.api_resolution, audio=True,
        images=min(len(request.refs), 5) + (1 if s.places else 0), videos=1 if request.ref_video else 0, audios=1 if (s.music_sync or s.audio == 'voice') else 0)
    found = guard.estimate(s.video_model, shot_frames, fps, s.api_budget_seconds, s.api_budget_usd, settings,
                           badges=lambda class_type: (schemas.get(class_type) or {}).get('price_badge'))
    return {'generator': found.generator, 'title': found.title, 'seconds': round(found.seconds, 2), 'usd_low': None if found.price is None else round(found.price.low, 2),
            'usd_high': None if found.price is None else round(found.price.high, 2), 'budget_seconds': found.budget_seconds, 'budget_usd': found.budget_usd,
            'over_budget': found.over_budget, 'stops_at': found.stops_at, 'text': found.text, 'approved': False}


def shot_frames_of(shots, fps: float = 24.0) -> list[int]:
    """The frames of the shots that a model generates (the others are made here from the sources): what the plan asks of the generator, or the shot's own length."""
    return [s.generation_frames or max(1, math.ceil(s.duration * fps)) for s in shots if s.render_source == 'generated']
