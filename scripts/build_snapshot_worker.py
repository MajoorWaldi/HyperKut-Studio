"""Build a minimal worker pack from explicit source files, never runtime media."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

BACKEND = ('artifact_contract.py','artifact_store.py','artifact_bundle.py','project_snapshot.py',
           'snapshot_schema.py','snapshot_worker.py','storage.py')
CORE = ('__init__.py','models.py','errors.py','fingerprints.py','timeline.py','timeline_edit.py','editorial_graph.py')


def build(target):
    studio = Path(__file__).resolve().parents[1]
    target = Path(target)
    if target.exists():
        raise ValueError('Worker build target already exists; choose a fresh directory')
    target.mkdir(parents=True)
    shutil.copy2(studio/'experimental/comfyui_snapshot_worker/__init__.py', target/'__init__.py')
    for package in ('runtime','runtime/studio','runtime/studio/backend','runtime/core'):
        path = target/package
        path.mkdir(parents=True, exist_ok=True)
        (path/'__init__.py').write_text('', encoding='utf-8')
    for name in BACKEND:
        shutil.copy2(studio/'backend'/name, target/'runtime/studio/backend'/name)
    for name in CORE:
        shutil.copy2(studio.parent/'core'/name, target/'runtime/core'/name)
    shutil.copy2(studio/'LICENSE', target/'LICENSE')
    (target/'README.md').write_text('Experimental HyperKut snapshot transport worker. Tested with ComfyUI 0.42.5 and 0.43.0.\nStandalone CPU Transform supports verify and set_prompt (generation=false).\nGraph transport v2 provides Workspace, SnapshotImport, SnapshotExport and WorkspaceRelease for native VideoTools workflows. H3 and music generation require their separately installed nodes and weights.\nIncludes MIT-licensed HyperKut Studio and VideoTools core source. No models or media bundled.\n', encoding='utf-8')
    (target/'requirements.txt').write_text('filelock>=3.16,<4\n', encoding='utf-8')
    hashes = {p.relative_to(target).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
              for p in target.rglob('*') if p.is_file()}
    (target/'build-manifest.json').write_text(json.dumps({'protocol':1,'generation':False,'graph_transport':2,'files':hashes}, indent=2), encoding='utf-8')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('target')
    print(build(parser.parse_args().target))
