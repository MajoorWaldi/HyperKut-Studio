"""Set up what a Comfy API image lacks, before any custom node loads: the controlnet_aux weight path and FFmpeg."""
import os
from pathlib import Path
import shutil
import tarfile
import tempfile

import folder_paths

AUX_FILES = ('hr16/DWPose-TorchScript-BatchSize5/dw-ll_ucoco_384_bs5.torchscript.pt', 'yzd-v/DWPose/yolox_l.onnx')
FFMPEG_ARCHIVE = 'ffmpeg-n8.1.3-32-g760d10603e-linux64-gpl-8.1.tar.xz'

models = Path(folder_paths.models_dir)
root = models / 'aux_ckpts'
# Only with the complete set: otherwise controlnet_aux keeps its own folder and downloads on first use.
if all((root / name).is_file() for name in AUX_FILES):
    os.environ.setdefault('AUX_ANNOTATOR_CKPTS_PATH', str(root))

archive = models / 'tools' / FFMPEG_ARCHIVE
if not shutil.which('ffmpeg') and archive.is_file():
    # A Build carries files, not system packages or executable bits, so the binaries are unpacked at each start.
    target = Path(tempfile.gettempdir()) / 'hyperkut-ffmpeg'
    target.mkdir(exist_ok=True)
    with tarfile.open(archive) as bundle:
        for member in bundle.getmembers():
            name = Path(member.name).name
            if member.isfile() and Path(member.name).parent.name == 'bin' and name in ('ffmpeg', 'ffprobe'):
                with bundle.extractfile(member) as source, (target / name).open('wb') as output:
                    shutil.copyfileobj(source, output)
                (target / name).chmod(0o755)
    os.environ['MAJOOR_FFMPEG'] = str(target / 'ffmpeg')
    os.environ['MAJOOR_FFPROBE'] = str(target / 'ffprobe')
    os.environ['PATH'] = f"{target}{os.pathsep}{os.environ.get('PATH', '')}"
