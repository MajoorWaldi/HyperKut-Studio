"""Automatic export gate: a delivered video is compared with what the job asked for. Findings are warnings, never failures."""
import re
import shutil
import subprocess
from pathlib import Path

from .media import media_info

SCENE_THRESHOLD = 0.35


def cut_count(path: Path) -> int | None:
    """Hard cuts found by ffmpeg scene detection; None when the scan cannot run."""
    try:
        scan = subprocess.run([shutil.which('ffmpeg') or 'ffmpeg', '-v', 'info', '-i', str(path), '-an', '-vf', f"select='gt(scene,{SCENE_THRESHOLD})',showinfo", '-f', 'null', '-'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=180)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return len(re.findall(rb'pts_time:', scan.stderr)) if scan.returncode == 0 else None


def export_qc(video: Path, *, duration: float | None, ratio: str | None, audio: bool, reference: Path | None = None) -> list[str]:
    """Codes of `optional:qc:*` warnings for a delivered video. ratio is "9:16" style; reference is the video a remix follows."""
    info = media_info(video)
    found = []
    if duration is not None and abs(info['video_duration'] - duration) > max(0.6, duration * 0.05):
        found.append('optional:qc:duration')
    if ratio and info['width'] and info['height']:
        width, height = (int(part) for part in ratio.split(':'))
        if abs(info['width'] / info['height'] - width / height) > 0.03 * width / height:
            found.append('optional:qc:ratio')
    if audio and not info['has_audio']:
        found.append('optional:qc:no_audio')
    if reference is not None:
        expected, delivered = cut_count(reference), cut_count(video)
        if expected is not None and delivered is not None and abs(expected - delivered) > max(2, expected * 0.5):
            found.append('optional:qc:remix_cuts')
    return found
