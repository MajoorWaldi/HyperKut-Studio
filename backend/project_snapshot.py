"""Explicit project snapshots; no implicit scan of uploads or user folders."""
from contextlib import contextmanager
import hashlib
import json
import re
from pathlib import Path
import shutil
import tempfile

from filelock import FileLock

from .artifact_contract import ArtifactRef, ProjectSnapshot, SnapshotAsset, portable_relative_path
from .artifact_store import CHUNK_SIZE, ArtifactIntegrityError, ArtifactQuotaError, _regular

MAX_JSON_BYTES = 16 * 1024 * 1024
AUDIO_INDEX = 'sources/audio/index.json'


def audio_references(index):
    if not isinstance(index, dict) or index.get('version') != 1 or not isinstance(index.get('assets'), dict):
        raise ValueError('Invalid persistent audio index')
    paths = {}
    for fingerprint, record in index['assets'].items():
        if not isinstance(fingerprint, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', fingerprint):
            raise ValueError('Invalid persistent audio fingerprint')
        digest = fingerprint.removeprefix('sha256:')
        if not isinstance(record, dict) or record.get('asset_id') != fingerprint or record.get('sha256') != fingerprint:
            raise ValueError('Persistent audio identity differs from its index')
        relative = record.get('media_ref')
        if not isinstance(relative, str) or not re.fullmatch(
                r'sources/audio/' + digest + r'\.(wav|mp3|flac|ogg|m4a|aac|audio)', relative):
            raise ValueError('Persistent audio path differs from its fingerprint')
        paths[relative] = digest
    return paths


def read_json(data):
    if len(data) > MAX_JSON_BYTES:
        raise ArtifactQuotaError('Snapshot JSON exceeds metadata limit')
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Non-finite JSON number')
    return json.loads(data, object_pairs_hook=unique, parse_constant=invalid)


def checked_file(project, relative):
    portable_relative_path(relative)
    project = Path(project).absolute()
    for candidate in (project, *project.parents):
        info = candidate.lstat()
        if candidate.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ArtifactIntegrityError('Project contains a reparse point')
    path = project
    for part in relative.split('/'):
        path = path / part
        info = path.lstat()
        if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ArtifactIntegrityError('Snapshot source contains a reparse point')
    _regular(path)
    return path


def referenced_files(manifest):
    # Reuse the established node schema and frame validation, including takes.
    from .snapshot_schema import shot_list
    sl = shot_list(manifest)
    paths = {sl.source.uri}
    for shot in sl.shots:
        paths.add(shot.source_media_ref)
        if shot.thumbnail_ref:
            paths.add(shot.thumbnail_ref)
        paths.update(revision.media_ref for revision in shot.revisions)
    for path in paths:
        portable_relative_path(path)
    return paths


def validate_snapshot(store, snapshot):
    with store.open_verified(snapshot.manifest) as source:
        manifest = read_json(source.read(MAX_JSON_BYTES + 1))
    if manifest.get('project_id') != snapshot.project_id or manifest.get('project_revision') != snapshot.revision:
        raise ValueError('Snapshot and manifest identity/revision differ')
    assets = {asset.relative_path: asset.artifact for asset in snapshot.assets}
    required = referenced_files(manifest)
    if AUDIO_INDEX in assets:
        with store.open_verified(assets[AUDIO_INDEX]) as source:
            audio = audio_references(read_json(source.read(MAX_JSON_BYTES + 1)))
        required.update(audio)
        for relative, digest in audio.items():
            if relative not in assets or assets[relative].sha256 != digest:
                raise ValueError('Snapshot persistent audio is missing or has changed')
    if 'editor/timeline.json' in assets:
        with store.open_verified(assets['editor/timeline.json']) as source:
            record = read_json(source.read(MAX_JSON_BYTES + 1))
        from .snapshot_schema import checked_document
        if type(record.get('enabled')) is not bool or record.get('version') != 1:
            raise ValueError('Invalid saved editor record')
        checked_document(record['sources'], record['document'])
        if record['sources'].get('project_id') != snapshot.project_id:
            raise ValueError('Editor sources belong to another project')
        # A disabled/stale montage may intentionally retain older takes.
        required.update(referenced_files(record['sources']))
    if not required.issubset(assets):
        raise ValueError('Snapshot is missing referenced project media')
    # Metadata-only validation must never publish a head with missing/corrupt blobs.
    for ref in {snapshot.manifest, *(asset.artifact for asset in snapshot.assets)}:
        with store.open_verified(ref):
            pass
    return manifest


def cache_file(store, path):
    info = _regular(path)
    if info.st_size > store.max_artifact_bytes:
        raise ArtifactQuotaError('Snapshot source exceeds per-file limit')
    with path.open('rb') as source:
        digest = hashlib.sha256()
        while chunk := source.read(CHUNK_SIZE):
            digest.update(chunk)
        expected = ArtifactRef(digest.hexdigest(), info.st_size)
        source.seek(0)
        store.put(source, expected)
    return expected


def capture_project(store, project, *, extra_paths=()):
    """Capture only referenced media and explicitly requested extras under the project lock."""
    project = Path(project).absolute()
    # Validate the project path before opening a lock or creating any file.
    checked_file(project, 'manifest.json')
    with FileLock(str(project / '.lock'), timeout=120):
        manifest_path = checked_file(project, 'manifest.json')
        if manifest_path.stat().st_size > MAX_JSON_BYTES:
            raise ArtifactQuotaError('Manifest exceeds metadata limit')
        manifest = read_json(manifest_path.read_bytes())
        paths = referenced_files(manifest) | set(extra_paths)
        if (project / AUDIO_INDEX).exists():
            index = checked_file(project, AUDIO_INDEX)
            if index.stat().st_size > MAX_JSON_BYTES:
                raise ArtifactQuotaError('Persistent audio index exceeds metadata limit')
            audio = audio_references(read_json(index.read_bytes()))
            paths.update((AUDIO_INDEX, *audio))
        for relative in ('music/retained.wav', 'sources/music.wav', 'editor/timeline.json'):
            if (project / relative).exists():
                paths.add(relative)
        if 'editor/timeline.json' in paths:
            editor_path = checked_file(project, 'editor/timeline.json')
            if editor_path.stat().st_size > MAX_JSON_BYTES:
                raise ArtifactQuotaError('Editor record exceeds metadata limit')
            record = read_json(editor_path.read_bytes())
            paths.update(referenced_files(record['sources']))
        # Validate descriptors and collisions before storing anything.
        empty = ArtifactRef('0' * 64, 0)
        ProjectSnapshot(project.name, manifest['project_revision'], empty,
                        tuple(SnapshotAsset(path, empty) for path in sorted(paths)))
        assets = tuple(SnapshotAsset(path, cache_file(store, checked_file(project, path))) for path in sorted(paths))
        snapshot = ProjectSnapshot(project.name, manifest['project_revision'], cache_file(store, manifest_path), assets)
        validate_snapshot(store, snapshot)
        return snapshot


@contextmanager
def materialize_snapshot(store, snapshot, workspace):
    """Create a disposable worker folder, never overwrite an existing project.

    Copy rather than hardlink: worker edits cannot mutate the cache. The caller
    must finish exporting results before leaving this context.
    """
    validate_snapshot(store, snapshot)
    workspace = Path(workspace).absolute()
    # Constructor validates ancestors; use a separate empty namespace for staging.
    from .artifact_store import LocalArtifactStore
    LocalArtifactStore(workspace)
    total = snapshot.manifest.size_bytes + sum(asset.artifact.size_bytes for asset in snapshot.assets)
    if total > store.max_cache_bytes:
        raise ArtifactQuotaError('Materialized snapshot exceeds workspace limit')
    with tempfile.TemporaryDirectory(prefix='snapshot-', dir=workspace) as temporary:
        project = Path(temporary) / snapshot.project_id
        project.mkdir()
        items = [('manifest.json', snapshot.manifest), *((a.relative_path, a.artifact) for a in snapshot.assets)]
        for relative, ref in items:
            destination = project / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with store.open_verified(ref) as source, destination.open('xb') as output:
                shutil.copyfileobj(source, output, length=CHUNK_SIZE)
        yield project
