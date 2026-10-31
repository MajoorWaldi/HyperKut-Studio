"""Load the existing pure node schema without the Studio server or ComfyUI."""
from functools import lru_cache
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys


@lru_cache(maxsize=1)
def core():
    directory = Path(__file__).resolve().parents[2] / 'core'
    if not (directory/'timeline_edit.py').is_file():
        raise ValueError('Snapshot runtime requires the packaged VideoTools core schema')
    name = 'hyperkut_snapshot_core_' + hashlib.sha256(str(directory).encode()).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(name, directory/'__init__.py', submodule_search_locations=[str(directory)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    spec.loader.exec_module(package)
    return importlib.import_module(name+'.models'), importlib.import_module(name+'.timeline_edit'), importlib.import_module(name+'.errors')


def motion_contract():
    models, _, _ = core()
    return importlib.import_module(models.__package__ + '.motion_contract')


def motion_library():
    models, _, _ = core()
    return importlib.import_module(models.__package__ + '.motion_library')


def shot_list(manifest):
    models, _, errors = core()
    try:
        return models.ShotList.from_dict(manifest)
    except errors.MajoorError as error:
        raise ValueError(str(error)) from error


def checked_document(manifest, document):
    _, edits, errors = core()
    try:
        return edits.parse_document(shot_list(manifest), json.dumps(document, allow_nan=False))
    except errors.MajoorError as error:
        raise ValueError(str(error)) from error
