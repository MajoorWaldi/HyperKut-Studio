import shutil
import subprocess

import pytest

from backend.creative_controls import strategy_values
from backend.export_qc import cut_count, cuts_kept, export_qc
from backend.models import Settings

pytestmark = pytest.mark.skipif(not shutil.which('ffmpeg'), reason='ffmpeg is required')


def make(path, size, seconds, audio=True, colors=('red',)):
    parts = [f"color=c={c}:s={size}:d={seconds / len(colors)}:r=24" for c in colors]
    command = ['ffmpeg', '-y', '-v', 'error']
    for part in parts:
        command += ['-f', 'lavfi', '-i', part]
    command += ['-filter_complex', ''.join(f'[{i}:v]' for i in range(len(parts))) + f'concat=n={len(parts)}:v=1[v]']
    if audio:
        command += ['-f', 'lavfi', '-i', f'sine=d={seconds}', '-map', '[v]', '-map', f'{len(parts)}:a', '-shortest']
    else:
        command += ['-map', '[v]']
    subprocess.run([*command, '-pix_fmt', 'yuv420p', str(path)], check=True)
    return path


def test_a_matching_export_has_no_findings(tmp_path):
    video = make(tmp_path / 'ok.mp4', '90x160', 4)
    assert export_qc(video, duration=4, ratio='9:16', audio=True) == []


def test_duration_ratio_and_audio_are_reported(tmp_path):
    video = make(tmp_path / 'bad.mp4', '160x90', 2, audio=False)
    assert export_qc(video, duration=8, ratio='9:16', audio=True) == ['optional:qc:duration', 'optional:qc:ratio', 'optional:qc:no_audio']
    assert export_qc(video, duration=None, ratio=None, audio=False) == []


def test_remix_cuts_are_compared_with_the_reference(tmp_path):
    reference = make(tmp_path / 'ref.mp4', '90x160', 6, colors=('red', 'blue', 'green', 'white', 'black', 'yellow'))
    still = make(tmp_path / 'still.mp4', '90x160', 6)
    assert cut_count(reference) == 5 and cut_count(still) == 0
    assert export_qc(still, duration=None, ratio=None, audio=True, reference=reference) == ['optional:qc:remix_cuts']
    assert export_qc(reference, duration=None, ratio=None, audio=True, reference=reference) == []


def test_same_number_of_cuts_at_other_moments_is_reported(tmp_path):
    reference = make(tmp_path / 'ref.mp4', '90x160', 8, colors=('red', 'blue', 'green', 'white'))
    shifted = tmp_path / 'shifted.mp4'
    command = ['ffmpeg', '-y', '-v', 'error']
    for color, seconds in (('red', 1), ('blue', 1), ('green', 1), ('white', 5)):
        command += ['-f', 'lavfi', '-i', f'color=c={color}:s=90x160:d={seconds}:r=24']
    command += ['-f', 'lavfi', '-i', 'sine=d=8', '-filter_complex', '[0:v][1:v][2:v][3:v]concat=n=4:v=1[v]', '-map', '[v]', '-map', '4:a', '-pix_fmt', 'yuv420p', str(shifted)]
    subprocess.run(command, check=True)
    assert cut_count(shifted) == cut_count(reference) == 3
    assert export_qc(shifted, duration=None, ratio=None, audio=True, reference=reference) == ['optional:qc:remix_timing']
    assert export_qc(reference, duration=None, ratio=None, audio=True, reference=reference) == []


def test_each_delivered_cut_answers_one_expected_cut():
    assert cuts_kept([1, 1.1, 1.2], [1.05]) == 1 / 3
    assert cuts_kept([2, 4], [2.3, 4.5]) == 0.5
    assert cuts_kept([], [3]) == 1.0


@pytest.mark.parametrize('ratio, size', [('9:16', '90x160'), ('16:9', '160x90'), ('1:1', '96x96'), ('3:4', '96x128')])
def test_every_studio_ratio_is_recognised_and_a_wrong_one_is_reported(tmp_path, ratio, size):
    video = make(tmp_path / 'ratio.mp4', size, 2)
    assert export_qc(video, duration=2, ratio=ratio, audio=True) == []
    other = next(r for r in ('9:16', '16:9', '1:1', '3:4') if r != ratio and abs(eval(r.replace(':', '/')) - eval(ratio.replace(':', '/'))) > 0.1)
    assert export_qc(video, duration=2, ratio=other, audio=True) == ['optional:qc:ratio']


def test_a_remix_strategy_sets_what_is_held_fixed():
    assert strategy_values(Settings()) == {}
    assert strategy_values(Settings(remix_strategy='preserve'))['pose_strength'] == 1.0
    creative, transfer = strategy_values(Settings(remix_strategy='creative')), strategy_values(Settings(remix_strategy='transfer'))
    assert creative['pose_strength'] < 0.5 and creative['reference_fidelity'] == 'loose'
    assert transfer['force_pose'] is True and transfer['creative_freedom'] == 'free'
