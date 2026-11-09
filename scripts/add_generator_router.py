"""Give the API templates of Text and Music (workflows/<mode>/*.api.json) the video model choice of the Creative workflows of ComfyUI-Majoor-VideoTools.

These templates are exported from graphs that have been edited since (casting, shot memory, camera moves...): they are patched here instead of exported
again, so nothing they hold is lost. What is added, as in scripts/add_generator_router.py of the pack:
  stage1 and shot  a Generator Select ("GS": the model and the budgets), Create Timeline plans for it (its `generator` input);
  shot             per take (the first and the retry): a Generate Shot (API) node beside the H3 nodes, and three lazy switches (images, audio, fps) that give the Create Video
                   of the take the H3 output or the API one, so only the model that is chosen runs and is paid for; the prompt writer of the shot reads the model;
  slots.json       video_model, api_budget_seconds, api_budget_usd (stage1 and shot), api_resolution, api_ratio (shot), and the seeds of the API takes.
Remix keeps H3 only. Run it from the root of the Studio:

    python scripts/add_generator_router.py

Idempotent: a template that already has a Generate Shot node is left as it is. The files are written the way they are kept: compact JSON."""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODES = ("text", "music")
H3 = "MiniMaxH3ReferenceToVideo"
GS, IS, FPS = "GS", "GIS", "H3FPS"
IMAGES = 9


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="")


def node(class_type: str, title: str, **inputs) -> dict:
    return {"class_type": class_type, "inputs": inputs, "_meta": {"title": title}}


def select() -> dict:
    return node("MajoorGeneratorSelect", "VIDEO MODEL (H3 local, or an API model)", generator="minimax_h3", max_api_seconds=120, max_api_usd=0.0)


def patch_shot(shot: dict, slots: dict, rng: random.Random) -> None:
    h3s = sorted((i for i, n in shot.items() if n["class_type"] == H3), key=lambda i: (len(i), i))
    if len(h3s) != 2:
        raise SystemExit(f"expected two H3 nodes (the take and the retry), found {h3s}")
    shot[GS] = select()
    shot[IS] = node("MajoorGeneratorIs", "H3 MODEL? (else the API branch)", generator=[GS, 0], **{"is": "minimax_h3"})
    shot[FPS] = node("PrimitiveFloat", "H3 fps", value=24.0)
    api_ids = []
    for k, h3_id in enumerate(h3s, 1):
        prefix = h3_id.rsplit(":", 1)[0]  # the sub-graph instance of the take: 109 for the first, 127 for the retry
        h3 = shot[h3_id]["inputs"]
        take = next(n for n in shot.values() if n["class_type"] == "CreateVideo" and isinstance(n["inputs"].get("images"), list) and str(n["inputs"]["images"][0]).startswith(prefix + ":"))
        wiring = {"generator": [GS, 0], "prompt": shot[f"{prefix}:165"]["inputs"]["value"], "seconds": shot[f"{prefix}:160"]["inputs"]["value"],
                  "aspect_ratio": "9:16", "resolution": "720p", "generate_audio": True, "seed": rng.randrange(1, 2**31), "reference_fps": 24.0}
        for i in range(IMAGES):
            if h3.get(f"ref_images.ref_image_{i}") is not None:
                wiring[f"image_{i + 1}"] = h3[f"ref_images.ref_image_{i}"]
        if isinstance(wiring["prompt"], str):
            raise SystemExit("the prompt of the take is not wired")
        for mine, theirs in (("reference_frames", "ref_videos.ref_video_0"), ("reference_audio", "ref_audios.ref_audio_0")):
            if h3.get(theirs) is not None:
                wiring[mine] = h3[theirs]
        api_id = f"AG{k}"
        api_ids.append(api_id)
        label = "API · generates the shot" if k == 1 else "API · again with another seed"
        shot[api_id] = node("MajoorGenerateShot", label, **wiring)
        images, audio = take["inputs"]["images"], take["inputs"]["audio"]
        for name, slot, h3_side, field in (("images", 0, images, "images"), ("audio", 1, audio, "audio"), ("fps", 2, [FPS, 0], "fps")):
            sid = f"SW{k}_{name}"
            shot[sid] = node("ComfySwitchNode", f"{label.split(' · ')[1].upper()} · {name}", switch=[IS, 0], on_false=[api_id, slot], on_true=h3_side)
            take["inputs"][field] = [sid, 0]
    for n in shot.values():  # the prompt writer of the shot follows the model
        if n["class_type"] == "MajoorEditSkills" and n["inputs"].get("skill") == "h3_shot_prompt_from_plan":
            n["inputs"]["generator"] = [GS, 0]
    s = slots["shot"]
    s["video_model"], s["api_budget_seconds"], s["api_budget_usd"] = [[GS, "generator"]], [[GS, "max_api_seconds"]], [[GS, "max_api_usd"]]
    s["api_resolution"] = [[a, "resolution"] for a in api_ids]
    s["api_ratio"] = [[a, "aspect_ratio"] for a in api_ids]
    s["seed"] = [*s["seed"], [api_ids[0], "seed"]]
    s["seed_b"] = [*s["seed_b"], [api_ids[1], "seed"]]


def patch_stage1(stage1: dict, slots: dict) -> None:
    stage1[GS] = select()
    timelines = [n for n in stage1.values() if n["class_type"] == "MajoorCreateTimeline"]
    if not timelines:
        raise SystemExit("stage1 has no Create Timeline")
    for n in timelines:  # the plan (lengths, warnings) follows the model
        n["inputs"]["generator"] = [GS, 0]
    s = slots["stage1"]
    s["video_model"], s["api_budget_seconds"], s["api_budget_usd"] = [[GS, "generator"]], [[GS, "max_api_seconds"]], [[GS, "max_api_usd"]]


def patch(mode: str) -> bool:
    folder = ROOT / "workflows" / mode
    shot, stage1, slots = load(folder / "shot.api.json"), load(folder / "stage1.api.json"), load(folder / "slots.json")
    if any(n["class_type"] == "MajoorGenerateShot" for n in shot.values()):
        return False
    patch_shot(shot, slots, random.Random(7))
    patch_stage1(stage1, slots)
    for name, data in (("shot.api.json", shot), ("stage1.api.json", stage1), ("slots.json", slots)):
        save(folder / name, data)
    return True


if __name__ == "__main__":
    for mode in MODES:
        print(f"{mode}: {'router added' if patch(mode) else 'already has it'}")
    sys.exit(0)
