from fastapi.testclient import TestClient
from backend.server import create_app
from backend.runner import MockRunner
from test_audit_regressions import settings


def test_preset_translations_survive_save_reload_and_reimport(tmp_path):
    config = settings(tmp_path)
    body = {'name': 'Roundtrip', 'mode': 'text', 'prompt': 'A bottle', 'settings': {'quality': 'max'},
            'translations': {'fr': {'name': 'Aller retour', 'description': 'Un produit', 'prompt': 'Un flacon', 'settings': {'mood': 'Calme'}}}}
    with TestClient(create_app(config, MockRunner())) as client:
        saved = client.post('/api/presets', json=body)
        assert saved.status_code == 200
    with TestClient(create_app(config, MockRunner())) as client:
        preset = next(p for p in client.get('/api/presets').json() if p['name'] == 'Roundtrip')
        assert preset['translations']['fr']['prompt'] == 'Un flacon'
        assert preset['settings']['quality'] == 'max'
        assert client.post('/api/presets', json=preset).json()['translations'] == saved.json()['translations']


def test_music_preset_references_and_track_survive_project_reopen(tmp_path):
    import io
    from PIL import Image
    from test_backend import _settings
    config = _settings(tmp_path, mock=True)
    picture = io.BytesIO()
    Image.new('RGB', (16, 16)).save(picture, format='PNG')
    with TestClient(create_app(config, MockRunner(pace=.001, shots=2))) as client:
        preset = client.post('/api/presets', json={'name': 'Music journey', 'mode': 'music', 'prompt': 'Product reveal', 'settings': {'quality': 'max'}}).json()
        refs = [client.post('/api/uploads', files={'file': (f'ref-{i}.png', picture.getvalue(), 'image/png')}).json()['id'] for i in range(2)]
        music = client.post('/api/uploads', files={'file': ('music.wav', b'mock waveform', 'audio/wav')}).json()['id']
        request = {'mode': preset['mode'], 'settings': {**preset['settings'], 'prompt': preset['prompt']}, 'refs': refs, 'music': music}
        response = client.post('/api/jobs', json=request)
        assert response.status_code == 200
        id = response.json()['id']
        client.get(f'/api/jobs/{id}/events')
        restored = client.get(f'/api/jobs/{id}/inputs').json()
        assert restored['mode'] == 'music' and restored['settings']['quality'] == 'max'
        assert restored['settings']['prompt'] == 'Product reveal'
        assert [r['id'] for r in restored['refs']] == refs and restored['music']['id'] == music


def test_preset_all_media_survive_restart_and_missing_files_are_reported(tmp_path):
    from dataclasses import replace
    config = replace(settings(tmp_path), mock=True)
    with TestClient(create_app(config, MockRunner())) as client:
        def upload(name, kind):
            response = client.post('/api/uploads', files={'file': (name, b'mock media', kind)})
            assert response.status_code == 200
            return response.json()
        source = upload('source.mp4', 'video/mp4')
        reference = upload('ref.png', 'image/png')
        reference_video = upload('motion.mp4', 'video/mp4')
        music = upload('music.wav', 'audio/wav')
        voice = upload('voice.wav', 'audio/wav')
        media = {'source': source, 'refs': [None, reference, None, None, None], 'refVideo': reference_video, 'music': music, 'voice': voice}
        body = {'name': 'Full media', 'mode': 'remix', 'inputs': media, 'settings': {'seed': 123}}
        body['inputs']['source']['url'] = 'https://untrusted.invalid/file.mp4'
        saved = client.post('/api/presets', json=body)
        assert saved.status_code == 200
        assert saved.json()['inputs']['source']['url'] == '/api/uploads/' + source['id']
    with TestClient(create_app(config, MockRunner())) as client:
        restored = next(p for p in client.get('/api/presets').json() if p['name'] == 'Full media')
        assert restored['inputs']['refs'][0] is None
        assert restored['inputs']['refs'][1]['id'] == reference['id']
        for slot in ['source', 'refVideo', 'music', 'voice']:
            assert restored['inputs'][slot]['id'] == media[slot]['id']
        assert restored['settings']['seed'] == 123 and restored['missing_inputs'] == []
        next((config.workspace/'uploads').glob(reference['id']+'.*')).unlink()
        missing = next(p for p in client.get('/api/presets').json() if p['name'] == 'Full media')
        assert missing['inputs']['refs'][1] is None and missing['missing_inputs'] == ['reference 2']


def test_preset_save_rejects_unknown_media(tmp_path):
    with TestClient(create_app(settings(tmp_path), MockRunner())) as client:
        response = client.post('/api/presets', json={'name': 'Missing', 'mode': 'text', 'inputs': {'music': {'id': 'missing', 'kind': 'audio', 'name': 'song', 'url': '/outside'}}})
        assert response.status_code == 422
