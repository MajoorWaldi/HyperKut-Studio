import os
from dataclasses import dataclass
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def _studio_env(suffix, default=None):
    """HyperKut names take priority; existing installations keep working."""
    return os.environ.get('HYPERKUT_' + suffix, os.environ.get('SECATOR_' + suffix, default))



def _output_directory(comfyui_url: str) -> Path | None:
    """The output folder of the running ComfyUI, read from its own command line (the app and the nodes share the disk)."""
    try:
        argv = httpx.get(f"{comfyui_url}/system_stats", timeout=3).json()["system"]["argv"]
    except (httpx.HTTPError, KeyError, ValueError):
        return None
    return Path(argv[argv.index("--output-directory") + 1]) if "--output-directory" in argv[:-1] else None


@dataclass(frozen=True)
class Settings:
    comfyui_url: str
    proxy_url: str
    output_dir: Path | None
    workspace: Path
    templates_dir: Path
    mock: bool
    max_upload_bytes: int = 1024 * 1024 * 1024
    max_media_seconds: int = 3600
    max_media_pixels: int = 4096 * 4096
    max_active_jobs: int = 8
    allowed_hosts: tuple[str, ...] = ('127.0.0.1', 'localhost', '[::1]', 'testserver')
    job_metadata_labels: bool = False  # Local proxy accepts no SDK label maps.
    experimental_ai_edit: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        comfyui = _studio_env('COMFYUI_URL', "http://127.0.0.1:8188").rstrip("/")
        output = _studio_env('OUTPUT_DIR')
        local_comfy = Path(_studio_env('COMFYUI_DIR',ROOT.parents[2]))
        detected = _output_directory(comfyui) if not output else None
        if detected is None and (local_comfy/'main.py').is_file():
            detected = local_comfy/'output'
        return cls(comfyui, os.environ.get("COMFY_BASE_URL", "http://127.0.0.1:8189").rstrip("/"), Path(output).resolve() if output else detected,
                   Path(_studio_env('WORKSPACE', ROOT / "workspace")), Path(_studio_env('TEMPLATES', ROOT / "workflows")), _studio_env('MOCK') == "1",
                   max_upload_bytes=int(_studio_env('MAX_UPLOAD_MB',1024))*1024*1024,
                   max_media_seconds=int(_studio_env('MAX_MEDIA_SECONDS',3600)), max_media_pixels=int(_studio_env('MAX_MEDIA_PIXELS',4096*4096)),
                   max_active_jobs=int(_studio_env('MAX_ACTIVE_JOBS',8)),
                   allowed_hosts=tuple(x.strip() for x in _studio_env('ALLOWED_HOSTS', '127.0.0.1,localhost,[::1]').split(',') if x.strip()),
                   job_metadata_labels=_studio_env('JOB_METADATA_LABELS') == '1',
                   experimental_ai_edit=_studio_env('EXPERIMENTAL_AI_EDIT') == '1')
