"""Measure the planner: the same ten briefs, the checks of the pack on what it wrote, a report to compare before and after a change of its prompt.

    python scripts/planner_eval.py --plans plans/             check plans that were saved (<brief id>.json): no model, no GPU
    python scripts/planner_eval.py --run [--runs 3]           ask the planner of the ComfyUI that runs for each brief (the language model generates: not while the GPU is busy)

The report is written to workspace/planner_eval.json and printed as one line per brief."""
import argparse
import json
import hashlib
import sys
import time
import types
import uuid
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
PACK = APP.parent
BRIEFS = PACK / "tests" / "fixtures" / "planner_briefs.json"

package = types.ModuleType("majoor_videotools")  # the checks are plain Python: the pack is read as a package without starting ComfyUI
package.__path__ = [str(PACK)]
sys.modules.setdefault("majoor_videotools", package)


def evaluate(briefs: list[dict], plans: dict[str, list[str]]) -> list[dict]:
    """For each brief, the issues of each plan that was written for it: [{"id", "runs", "errors", "warnings", "codes", "issues"}]."""
    from majoor_videotools.core.plan_checks import check_plan, summarize
    report = []
    for brief in briefs:
        found = [check_plan(text, duration=brief["duration"], density=brief["cut_density"], text_allowed=brief["text_allowed"]) for text in plans.get(brief["id"], [])]
        summaries = [summarize(issues) for issues in found]
        report.append({"id": brief["id"], "runs": len(found), "errors": sum(s["errors"] for s in summaries), "warnings": sum(s["warnings"] for s in summaries),
                       "codes": sorted({c for s in summaries for c in s["codes"]}), "issues": found})
    return report


def wait_plan(client, comfy: str, prompt_id: str, timeout: float = 300, poll: float = 2) -> str:
    """Read only this request; on deadline remove/interrupt only this request."""
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            response = client.get(f'{comfy}/history/{prompt_id}')
            response.raise_for_status()
            result = response.json().get(prompt_id)
            if result:
                status = result.get('status', {})
                if status.get('status_str') == 'error':
                    raise RuntimeError(f'Planner failed: {status.get("messages", [])}')
                if status.get('completed') is True:
                    text = result.get('outputs', {}).get('raw', {}).get('text')
                    if not isinstance(text, list) or not text or not isinstance(text[0], str):
                        raise RuntimeError('Planner completed without a text output')
                    return text[0]
            time.sleep(poll)
        raise TimeoutError(f'Planner request exceeded {timeout:g} seconds')
    except (Exception, KeyboardInterrupt):
        # There is no global interrupt: unrelated work must remain untouched.
        for route, body in (('queue', {'delete': [prompt_id]}), ('interrupt', {'prompt_id': prompt_id})):
            try:
                client.post(f'{comfy}/{route}', json=body).raise_for_status()
            except Exception:
                pass  # preserve the original timeout/interrupt; id is printed by caller
        raise


