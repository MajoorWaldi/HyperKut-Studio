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


def can_remix(model: str) -> bool:
    """Can the model replace the subject of a source video? H3 does with its pose map, Seedance in edit mode."""
    try:
        return bool(_module('generators').load_generator(model).remix)
    except Exception:
        return model in ('minimax_h3', 'seedance_2_5')


def describe_models(mode: str | None = None) -> list[dict]:
    """For the interface: id, title, local or API. A Remix is offered only the models that can edit a source video."""
    try:
        generators = _module('generators')
        rows = [{'id': g, 'title': generators.load_generator(g).title, 'source': generators.load_generator(g).source} for g in video_models() if mode != 'remix' or can_remix(g)]
        return sorted(rows, key=lambda row: (row['source'] != 'local', row['title']))  # the model that runs here first
    except Exception:
        return [{'id': g, 'title': g, 'source': 'local' if g == LOCAL_MODEL else 'api'} for g in video_models() if mode != 'remix' or can_remix(g)]


def takes_of(request) -> tuple[int, int]:
    """(fewest, most) takes a shot may be made with: a second take always (best of two), or only for a bad take (retry, the quality check of a Remix)."""
    s = request.settings
    if s.best_of_two:
        return 2, 2
    retry = s.quality_check if request.mode == 'remix' else s.retry_bad_takes
    return 1, (2 if retry else 1)


def plan_cost(request, shot_frames: list[int], schemas: dict, fps: float = 24.0) -> dict | None:
    """The cost of the shots of a plan with the model of the job, None when the model runs here. shot_frames: the length of each shot that is generated.
    The budget is checked on the most takes a shot may need (a second take, a retry). When the pack cannot price the plan the cost is unknown and
    the plan waits for an approval rather than starting paid takes unchecked."""
    s = request.settings
    if not is_api(s.video_model) or not shot_frames:
        return None
    low, high = takes_of(request)
    try:
        guard = _module('cost_guard')
        remix = request.mode == 'remix'  # a remix changes the source shot: one video, the pictures, no audio reference
        settings = guard.Settings(
            aspect=s.ratio, resolution=s.api_resolution, audio=True, images=min(len(request.refs), 5) + (1 if s.places else 0),
            videos=1 if (remix or request.ref_video) else 0, audios=0 if remix else (1 if (s.music_sync or s.audio == 'voice') else 0), task='edit' if remix else 'reference')
        found = guard.estimate(s.video_model, shot_frames, fps, s.api_budget_seconds, s.api_budget_usd, settings,
                               badges=lambda class_type: (schemas.get(class_type) or {}).get('price_badge'), takes=high, takes_low=low)
    except Exception as error:  # the pack could not be read or priced the plan: nothing is paid before someone looks at it
        text = f'The cost of the plan could not be estimated ({type(error).__name__}: {error}). Check the VideoTools pack, then approve to run it with the budget of the settings.'
        return {'generator': s.video_model, 'title': s.video_model, 'seconds': None, 'seconds_high': None, 'usd_low': None, 'usd_high': None, 'takes': high,
                'budget_seconds': s.api_budget_seconds, 'budget_usd': s.api_budget_usd, 'over_budget': True, 'stops_at': 1, 'text': text, 'approved': False, 'unknown': True}
    return {'generator': found.generator, 'title': found.title, 'seconds': round(found.seconds, 2), 'seconds_high': round(found.seconds_high, 2), 'takes': found.takes,
            'usd_low': None if found.price is None else round(found.price.low, 2), 'usd_high': None if found.price is None else round(found.price.high, 2),
            'budget_seconds': found.budget_seconds, 'budget_usd': found.budget_usd, 'over_budget': found.over_budget, 'stops_at': found.stops_at, 'text': found.text, 'approved': False}


def approve(cost: dict) -> dict:
    """The cost once the user approved it: the amounts on the screen become the cap of the job (never no cap)."""
    return {**cost, 'approved': True, 'approved_seconds': cost.get('approved_seconds', cost.get('seconds_high')), 'approved_usd': cost.get('approved_usd', cost.get('usd_high'))}


