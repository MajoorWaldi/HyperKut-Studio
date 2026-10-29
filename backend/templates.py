"""The workflows of the app: API-format prompts exported from the SECATOR graphs, with named slots.

A mode has three templates (workflows/<mode>/): `stage1` (the plan, the music, the rhythm), `shot` (one shot, with its shot id as a slot) and `final` (the edit, the sound, the
effects, the save). `slots.json` names the places that the interface fills: {"stage1": {"idea": [["12", "value"]], ...}, "shot": {...}, "final": {...}}; a slot is a list of
[node id, input] because one value can go to several nodes (the seed of a shot goes to the two H3 of its block).
The prompts and the slots are written by scripts/export_templates.js from the graphs; the SDK has no named parameters, these are ours."""
import copy
import json
from dataclasses import dataclass
from pathlib import Path

PHASES = ("stage1", "shot", "final")


class TemplateError(Exception):
    pass


@dataclass(frozen=True)
class Template:
    prompt: dict
    slots: dict[str, tuple[tuple[str, str], ...]]

    def fill(self, values: dict, absent: tuple[str, ...] = ()) -> dict:
        """A copy of the prompt with every value put in its slots. A value that names no slot is an error (a typo would otherwise run the default).
        The nodes of the slots named in `absent` (a picture or a video that was not given) are taken out, with every input that was connected to them and every node that was
        only fed by them."""
        unknown = sorted((set(values) | set(absent)) - set(self.slots))
        if unknown:
            raise TemplateError(f"No slot named {unknown}: the slots are {sorted(self.slots)}")
        prompt = copy.deepcopy(self.prompt)
        for name, value in values.items():
            for node, field in self.slots[name]:
                if node not in prompt:
                    raise TemplateError(f"The slot '{name}' points at node {node}, which is not in the prompt")
                prompt[node]["inputs"][field] = value
        gone = {node for name in absent for node, _ in self.slots[name]}
        while True:  # a node whose connected inputs all came from removed nodes has nothing left to work on: it goes too (the frames of a video that was not given)
            orphans = {id_ for id_, node in prompt.items() if id_ not in gone and (links := [v for v in node["inputs"].values() if isinstance(v, list)])
                       and all(str(v[0]) in gone for v in links)}
            if not orphans:
                break
            gone |= orphans
        for node in gone:
            prompt.pop(node, None)
        for node in prompt.values():
            node["inputs"] = {field: value for field, value in node["inputs"].items() if not (isinstance(value, list) and str(value[0]) in gone)}
        for optional_id, optional in list(prompt.items()):
            source_enabled = optional['inputs'].get('source_layers_enabled', False)
            if isinstance(source_enabled, list):
                source_enabled = prompt.get(str(source_enabled[0]), {}).get('inputs', {}).get('value')
            if optional['class_type'] == 'MajoorHyperFrames' and optional['inputs'].get('enabled') is False and optional['inputs'].get('layers','[]').strip() in ('','[]') and source_enabled is False:
                source = optional['inputs']['video']
                for node in prompt.values():
                    for name, value in list(node['inputs'].items()):
                        if value == [optional_id, 0]:
                            node['inputs'][name] = copy.deepcopy(source)
                prompt.pop(optional_id)
        return prompt


EDIT_SLOTS = {"edit_effects": "effects", "edit_text": "text", "edit_sub_cuts": "sub_cuts", "edit_auto_sfx": "auto_sfx", "edit_shot_volume": "shot_volume", "edit_duck": "duck", "edit_music_volume": "music_volume"}


def applied_style(template: Template, values: dict) -> dict:
    """What the edit prompt really applies, for the controls of the interface: the value of each edit slot once the values are in, or the primitive that the input is linked to (a volume, for example)."""
    prompt = template.fill({k: v for k, v in values.items() if k in template.slots and not isinstance(v, Path)})
    found = {}
    for slot, name in EDIT_SLOTS.items():
        for node, field in template.slots.get(slot, ()):
            value = prompt.get(node, {}).get("inputs", {}).get(field)
            while isinstance(value, list):  # linked to a primitive: its own value
                value = prompt.get(str(value[0]), {}).get("inputs", {}).get("value")
            if isinstance(value, (bool, int, float)):
                found[name] = value if isinstance(value, bool) else float(value) if name in ("shot_volume", "duck", "music_volume") else value
                break
    return found


def load_templates(directory: Path, mode: str) -> dict[str, Template]:
    folder = directory / mode
    slots_file = folder / "slots.json"
    if not slots_file.is_file():
        raise TemplateError(f"The workflows of the mode '{mode}' are not exported yet ({slots_file} is missing): run scripts/export_templates.js")
    slots = json.loads(slots_file.read_text(encoding="utf-8"))
    templates = {}
    for phase in (*PHASES,*(('local',) if (folder/'local.api.json').is_file() else ())):
        file = folder / f"{phase}.api.json"
        if not file.is_file():
            raise TemplateError(f"{file} is missing")
        templates[phase] = Template(json.loads(file.read_text(encoding="utf-8")), {name: tuple((str(n), str(f)) for n, f in targets) for name, targets in slots.get(phase, {}).items()})
    return templates
