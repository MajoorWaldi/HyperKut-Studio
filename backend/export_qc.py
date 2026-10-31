"""Automatic export gate: a delivered video is compared with what the job asked for. Findings are warnings, never failures."""
import re
import shutil
import subprocess
from pathlib import Path

from .media import media_info

SCENE_THRESHOLD = 0.35
CUT_TOLERANCE = 0.4
KEPT_MIN = 0.6


def cut_times(path: Path) -> list[float] | None:
    """Seconds of the hard cuts found by ffmpeg scene detection; None when the scan cannot run."""
    try:
        scan = subprocess.run([shutil.which('ffmpeg') or 'ffmpeg', '-v', 'info', '-i', str(path), '-an', '-vf', f"select='gt(scene,{SCENE_THRESHOLD})',showinfo", '-f', 'null', '-'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=180)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return [float(t) for t in re.findall(rb'pts_time:([0-9.]+)', scan.stderr)] if scan.returncode == 0 else None


def cut_count(path: Path) -> int | None:
    times = cut_times(path)
    return None if times is None else len(times)


def cuts_kept(expected: list[float], delivered: list[float]) -> float:
    """Share of the expected cuts that have a delivered cut within CUT_TOLERANCE seconds, each delivered cut used once."""
    free, kept = sorted(delivered), 0
    for cut in sorted(expected):
        near = next((c for c in free if abs(c - cut) <= CUT_TOLERANCE), None)
        if near is not None:
            free.remove(near)
            kept += 1
    return kept / len(expected) if expected else 1.0


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
        expected, delivered = cut_times(reference), cut_times(video)
        if expected is not None and delivered is not None:
            if abs(len(expected) - len(delivered)) > max(2, len(expected) * 0.5):
                found.append('optional:qc:remix_cuts')
            elif cuts_kept(expected, delivered) < KEPT_MIN:
                found.append('optional:qc:remix_timing')
    return found
