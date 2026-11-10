import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]

MIB = 1024 * 1024
MAX_STUDIO_UPLOAD_BYTES = 1024 * MIB
MAX_ARTIFACT_BYTES = 2 * 1024**3
MAX_ARTIFACT_CACHE_BYTES = 20 * 1024**3
MAX_SNAPSHOT_METADATA_BYTES = 16 * MIB
MAX_ARTIFACT_TRANSFER_BYTES = MAX_ARTIFACT_CACHE_BYTES + 2 * MAX_SNAPSHOT_METADATA_BYTES
PROXY_MAX_UPLOAD_MB = (MAX_ARTIFACT_TRANSFER_BYTES + MIB - 1) // MIB


def _studio_env(suffix, default=None):
    """HyperKut names take priority; existing installations keep working."""
    return os.environ.get('HYPERKUT_' + suffix, os.environ.get('SECATOR_' + suffix, default))


def _studio_int(suffix, default):
    value = _studio_env(suffix, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f'HYPERKUT_{suffix} must be an integer, received {value!r}') from None


def configuration_identity(
    comfyui_url: str,
    workspace: Path | str,
    storage_backend: str,
    proxy_url: str = '',
) -> dict:
    """Return a stable, non-secret identity for the local Studio configuration."""
    target_hash = hashlib.sha256(comfyui_url.rstrip('/').encode('utf-8')).hexdigest()
    proxy_hash = hashlib.sha256(proxy_url.rstrip('/').encode('utf-8')).hexdigest()
    workspace_path = os.path.normcase(os.path.abspath(os.fspath(workspace)))
    workspace_hash = hashlib.sha256(workspace_path.encode('utf-8')).hexdigest()
    identity = hashlib.sha256(
        f'hyperkut-studio-config-v1\n{target_hash}\n{proxy_hash}\n{workspace_hash}\n{storage_backend}'.encode('utf-8')
    ).hexdigest()
    return {
        'version': 1,
        'target_sha256': target_hash,
        'proxy_sha256': proxy_hash,
        'workspace_sha256': workspace_hash,
        'storage_backend': storage_backend,
        'id': identity,
    }


def _output_directory(comfyui_url: str) -> Path | None:
    """The output folder of the running ComfyUI, read from its own command line (the app and the nodes share the disk)."""
    try:
        argv = httpx.get(f"{comfyui_url}/system_stats", timeout=3).json()["system"]["argv"]
    except (httpx.HTTPError, KeyError, ValueError):
        return None
    return Path(argv[argv.index("--output-directory") + 1]) if "--output-directory" in argv[:-1] else None


def key_travels_safely(url: str) -> bool:
    """An API key may be sent to `url`: HTTPS, or plain HTTP to this computer only (a key sent in clear to another host can be read on the way)."""
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    if parts.scheme == 'https':
        return True
    return parts.scheme == 'http' and (parts.hostname or '') in ('127.0.0.1', 'localhost', '::1')