def ask_planner(brief: dict, comfy: str, *, seed: int = 42, timeout: float = 300) -> str:
    """One plan from the planner of a running ComfyUI, with the settings of the brief (this is a generation)."""
    import httpx

    sys.path.insert(0, str(APP))
    from backend.jobs import Job
    from backend.models import JobRequest
    from backend.runner import ComfyRunner
    from backend.templates import load_templates
    from backend.direction import apply_plan_contract, normalize_media_roles

    settings = {"prompt": brief["brief"], "duration": brief["duration"], "style": brief["style"], "cut_density": brief["cut_density"], "text_allowed": brief["text_allowed"], "text": True,
                "ratio": "9:16", "audio": "new", "seed": seed}
    runner = ComfyRunner.__new__(ComfyRunner)
    runner.uploads = {}
    values = runner._values(Job(JobRequest(mode="text", settings=settings)))
    template = load_templates(APP / "workflows", "text")["stage1"]
    absent = tuple(name for name in ("ref1", "ref2", "ref3", "ref4", "ref5", "ref_video", "voice", "energy_reference") if name in template.slots)
    prompt = template.fill({k: v for k, v in values.items() if k in template.slots and not isinstance(v, Path)}, absent)
    normalize_media_roles(prompt)
    apply_plan_contract(prompt, JobRequest(mode="text", settings=settings).settings)
    planner = next(k for k, n in prompt.items() if n["class_type"] == "TextGenerate" and isinstance(n["inputs"].get("system_prompt"), list)
                   and prompt[str(n["inputs"]["system_prompt"][0])]["inputs"].get("skill") == "timeline_planner")
    keep: dict = {}

    def walk(node_id: str) -> None:
        if node_id in keep or node_id not in prompt:
            return
        keep[node_id] = prompt[node_id]
        for value in prompt[node_id]["inputs"].values():
            if isinstance(value, list):
                walk(str(value[0]))

    walk(planner)
    for node in keep.values():
        if node['class_type'] == 'TextGenerate':
            node['inputs']['sampling_mode.seed'] = seed
    keep["raw"] = {"class_type": "PreviewAny", "inputs": {"source": [planner, 0]}}
    with httpx.Client(timeout=min(30, timeout)) as client:
        queue = client.get(f'{comfy}/queue')
        queue.raise_for_status()
        if queue.json().get('queue_running') or queue.json().get('queue_pending'):
            raise RuntimeError('GPU queue is busy; planner benchmark was not submitted')
        # Never retry an uncertain submission automatically.
        response = client.post(f"{comfy}/prompt", json={"prompt": keep, "client_id": str(uuid.uuid4())})
        response.raise_for_status()
        prompt_id = response.json()['prompt_id']
        print(f'planner request {prompt_id}, seed {seed}', flush=True)
        return wait_plan(client, comfy, prompt_id, timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plans", type=Path, help="a folder of saved plans, <brief id>.json (or <brief id>.<n>.json for several)")
    parser.add_argument("--run", action="store_true", help="ask the planner of the running ComfyUI (a generation)")
    parser.add_argument("--runs", type=int, default=1, help="plans per brief with --run")
    parser.add_argument("--comfy", default="http://127.0.0.1:8188")
    parser.add_argument("--only", help="one brief id")
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--timeout', type=float, default=300)
    parser.add_argument('--output', type=Path, default=APP / 'workspace' / 'planner_eval.json')
    parser.add_argument('--extended', action='store_true', help='include continuity and micro-cut cases')
    args = parser.parse_args()
    if not 1 <= args.runs <= 3 or not 10 <= args.timeout <= 900:
        parser.error('--runs must be 1..3 and --timeout 10..900 seconds')
    briefs = json.loads(BRIEFS.read_text(encoding='utf-8'))
    if args.extended:
        briefs += json.loads(BRIEFS.with_name('planner_extended_briefs.json').read_text(encoding='utf-8'))
    briefs = [b for b in briefs if not args.only or b['id'] == args.only]
    if not briefs:
        parser.error('no matching brief')
    if bool(args.plans) == args.run:
        parser.error("give --plans <folder> or --run")
    started = time.monotonic()
    plans: dict[str, list[str]] = {}
    runs = []
    if args.plans:
        for brief in briefs:
            plans[brief["id"]] = [f.read_text(encoding="utf-8") for f in sorted(args.plans.glob(f"{brief['id']}*.json"))]
    else:
        saved = APP / "workspace" / "planner_plans"
        saved.mkdir(parents=True, exist_ok=True)
        for brief in briefs:
            plans[brief["id"]] = []
            for n in range(args.runs):
                seed = args.seed + n
                run_start = time.monotonic()
                text = ask_planner(brief, args.comfy, seed=seed, timeout=args.timeout)
                runs.append({'brief_id': brief['id'], 'seed': seed, 'seconds': round(time.monotonic() - run_start, 3), 'brief': brief})
                (saved / f"{brief['id']}.{n + 1}.json").write_text(text, encoding="utf-8")
                plans[brief["id"]].append(text)
    report = evaluate(briefs, plans)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding='utf-8')
    fingerprints = {}
    for path in [BRIEFS, APP / 'backend' / 'direction.py', APP / 'backend' / 'runner.py', Path(__file__), *sorted((PACK / 'examples' / 'prompts').glob('*.txt')), *sorted((APP / 'workflows' / 'text').glob('*.json'))]:
        fingerprints[str(path.relative_to(PACK))] = hashlib.sha256(path.read_bytes()).hexdigest()
    args.output.with_suffix('.metadata.json').write_text(json.dumps({'seed_base': args.seed, 'runs': runs,
        'source': 'live_planner' if args.run else 'saved_plans_unknown_generation_seed',
        'seconds': round(time.monotonic() - started, 3), 'fingerprints': fingerprints}, indent=2), encoding='utf-8')
    for row in report:
        print(f"{row['id']:18s} plans {row['runs']}  errors {row['errors']}  warnings {row['warnings']}  {', '.join(row['codes'])}")
    print(f"total: {sum(r['errors'] for r in report)} errors, {sum(r['warnings'] for r in report)} warnings in {sum(r['runs'] for r in report)} plans")
    return 0


if __name__ == "__main__":
    sys.exit(main())
