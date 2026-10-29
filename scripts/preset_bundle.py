"""Offline, rights-gated preset bundles. Never exports the whole workspace.

Build: python scripts/preset_bundle.py build --rights rights.json --output bundle
Install BEFORE first start: python scripts/preset_bundle.py install --bundle bundle
Only a fresh workspace is accepted. Existing projects/uploads are never merged.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = {'image': {'.png', '.jpg', '.jpeg', '.webp', '.gif'},
            'video': {'.mp4', '.webm', '.mov'},
            'audio': {'.wav', '.mp3', '.flac', '.ogg', '.m4a'}}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.next')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def child(root, relative):
    if not isinstance(relative, str) or '\\' in relative or ':' in relative:
        raise ValueError('Invalid bundle path')
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve() or not path.is_file():
        raise ValueError('Missing asset or bundle path escapes its root')
    return path


def build(studio, rights_path, output):
    studio, output = Path(studio), Path(output)
    if output.exists():
        raise ValueError('Output must be a new directory')
    rights = read(rights_path).get('assets', {})
    names_path = studio / 'workspace/uploads.json'
    names = read(names_path) if names_path.is_file() else {}
    assets, presets, withheld = {}, {}, []
    sources = {}

    def convert(item, slot, preset):
        if item is None:
            return None
        uid = item.get('id')
        matches = list((studio / 'workspace/uploads').glob(str(uid) + '.*')) if isinstance(uid, str) and uid.isalnum() else []
        if len(matches) != 1:
            withheld.append({'preset': preset, 'slot': slot, 'reason': 'missing upload'})
            return None
        source = matches[0]
        sha = digest(source)
        grant = rights.get(sha, {})
        kind = item.get('kind')
        if (grant.get('redistribute') is not True or not grant.get('evidence')
                or not grant.get('license') or kind not in SUFFIXES
                or source.suffix.lower() not in SUFFIXES.get(kind, set())):
            withheld.append({'preset': preset, 'slot': slot, 'sha256': sha, 'reason': 'redistribution not cleared'})
            return None
        key = sha[:24]
        relative = f'assets/{sha}{source.suffix.lower()}'
        original_name = names.get(uid, {})
        original_name = original_name.get('name', source.name) if isinstance(original_name, dict) else original_name
        record = {'file': relative, 'sha256': sha, 'kind': kind,
                  'name': grant.get('public_name') or original_name or source.name,
                  'license': grant['license'], 'evidence': grant['evidence']}
        if key in assets and assets[key]['sha256'] != sha:
            raise ValueError('Asset ID collision')
        assets[key], sources[key] = record, source
        return {'id': key, 'name': record['name'], 'kind': kind, 'url': f'/api/uploads/{key}'}

    for path in sorted((studio / 'presets').glob('*.json')):
        preset = copy.deepcopy(read(path))
        old = preset.get('inputs') or {}
        preset['inputs'] = {key: convert(old.get(key), key, path.stem)
                            for key in ('source', 'refVideo', 'music', 'voice')}
        preset['inputs']['refs'] = [convert(item, f'reference {i+1}', path.stem)
                                    for i, item in enumerate(old.get('refs', [])[:5])]
        for key in ('preview', 'reference', 'source_job', 'missing_inputs'):
            preset.pop(key, None)
        # Outputs have separate H3/source-media rights. Never infer clearance from input ownership.
        presets[path.stem] = preset
    output.mkdir(parents=True)
    for key, record in assets.items():
        target = output / record['file']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sources[key], target)
    for key, preset in presets.items():
        write(output / 'presets' / f'{key}.json', preset)
    manifest = {'version': 1, 'assets': assets, 'presets': [f'presets/{key}.json' for key in presets],
                'withheld': withheld, 'previews': 'Excluded pending separate output and source-media clearance'}
    write(output / 'manifest.json', manifest)
    return manifest


def validate(bundle):
    bundle = Path(bundle).resolve()
    manifest = read(bundle / 'manifest.json')
    if manifest.get('version') != 1:
        raise ValueError('Unsupported bundle version')
    assets = manifest.get('assets', {})
    for uid, item in assets.items():
        if not isinstance(uid, str) or not uid.isalnum() or not isinstance(item, dict):
            raise ValueError('Invalid asset ID')
        source = child(bundle, item['file'])
        if source.stat().st_size > 512 * 1024 * 1024:
            raise ValueError('Asset exceeds 512 MB')
        if item.get('kind') not in SUFFIXES or source.suffix.lower() not in SUFFIXES[item['kind']]:
            raise ValueError('Unsupported media kind')
        if digest(source) != item.get('sha256') or uid != item['sha256'][:24]:
            raise ValueError('Asset SHA-256 mismatch')
        if not item.get('license') or not item.get('evidence'):
            raise ValueError('Missing rights record')
    presets = []
    for relative in manifest.get('presets', []):
        path = child(bundle, relative)
        if path.suffix != '.json' or path.parent != bundle / 'presets':
            raise ValueError('Invalid preset path')
        preset = read(path)
        inputs = preset.get('inputs') or {}
        for item in [inputs.get(k) for k in ('source', 'refVideo', 'music', 'voice')] + inputs.get('refs', []):
            if item is not None and (item.get('id') not in assets or item.get('kind') != assets[item['id']]['kind']):
                raise ValueError('Preset references an unbundled asset')
        presets.append((path.name, preset))
    return manifest, presets


def install(bundle, studio, verify_only=False):
    bundle, studio = Path(bundle).resolve(), Path(studio).resolve()
    manifest, presets = validate(bundle)  # Validate every byte/path BEFORE changing the destination.
    workspace = studio / 'workspace'
    if workspace.exists() and any(workspace.iterdir()):
        raise ValueError('Fresh workspace required; existing projects/uploads are never overwritten')
    if not (studio / 'backend/server.py').is_file():
        raise ValueError('Not a Studio source directory')
    if verify_only:
        return manifest
    uploads = workspace / 'uploads'
    uploads.mkdir(parents=True, exist_ok=True)
    names = {}
    for uid, item in manifest['assets'].items():
        source = child(bundle, item['file'])
        shutil.copy2(source, uploads / f'{uid}{source.suffix.lower()}')
        names[uid] = {'kind': item['kind'], 'name': item['name']}
    write(workspace / 'uploads.json', names)
    for name, preset in presets:
        write(studio / 'presets' / name, preset)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'install', 'verify'])
    parser.add_argument('--studio-root', type=Path, default=ROOT)
    parser.add_argument('--rights', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--bundle', type=Path)
    args = parser.parse_args()
    if args.action == 'build':
        if not args.rights or not args.output:
            parser.error('build requires --rights and --output')
        result = build(args.studio_root, args.rights, args.output)
    else:
        if not args.bundle:
            parser.error('install/verify requires --bundle')
        result = install(args.bundle, args.studio_root, verify_only=args.action == 'verify')
    print(json.dumps({'assets': len(result['assets']), 'presets': len(result['presets']),
                      'withheld': len(result.get('withheld', []))}))
