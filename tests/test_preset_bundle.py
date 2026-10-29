import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.runner import MockRunner
from backend.server import create_app

spec = importlib.util.spec_from_file_location('preset_bundle', Path(__file__).parents[1] / 'scripts/preset_bundle.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


def sample(tmp_path, cleared=True):
    source = tmp_path / 'source'
    (source / 'workspace/uploads').mkdir(parents=True)
    media = source / 'workspace/uploads/old123.wav'
    media.write_bytes(b'RIFF portable fixture')
    bundle.write(source / 'presets/music.json', {
        'name': 'Portable', 'mode': 'music', 'prompt': 'A journey', 'settings': {'seed': 42},
        'preview': 'private.mp4', 'source_job': 'private-job',
        'inputs': {'music': {'id': 'old123', 'kind': 'audio', 'url': '/api/uploads/old123'},
                   'refs': [None, None]}})
    rights = tmp_path / 'rights.json'
    bundle.write(rights, {'assets': {bundle.digest(media): {
        'redistribute': cleared, 'license': 'Test fixture', 'evidence': 'Synthetic test data'}}})
    destination = tmp_path / 'bundle'
    bundle.build(source, rights, destination)
    return destination


def fresh(tmp_path):
    studio = tmp_path / 'fresh'
    (studio / 'backend').mkdir(parents=True)
    (studio / 'backend/server.py').touch()
    return studio


def test_portable_music_resolves_through_actual_api_after_restart(tmp_path, monkeypatch):
    package = sample(tmp_path)
    studio = fresh(tmp_path)
    bundle.install(package, studio)
    import backend.server as server
    monkeypatch.setattr(server, 'ROOT', studio)
    settings = Settings('http://127.0.0.1:1', 'http://127.0.0.1:1', tmp_path / 'out',
                        studio / 'workspace', studio / 'workflows', True)
    for _ in range(2):
        with TestClient(create_app(settings, MockRunner())) as client:
            preset = client.get('/api/presets').json()[0]
            assert preset['missing_inputs'] == []
            assert preset['inputs']['refs'] == [None, None]
            assert client.get(preset['inputs']['music']['url']).content == b'RIFF portable fixture'
            assert preset['settings']['seed'] == 42
            assert 'source_job' not in preset and 'preview' not in preset


def test_uncleared_media_is_absent_not_a_broken_local_upload(tmp_path):
    package = sample(tmp_path, cleared=False)
    manifest, presets = bundle.validate(package)
    assert manifest['assets'] == {}
    assert presets[0][1]['inputs']['music'] is None
    assert manifest['withheld'][0]['reason'] == 'redistribution not cleared'
    assert not (package / 'assets').exists()


@pytest.mark.parametrize('attack', ['tamper', 'escape'])
def test_invalid_bundle_cannot_partially_write_workspace(tmp_path, attack):
    package = sample(tmp_path)
    studio = fresh(tmp_path)
    manifest = bundle.read(package / 'manifest.json')
    record = next(iter(manifest['assets'].values()))
    if attack == 'tamper':
        (package / record['file']).write_bytes(b'changed')
    else:
        outside = tmp_path / 'outside.wav'
        outside.write_bytes(b'RIFF portable fixture')
        record['file'] = '../outside.wav'
        bundle.write(package / 'manifest.json', manifest)
    with pytest.raises(ValueError):
        bundle.install(package, studio)
    assert not (studio / 'workspace').exists()


def test_installer_refuses_existing_workspace(tmp_path):
    package = sample(tmp_path)
    studio = fresh(tmp_path)
    (studio / 'workspace').mkdir()
    sentinel = studio / 'workspace/private.txt'
    sentinel.write_text('keep')
    with pytest.raises(ValueError, match='Fresh workspace'):
        bundle.install(package, studio)
    assert sentinel.read_text() == 'keep'
    assert not (studio / 'presets').exists()