def still_approved(previous: dict | None, cost: dict) -> bool:
    """A plan made again (or resumed) keeps the approval of the one before only when it asks for no more than what was approved."""
    if not previous or not previous.get('approved'):
        return False
    if cost.get('unknown'):
        return bool(previous.get('unknown'))  # still no estimate: the approval was given knowing that
    seconds = previous.get('approved_seconds', previous.get('seconds_high', previous.get('seconds')))
    if seconds is None or (cost.get('seconds_high') or 0) > seconds + 1e-6:
        return False
    usd = previous.get('approved_usd', previous.get('usd_high'))
    return usd is None or cost.get('usd_high') is None or cost['usd_high'] <= usd + 1e-6


def caps(settings, cost: dict | None) -> tuple[int, float]:
    """The budgets a shot prompt is sent with (Generator Select of the template). Before an approval: the settings. After: the approved amounts with a
    small margin (a take rounded up by the model), never below the settings and never 0 (no limit) unless the settings say no limit.
    A dollar figure that was approved without a price (no badge) cannot be checked by the pack, so the cap then holds on the seconds."""
    seconds, usd = settings.api_budget_seconds, settings.api_budget_usd
    if not cost or not cost.get('approved') or cost.get('unknown'):
        return seconds, usd
    approved_s, approved_usd = cost.get('approved_seconds'), cost.get('approved_usd')
    if seconds > 0:
        seconds = max(seconds, math.ceil((approved_s or 0) * 1.05) + 1) if approved_s is not None else seconds
    if usd > 0:
        usd = max(usd, round((approved_usd or 0) * 1.05, 2)) if approved_usd is not None else 0.0
        if approved_usd is None and seconds == 0 and approved_s is not None:
            seconds = math.ceil(approved_s * 1.05) + 1  # the dollars cannot be checked: the seconds that were approved hold instead
    return seconds, usd


AVERAGE_SHOT = 3.0  # seconds: before the plan exists, an edit of N seconds is counted as N / 3 shots, each rounded up the way the model rounds it


def estimate_models(mode: str, seconds: float, schemas: dict, *, ratio: str = '9:16', resolution: str = '720p', refs: int = 1, ref_video: bool = False,
                    music: bool = False, fps: float = 24.0) -> list[dict]:
    """What an edit of `seconds` costs with each model offered for the mode, before any plan: the card of the model picker. Local models cost nothing here.
    The plan shows the exact figure (the shots it really has); this one counts average shots, so it is said to be about."""
    from .models import JobRequest
    shots = max(1, math.ceil(max(1.0, seconds) / AVERAGE_SHOT))
    frames = [max(1, round(min(AVERAGE_SHOT, max(1.0, seconds)) * fps))] * shots
    rows = []
    for model in describe_models(mode):
        row = {**model, 'seconds': None, 'seconds_high': None, 'usd_low': None, 'usd_high': None, 'text': ''}
        if model['source'] == 'api':
            request = JobRequest(mode=mode, settings={'prompt': 'estimate', 'video_model': model['id'], 'ratio': ratio, 'api_resolution': resolution, 'music_sync': music}, refs=[f'r{i}' for i in range(max(0, refs))],
                                 **({'ref_video': 'v'} if ref_video else {}))
            cost = plan_cost(request, frames, schemas, fps)
            if cost:
                row.update(seconds=cost['seconds'], seconds_high=cost.get('seconds_high'), usd_low=cost['usd_low'], usd_high=cost['usd_high'], text=cost['text'])
        rows.append(row)
    return rows


def shot_frames_of(shots, fps: float = 24.0) -> list[int]:
    """The frames of the shots that a model generates (the others are made here from the sources): what the plan asks of the generator, or the shot's own length."""
    return [s.generation_frames or max(1, math.ceil(s.duration * fps)) for s in shots if s.render_source == 'generated']
