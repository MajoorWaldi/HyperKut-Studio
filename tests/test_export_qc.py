import shutil
import subprocess

import pytest

from backend.export_qc import cut_count, export_qc

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


@pytest.mark.parametrize('ratio, size', [('9:16', '90x160'), ('16:9', '160x90'), ('1:1', '96x96'), ('3:4', '96x128')])
def test_every_studio_ratio_is_recognised_and_a_wrong_one_is_reported(tmp_path, ratio, size):
    video = make(tmp_path / 'ratio.mp4', size, 2)
    assert export_qc(video, duration=2, ratio=ratio, audio=True) == []
    other = next(r for r in ('9:16', '16:9', '1:1', '3:4') if r != ratio and abs(eval(r.replace(':', '/')) - eval(ratio.replace(':', '/'))) > 0.1)
    assert export_qc(video, duration=2, ratio=other, audio=True) == ['optional:qc:ratio']
