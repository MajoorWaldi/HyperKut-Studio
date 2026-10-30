"""Versioned descriptors for future remote project transport.

No network, SDK, file IO or runner integration. A descriptor identifies bytes;
it does not prove those bytes exist or authorize materializing them on disk.
"""
from dataclasses import dataclass
import re

SCHEMA_VERSION = 1
MAX_ASSETS = 4096
_DIGEST = re.compile(r"[0-9a-f]{64}")
_PROJECT = re.compile(r"p_[0-9a-f]{8,32}")
_MIME = re.compile(r"[a-z0-9][a-z0-9.+-]*/[a-z0-9][a-z0-9.+-]*")
_DEVICES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def _fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError("Invalid descriptor fields")


def _integer(value, minimum):
    return type(value) is int and value >= minimum


def portable_relative_path(value):
    """Validate canonical project-relative names across Windows and POSIX."""
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise ValueError("Invalid artifact path")
    if any(ord(c) < 32 or ord(c) == 127 for c in value) or any(c in value for c in '\\:*?"<>|'):
        raise ValueError("Artifact path is not portable")
    parts = value.split('/')
    if any(part in ('', '.', '..') or part.rstrip(' .') != part for part in parts):
        raise ValueError("Artifact path must be canonical and relative")
    if any(part.split('.')[0].casefold() in _DEVICES for part in parts):
        raise ValueError("Artifact path uses a reserved name")
    return value


@dataclass(frozen=True)
class ArtifactRef:
    sha256: str
    size_bytes: int
    media_type: str = "application/octet-stream"

    def __post_init__(self):
        if not isinstance(self.sha256, str) or not _DIGEST.fullmatch(self.sha256):
            raise ValueError("Invalid SHA-256")
        if not _integer(self.size_bytes, 0):
            raise ValueError("Invalid artifact size")
        if not isinstance(self.media_type, str) or len(self.media_type) > 127 or not _MIME.fullmatch(self.media_type):
            raise ValueError("Invalid media type")

    @property
    def storage_key(self):
        return f"sha256/{self.sha256}"

    def to_dict(self):
        return {"sha256": self.sha256, "size_bytes": self.size_bytes, "media_type": self.media_type}

    @classmethod
    def from_dict(cls, value):
        _fields(value, ('sha256', 'size_bytes', 'media_type'))
        return cls(**value)


@dataclass(frozen=True)
class SnapshotAsset:
    relative_path: str
    artifact: ArtifactRef

    def __post_init__(self):
        portable_relative_path(self.relative_path)
        if self.relative_path.split('/')[0].casefold() == 'manifest.json':
            raise ValueError("Manifest is a separate snapshot artifact")
        if not isinstance(self.artifact, ArtifactRef):
            raise ValueError("Invalid artifact reference")

    def to_dict(self):
        return {"relative_path": self.relative_path, "artifact": self.artifact.to_dict()}

    @classmethod
    def from_dict(cls, value):
        _fields(value, ('relative_path', 'artifact'))
        return cls(value['relative_path'], ArtifactRef.from_dict(value['artifact']))


@dataclass(frozen=True)
class ProjectSnapshot:
    project_id: str
    revision: int
    manifest: ArtifactRef
    assets: tuple[SnapshotAsset, ...] = ()
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ValueError("Unsupported snapshot schema")
        if not isinstance(self.project_id, str) or not _PROJECT.fullmatch(self.project_id):
            raise ValueError("Invalid project id")
        if not _integer(self.revision, 1) or not isinstance(self.manifest, ArtifactRef):
            raise ValueError("Invalid snapshot revision or manifest")
        if type(self.assets) is not tuple or len(self.assets) > MAX_ASSETS or not all(isinstance(a, SnapshotAsset) for a in self.assets):
            raise ValueError("Invalid snapshot assets")
        seen = set()
        for asset in self.assets:
            key = asset.relative_path.casefold()
            if key in seen:
                raise ValueError("Duplicate or case-colliding artifact path")
            seen.add(key)
        # A file must never also be a parent directory of another file.
        for key in seen:
            parts = key.split('/')
            if any('/'.join(parts[:i]) in seen for i in range(1, len(parts))):
                raise ValueError("Artifact file/directory collision")

    def to_dict(self):
        return {"schema_version": self.schema_version, "project_id": self.project_id,
                "revision": self.revision, "manifest": self.manifest.to_dict(),
                "assets": [asset.to_dict() for asset in self.assets]}

    @classmethod
    def from_dict(cls, value):
        _fields(value, ('schema_version', 'project_id', 'revision', 'manifest', 'assets'))
        if not isinstance(value['assets'], list) or len(value['assets']) > MAX_ASSETS:
            raise ValueError("Invalid snapshot assets")
        return cls(value['project_id'], value['revision'], ArtifactRef.from_dict(value['manifest']),
                   tuple(SnapshotAsset.from_dict(a) for a in value['assets']), value['schema_version'])
