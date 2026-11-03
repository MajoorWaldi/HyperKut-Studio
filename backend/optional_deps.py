"""Optional models and nodes must never stop a generation.

ComfyUI refuses a whole prompt when one node of it names a file it does not have or a node it does not know, even in a branch that a switch never takes. The Studio graphs
carry three such branches (the Pika H3 Flex LoRA, the pose control of H3, the location plates of FLUX). When the schemas of ComfyUI say that something one of them needs is
missing, the branch is cut out of the prompt before it is sent; the shots then come out the way they do without the option. A branch is never cut when everything it needs is there,
so an installation that has all the files gets the graph as it is."""
import copy

FLEX_PREFIX = "pika_h3_flex"


def _choices(schemas: dict, class_type: str, field: str):
    """The files ComfyUI lists for a combo input, or None when the schema does not say (then nothing is cut)."""
    spec = {**schemas.get(class_type, {}).get("input", {}).get("required", {}), **schemas.get(class_type, {}).get("input", {}).get("optional", {})}.get(field)
    if not spec:
        return None
    first = spec[0]
    if isinstance(first, list):
        return first
    options = spec[1].get("options") if len(spec) > 1 and isinstance(spec[1], dict) else None
    return options if isinstance(options, list) else None


_FILE_FIELDS = ("unet_name", "lora_name", "clip_name", "vae_name", "name", "ckpt_name", "bbox_detector", "pose_estimator")


def _missing(prompt: dict, schemas: dict, ids) -> list[str]:
    """What the nodes `ids` need and ComfyUI does not have: unknown node types and files that are not in the list of their loader."""
    found = []
    for key in ids:
        node = prompt[key]
        if node["class_type"] not in schemas:
            found.append(node["class_type"])
            continue
        for field in _FILE_FIELDS:
            value = node["inputs"].get(field)
            options = _choices(schemas, node["class_type"], field) if isinstance(value, str) else None
            if options is not None and value not in options:
                found.append(value)
    return found


def _ancestors(prompt: dict, start: str) -> set[str]:
    seen, pending = set(), [start]
    while pending:
        key = pending.pop()
        if key in seen or key not in prompt:
            continue
        seen.add(key)
        pending.extend(str(v[0]) for v in prompt[key]["inputs"].values() if isinstance(v, list))
    return seen


def _reroute(prompt: dict, old: str, new_link) -> None:
    """Every input that read the first output of `old` reads `new_link` instead."""
    for node in prompt.values():
        for field, value in node["inputs"].items():
            if isinstance(value, list) and str(value[0]) == old and value[1] == 0:
                node["inputs"][field] = copy.deepcopy(new_link)


def _switch_off(prompt: dict, switch: str) -> None:
    """The boolean that drives a switch is set to False when it is a plain value."""
    link = prompt[switch]["inputs"].get("switch")
    if isinstance(link, list) and str(link[0]) in prompt and "value" in prompt[str(link[0])]["inputs"]:
        prompt[str(link[0])]["inputs"]["value"] = False


def prune_unavailable(prompt: dict, schemas: dict, *, flex: bool = False, places: bool = False) -> list[str]:
    """Cut the optional branches whose models or nodes ComfyUI does not have, in place; the sentences to show the user (empty when nothing was cut).

    `schemas` is the object_info of ComfyUI; an empty one (ComfyUI could not be asked) cuts nothing."""
    if not schemas:
        return []
    notes = []

    # Pika H3 Flex: the LoRA is only read when the option is on, but ComfyUI checks its file anyway.
    for key, node in list(prompt.items()):
        if node["class_type"] == "LoraLoaderModelOnly" and str(node["inputs"].get("lora_name", "")).startswith(FLEX_PREFIX) and _missing(prompt, schemas, [key]):
            for switch_key, switch in prompt.items():
                if switch["class_type"] == "ComfySwitchNode" and switch["inputs"].get("on_true") == [key, 0]:
                    del switch["inputs"]["on_true"]
                    _switch_off(prompt, switch_key)
            for other in prompt.values():
                for field in [f for f, v in other["inputs"].items() if isinstance(v, list) and str(v[0]) == key]:
                    del other["inputs"][field]
            if flex:
                notes.append("The Pika H3 Flex LoRA is not installed: the shots were made with the turbo LoRA.")

    # Pose control of H3 at strength 0: the patch file, the pose detector and the depth node are not needed to make a shot.
    for key, node in list(prompt.items()):
        if node["class_type"] == "MiniMaxH3FunControlNetApply" and node["inputs"].get("strength") == 0 and isinstance(node["inputs"].get("model"), list):
            needs = [k for k in _ancestors(prompt, key) if k != key and k != str(node["inputs"]["model"][0]) and k not in _ancestors(prompt, str(node["inputs"]["model"][0]))]
            if _missing(prompt, schemas, needs):
                _reroute(prompt, key, node["inputs"]["model"])
                del prompt[key]

    # Location plates (FLUX): the images of the places are a help, not a need.
    for key, node in list(prompt.items()):
        if node["class_type"] != "MajoorCheckPlate":
            continue
        gone = _missing(prompt, schemas, _ancestors(prompt, key))
        if not gone:
            continue
        for switch_key, switch in prompt.items():
            if switch["class_type"] == "ComfySwitchNode" and switch["inputs"].get("on_true") == [key, 0]:
                del switch["inputs"]["on_true"]
                _switch_off(prompt, switch_key)
        for other_key, other in prompt.items():
            if other_key != key:
                for field in [f for f, v in other["inputs"].items() if isinstance(v, list) and str(v[0]) == key]:
                    del other["inputs"][field]
        if places:
            notes.append("The location images need FLUX files that are not installed (" + ", ".join(sorted(set(gone))) + "): the shots were made without them.")

    # The plan of a remix needs a pack loaded after it was added: an older ComfyUI keeps the shots as detected.
    for key, node in list(prompt.items()):
        if node["class_type"] == "MajoorRemixPlan" and node["class_type"] not in schemas and isinstance(node["inputs"].get("shot_list"), list):
            _reroute(prompt, key, node["inputs"]["shot_list"])
            del prompt[key]
            notes.append("ComfyUI has not loaded the Remix Plan node yet (restart ComfyUI): the remix was made without its story, people and kept shots.")

    # Generated music (YuE2): the edit needs a beat grid, not the song; without the music model it is made on silence and the user is told.
    for key, node in list(prompt.items()):
        source = node["inputs"].get("music")
        if node["class_type"] != "MajoorMusicFit" or not isinstance(source, list) or str(source[0]) not in prompt:
            continue
        needs = [k for k in _ancestors(prompt, str(source[0])) if prompt[k]["class_type"] in ("CheckpointLoaderSimple",) or prompt[k]["class_type"].startswith(("YuE2", "EmptyYuE2", "MajoorYuE2"))]
        gone = _missing(prompt, schemas, needs)
        if gone and "EmptyAudio" in schemas:
            prompt["OPT_SILENCE"] = {"class_type": "EmptyAudio", "inputs": {"duration": node["inputs"].get("length", 8.0), "sample_rate": 44100, "channels": 2}, "_meta": {"title": "NO MUSIC MODEL: silence"}}
            node["inputs"]["music"] = ["OPT_SILENCE", 0]
            notes.append("The music model is not installed (" + ", ".join(sorted(set(gone))) + "): the edit was cut on a steady grid and has no generated music.")
    return notes
