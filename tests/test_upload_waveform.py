import io
import json
import math
import struct
import subprocess
import wave
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.runner import MockRunner
from backend.server import create_app
from test_backend import _finished_job, _settings
from backend.media import audio_waveform


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


def test_audio_waveform_keeps_decoded_pcm_out_of_process_memory(monkeypatch, tmp_path):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        if 'ffprobe' in Path(command[0]).stem.lower():
            return SimpleNamespace(returncode=0, stdout=json.dumps({
                'streams': [{'codec_type': 'audio'}],
                'format': {'duration': '1'},
            }).encode())
        assert kwargs['stdout'] is not subprocess.PIPE
        kwargs['stdout'].write(struct.pack('<ffff', 0.0, 0.25, -0.5, 1.0))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr('backend.media.subprocess.run', run)
    peaks = audio_waveform(tmp_path / 'fixture.wav', 1, bins=4)
    assert peaks == [1.0, 0.0, 0.0, 0.0]
    assert calls[1][1]['timeout'] == 60


def test_job_waveform_uses_the_block_decoder_and_is_flat_without_audio(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings, MockRunner())) as client:
        job = _finished_job(client)
        jobs = settings.workspace / 'jobs'
        jobs.mkdir(parents=True, exist_ok=True)
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=64x64:d=2:r=24', '-f', 'lavfi', '-i', 'sine=d=2',
                        '-shortest', '-pix_fmt', 'yuv420p', str(jobs / f'{job}.mp4')], check=True)
        peaks = client.get(f'/api/jobs/{job}/waveform', params={'bins': 40}).json()
        assert len(peaks) == 40 and max(peaks) == 1
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=red:s=64x64:d=2:r=24', '-pix_fmt', 'yuv420p', str(jobs / f'{job}.mp4')], check=True)
        silent = client.get(f'/api/jobs/{job}/waveform', params={'bins': 20}).json()
        assert silent == [0.0] * 20
