import json
import array
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image


def audio_waveform(path: Path, max_seconds: float, bins: int = 96) -> list[float]:
    result = subprocess.run(
        [shutil.which('ffmpeg') or 'ffmpeg', '-v', 'error', '-i', str(path),
         '-t', str(max_seconds), '-vn', '-ac', '1', '-ar', '8000', '-f', 'f32le', '-'],
        capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError('The audio waveform could not be decoded')
    samples = array.array('f')
    samples.frombytes(result.stdout[:len(result.stdout) // 4 * 4])
    if not samples or not all(math.isfinite(x) for x in samples):
        raise ValueError('The audio waveform contains no valid samples')
    peaks = [max((abs(x) for x in samples[i * len(samples) // bins:(i + 1) * len(samples) // bins]), default=0.0)
             for i in range(bins)]
    top = max(peaks) or 1.0
    return [round(peak / top, 3) for peak in peaks]


def media_info(path: Path) -> dict:
    result = subprocess.run([shutil.which('ffprobe') or 'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)], capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError('The media could not be decoded')
    data = json.loads(result.stdout)
    streams = data.get('streams', [])
    video = next((s for s in streams if s.get('codec_type') == 'video' and not s.get('disposition', {}).get('attached_pic')), None)
    audio = any(s.get('codec_type') == 'audio' for s in streams)
    if video is None and not audio:
        raise ValueError('The file contains no image, video or audio stream')
    return {'kind': 'video' if video else 'audio', 'has_audio': audio,
            'video_duration': float((video or {}).get('duration') or data.get('format', {}).get('duration') or 0),
            'stream_index': video['index'] if video else None, 'duration': float(data.get('format', {}).get('duration') or (video or {}).get('duration') or 0),
            'width': int((video or {}).get('width', 0)), 'height': int((video or {}).get('height', 0))}


def validate_media(path: Path, kind: str, max_seconds=3600, max_pixels=4096*4096) -> None:
    if kind == 'image':
        with Image.open(path) as image:
            if image.width * image.height > max_pixels:
                raise ValueError('Image dimensions exceed the configured pixel limit')
            image.verify()
        return
    info = media_info(path)
    if info['kind'] != kind:
        raise ValueError(f'Expected {kind}, received {info["kind"]}')
    if info['duration'] <= 0 or info['duration'] > max_seconds:
        raise ValueError('Media duration is empty or exceeds the configured limit')
    if info['width'] * info['height'] > max_pixels:
        raise ValueError('Video dimensions exceed the configured pixel limit')
    streams=['-map',f'0:{info["stream_index"]}','-map','0:a:0?'] if kind=='video' else ['-map','0:a:0']
    try:
        decoded=subprocess.run([shutil.which('ffmpeg') or 'ffmpeg','-v','error','-xerror','-err_detect','explode','-i',str(path),*streams,'-sn','-dn','-f','null','-'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=120)
    except subprocess.TimeoutExpired as error:
        raise ValueError('Media decoding exceeded the 120 second validation limit') from error
    if decoded.returncode:
        raise ValueError('The media is corrupt or cannot be decoded: '+decoded.stderr.decode(errors='replace')[-300:])


def validate_video(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError('SaveVideo produced no video file')
    validate_media(path, 'video')