@dataclass(frozen=True)
class Settings:
    comfyui_url: str
    proxy_url: str
    output_dir: Path | None
    workspace: Path
    templates_dir: Path
    mock: bool
    max_upload_bytes: int = MAX_STUDIO_UPLOAD_BYTES
    max_media_seconds: int = 3600
    max_media_pixels: int = 4096 * 4096
    max_active_jobs: int = 1
    allowed_hosts: tuple[str, ...] = ('127.0.0.1', 'localhost', '[::1]', 'testserver')
    job_metadata_labels: bool = False  # Local proxy accepts no SDK label maps.
    experimental_ai_edit: bool = False
    storage_backend: str = "shared_local"
    max_artifact_bytes: int = MAX_ARTIFACT_BYTES
    max_artifact_cache_bytes: int = MAX_ARTIFACT_CACHE_BYTES
    access_mode: str = "local"
    access_username: str = field(default="", repr=False)
    access_password: str = field(default="", repr=False)
    max_workspace_bytes: int = 20 * 1024**3
    min_free_disk_bytes: int = 256 * 1024**2
    sfx_root: Path | None = None
    jury_visitor_limit: int = 5
    jury_total_limit: int = 15
    comfy_api: bool = False  # COMFY_BASE_URL is a Comfy API deployment, which has no ComfyUI routes

    def __post_init__(self):
        if not 1 <= self.max_active_jobs <= 8:
            raise ValueError('MAX_ACTIVE_JOBS must be between 1 and 8')
        if self.max_workspace_bytes <= 0 or self.min_free_disk_bytes < 0:
            raise ValueError('Workspace and free-disk limits must be positive')

    @classmethod
    def from_env(cls) -> "Settings":
        comfyui = _studio_env('COMFYUI_URL', "http://127.0.0.1:8188").rstrip("/")
        backend = _studio_env('STORAGE_BACKEND', 'shared_local')
        if backend not in ('shared_local','remote_artifacts'):
            raise ValueError('Unknown storage backend')
        workspace = Path(_studio_env('WORKSPACE', ROOT / 'workspace'))
        access_mode = _studio_env('ACCESS_MODE', 'local')
        if access_mode in ('jury', 'jury_open') and (not _studio_env('WORKSPACE') or not _studio_env('OUTPUT_DIR')):
            raise ValueError('Jury access requires explicit dedicated WORKSPACE and OUTPUT_DIR')
        upload_mb = _studio_int('MAX_UPLOAD_MB', 1024)
        if not 1 <= upload_mb <= MAX_STUDIO_UPLOAD_BYTES // MIB:
            raise ValueError('MAX_UPLOAD_MB must be between 1 and 1024 (Studio uploads are capped at 1 GiB)')
        max_active_jobs = _studio_int('MAX_ACTIVE_JOBS', 1)
        if not 1 <= max_active_jobs <= 8:
            raise ValueError('MAX_ACTIVE_JOBS must be between 1 and 8')
        workspace_mb = _studio_int('MAX_WORKSPACE_MB', 20480)
        min_free_disk_mb = _studio_int('MIN_FREE_DISK_MB', 256)
        if workspace_mb < 1 or min_free_disk_mb < 0:
            raise ValueError('MAX_WORKSPACE_MB must be positive and MIN_FREE_DISK_MB cannot be negative')
        comfy_api = _studio_env('COMFY_API') == '1'
        if comfy_api and backend != 'remote_artifacts':
            raise ValueError('A Comfy API deployment needs STORAGE_BACKEND=remote_artifacts')
        if comfy_api and not os.environ.get('COMFY_API_KEY', '').strip():
            raise ValueError('A Comfy API deployment needs COMFY_API_KEY')
        if comfy_api and not key_travels_safely(os.environ.get('COMFY_BASE_URL', 'http://127.0.0.1:8189')):
            raise ValueError('COMFY_BASE_URL must use HTTPS when it is not this computer: COMFY_API_KEY is sent to it')
        output = _studio_env('OUTPUT_DIR')
        if backend == 'remote_artifacts':
            output = str(workspace / 'remote-output')
        local_comfy = Path(_studio_env('COMFYUI_DIR', ROOT.parents[2] if len(ROOT.parents) > 2 else ROOT))
        detected = _output_directory(comfyui) if not output else None
        if detected is None and (local_comfy/'main.py').is_file():
            detected = local_comfy/'output'
        return cls(comfyui, os.environ.get("COMFY_BASE_URL", "http://127.0.0.1:8189").rstrip("/"), Path(output).resolve() if output else detected,
                   workspace, Path(_studio_env('TEMPLATES', ROOT / "workflows")), _studio_env('MOCK') == "1",
                   max_media_seconds=_studio_int('MAX_MEDIA_SECONDS', 3600), max_media_pixels=_studio_int('MAX_MEDIA_PIXELS', 4096*4096),
                   max_active_jobs=max_active_jobs,
                   allowed_hosts=tuple(x.strip() for x in _studio_env('ALLOWED_HOSTS', '127.0.0.1,localhost,[::1]').split(',') if x.strip()),
                   job_metadata_labels=_studio_env('JOB_METADATA_LABELS') == '1',
                   experimental_ai_edit=_studio_env('EXPERIMENTAL_AI_EDIT') == '1', storage_backend=backend,
                   max_artifact_bytes=MAX_ARTIFACT_BYTES, max_artifact_cache_bytes=MAX_ARTIFACT_CACHE_BYTES,
                   max_upload_bytes=upload_mb * MIB, access_mode=access_mode,
                   access_username=_studio_env('ACCESS_USERNAME', ''), access_password=_studio_env('ACCESS_PASSWORD', ''),
                   max_workspace_bytes=workspace_mb * MIB,
                   min_free_disk_bytes=min_free_disk_mb * MIB,
                   sfx_root=Path(_studio_env('SFX_ROOT')).resolve() if _studio_env('SFX_ROOT') else None,
                   jury_visitor_limit=_studio_int('JURY_VISITOR_LIMIT', 5), jury_total_limit=_studio_int('JURY_TOTAL_LIMIT', 15), comfy_api=comfy_api)

    def config_identity(self) -> dict:
        return configuration_identity(self.comfyui_url, self.workspace, self.storage_backend, self.proxy_url)

    def effective_limits(self) -> dict:
        transfer_bytes = self.max_artifact_cache_bytes + 2 * MAX_SNAPSHOT_METADATA_BYTES
        return {
            'studio_upload_bytes': self.max_upload_bytes,
            'studio_upload_max_bytes': MAX_STUDIO_UPLOAD_BYTES,
            'artifact_max_bytes': self.max_artifact_bytes,
            'artifact_cache_max_bytes': self.max_artifact_cache_bytes,
            'snapshot_transfer_max_bytes': transfer_bytes,
            'proxy_upload_max_mb': (transfer_bytes + MIB - 1) // MIB,
            'max_active_jobs': self.max_active_jobs,
            'workspace_max_bytes': self.max_workspace_bytes,
            'minimum_free_disk_bytes': self.min_free_disk_bytes,
        }
