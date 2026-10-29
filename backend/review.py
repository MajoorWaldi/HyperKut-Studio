"""Local contact sheets, cached by the exact video bytes and sampling interval."""
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

from filelock import FileLock

from .media import media_info
from .storage import write_json


def build_review_frames(video: Path, directory: Path, interval: float=.5) -> list[dict]:
    if not math.isfinite(interval) or interval<=0:
        raise ValueError('Review interval must be positive')
    digest=hashlib.sha256()
    with video.open('rb') as stream:
        while chunk:=stream.read(1024*1024):digest.update(chunk)
    key=hashlib.sha256((digest.hexdigest()+str(interval)).encode()).hexdigest()[:20]
    cache=directory/key
    cache.mkdir(parents=True,exist_ok=True)
    with FileLock(str(cache/'.lock'),timeout=120):
        index=cache/'index.json'
        if index.is_file():
            frames=json.loads(index.read_text(encoding='utf-8'))
            if all((directory/f['file']).is_file() for f in frames):return frames
        duration=media_info(video)['duration']
        count=math.ceil(duration/interval)
        if count>240:raise ValueError('Review is limited to 240 frames; increase the sampling interval')
        subprocess.run([shutil.which('ffmpeg') or 'ffmpeg','-y','-v','error','-i',str(video),'-vf',f'tpad=stop_mode=clone:stop_duration={interval},fps=1/{interval}:start_time=0,scale=320:-2','-frames:v',str(count),str(cache/'%06d.jpg')],capture_output=True,timeout=120,check=True)
        frames=[{'seconds':round(i*interval,4),'file':f'{key}/{i+1:06d}.jpg'} for i in range(count) if (cache/f'{i+1:06d}.jpg').is_file()]
        if len(frames)!=count:raise ValueError('The contact sheet is incomplete')
        write_json(index,frames)
        return frames
