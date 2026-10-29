import io
import math
import struct
import wave

from fastapi.testclient import TestClient

from backend.runner import MockRunner
from backend.server import create_app
from test_backend import _settings


def wav_bytes(silent=False):
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b''.join(struct.pack('<h', 0 if silent else int(15000 * math.sin(i * .2))) for i in range(8000)))
    return buffer.getvalue()


def test_audio_upload_waveform_is_measured_cached_and_handles_silence(tmp_path):
    with TestClient(create_app(_settings(tmp_path), MockRunner())) as client:
        for silent in (False, True):
            upload = client.post('/api/uploads', files={'file': ('sound.wav', wav_bytes(silent), 'audio/wav')}).json()
            response = client.get(f"/api/uploads/{upload['id']}/waveform")
            assert response.status_code == 200, response.text
            peaks = response.json()
            assert len(peaks) == 96
            assert all(0 <= p <= 1 for p in peaks)
            assert max(peaks) == (0 if silent else 1)
            assert client.get(f"/api/uploads/{upload['id']}/waveform").json() == peaks
        assert client.get('/api/uploads/unknown/waveform').status_code == 404
        bad = client.post('/api/uploads', files={'file': ('bad.wav', b'invalid', 'audio/wav')}).json()
        assert client.get(f"/api/uploads/{bad['id']}/waveform").status_code == 422
