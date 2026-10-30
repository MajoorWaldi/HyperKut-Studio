"""Strict validation and extraction for portable Studio project archives."""
from dataclasses import dataclass
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from collections.abc import Callable

from .models import JobRequest
from .project_snapshot import MAX_JSON_BYTES, audio_references, read_json, referenced_files
from .snapshot_schema import checked_document

MAX_ARCHIVE_ENTRIES = 20_000
MAX_COMPRESSION_RATIO = 1_000


@dataclass(frozen=True)
class ImportedProject:
    request: JobRequest
    manifest: dict
    request_files: dict[str, str]
    files: frozenset[str]
    uncompressed_bytes: int


def _safe_entry(name: str, is_directory: bool = False) -> str:
    if not name or '\\' in name or '\x00' in name:
        raise ValueError('Project archive contains an unsafe path')
    relative = name[:-1] if is_directory and name.endswith('/') else name
    path = PurePosixPath(relative)
    if not path.parts or path.is_absolute() or any(part in ('', '.', '..') for part in path.parts) or ':' in path.parts[0]:
        raise ValueError('Project archive contains an unsafe path')
    if str(path) != relative:
        raise ValueError('Project archive contains a non-canonical path')
    return relative


def extract_project_archive(
    archive_path: Path,
    destination: Path,
    maximum_bytes: int,
    preflight: Callable[[int], None] | None = None,
) -> ImportedProject:
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_ENTRIES:
            raise ValueError('Project archive contains too many entries')
        files: dict[str, zipfile.ZipInfo] = {}
        total_bytes = 0
        folded_names = set()
        for info in infos:
            if info.is_dir():
                _safe_entry(info.filename, is_directory=True)
                continue
            name = _safe_entry(info.filename)
            folded = name.casefold()
            if folded in folded_names:
                raise ValueError('Project archive contains duplicate paths')
            folded_names.add(folded)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG)):
                raise ValueError('Project archive contains a link or special file')
            if info.flag_bits & 1:
                raise ValueError('Encrypted project archives are not supported')
            if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise ValueError('Project archive uses an unsupported compression method')
            if info.file_size < 0 or info.compress_size < 0:
                raise ValueError('Project archive contains invalid file sizes')
            if info.file_size > MAX_JSON_BYTES and name in ('manifest.json', 'request.json', 'request_files.json'):
                raise ValueError('Project archive metadata exceeds its size limit')
            if info.file_size > max(1, info.compress_size) * MAX_COMPRESSION_RATIO:
                raise ValueError('Project archive compression ratio exceeds its safety limit')
            total_bytes += info.file_size
            if total_bytes > maximum_bytes:
                raise ValueError('Project archive exceeds the configured import size limit')
            files[name] = info

        required_metadata = {'manifest.json', 'request.json', 'request_files.json'}
        if not required_metadata <= files.keys():
            raise ValueError('Project archive is missing its request or manifest')

        if preflight is not None:
            preflight(total_bytes)
        destination.mkdir(parents=True, exist_ok=False)
        for name, info in files.items():
            target = destination.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with archive.open(info) as source, target.open('xb') as output:
                while chunk := source.read(1024 * 1024):
                    written += len(chunk)
                    if written > info.file_size:
                        raise ValueError(f'Project archive entry exceeds its declared size: {name}')
                    output.write(chunk)
            if written != info.file_size:
                raise ValueError(f'Project archive entry is truncated: {name}')

    manifest_path = destination / 'manifest.json'
    if manifest_path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError('Project manifest exceeds its metadata size limit')
    manifest = read_json(manifest_path.read_bytes())
    if not isinstance(manifest, dict) or not re.fullmatch(r'p_[0-9a-f]{8,32}', str(manifest.get('project_id', ''))):
        raise ValueError('Project manifest has an invalid project identity')
    request_data = read_json((destination / 'request.json').read_bytes())
    request = JobRequest.model_validate(request_data)
    request_files = read_json((destination / 'request_files.json').read_bytes())
    if not isinstance(request_files, dict) or any(
        not isinstance(key, str) or not re.fullmatch(r'[0-9a-f]{12}', key)
        or not isinstance(value, str) for key, value in request_files.items()
    ):
        raise ValueError('Project archive has an invalid input-file map')

    project_assets = referenced_files(manifest)
    if 'sources/audio/index.json' in files:
        index = read_json((destination / 'sources/audio/index.json').read_bytes())
        project_assets.update(audio_references(index))
        project_assets.add('sources/audio/index.json')
    for optional in ('music/retained.wav', 'sources/music.wav', 'editor/timeline.json'):
        if optional in files:
            project_assets.add(optional)
    if 'editor/timeline.json' in files:
        editor_path = destination / 'editor/timeline.json'
        if editor_path.stat().st_size > MAX_JSON_BYTES:
            raise ValueError('Saved timeline exceeds its metadata size limit')
        record = read_json(editor_path.read_bytes())
        if not isinstance(record, dict):
            raise ValueError('Saved timeline metadata is invalid')
        if type(record.get('enabled')) is not bool or type(record.get('version')) is not int or record.get('version') != 1:
            raise ValueError('Saved timeline metadata is invalid')
        sources = record.get('sources')
        if not isinstance(sources, dict) or sources.get('project_id') != manifest['project_id']:
            raise ValueError('Saved timeline belongs to another project')
        checked_document(sources, record['document'])
        project_assets.update(referenced_files(sources))

    input_assets = set(request_files.values())
    if any(
        not entry.startswith('inputs/') or _safe_entry(entry) != entry
        or PurePosixPath(entry).parent != PurePosixPath('inputs')
        for entry in input_assets
    ):
        raise ValueError('Project input map points outside its media folder')
    allowed = required_metadata | {'result.mp4'} | project_assets | input_assets
    unknown = files.keys() - allowed
    if unknown:
        raise ValueError('Project archive contains unreferenced files')
    if not project_assets <= files.keys() or not input_assets <= files.keys():
        raise ValueError('Project archive is missing referenced project or input media')
    return ImportedProject(request, manifest, request_files, frozenset(files), total_bytes)
