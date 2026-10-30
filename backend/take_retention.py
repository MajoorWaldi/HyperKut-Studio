"""Recoverable, journaled deletion of unused take media."""
import json
import os
import uuid
from pathlib import Path

from .storage import SharedProjectRepository, write_json


def _media_references(manifest: dict) -> set[str]:
    references = set()
    source = manifest.get('source') or {}
    if source.get('uri'):
        references.add(source['uri'])
    for shot in manifest.get('shots', []):
        for key in ('source_media_ref', 'thumbnail_ref'):
            if shot.get(key):
                references.add(shot[key])
        references.update(
            revision['media_ref'] for revision in shot.get('revisions', [])
            if revision.get('media_ref')
        )
    return references


def _resolve_relative(project: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('Invalid media path in take-retention journal')
    target = (project / relative).resolve()
    if project.resolve() not in target.parents:
        raise ValueError('Take-retention path escapes the project')
    return target


def _recover(project: Path, manifest: dict, journal_path: Path) -> int:
    if not journal_path.is_file():
        return 0
    journal = json.loads(journal_path.read_text(encoding='utf-8'))
    items = journal.get('items')
    if not isinstance(items, list):
        raise ValueError('Invalid take-retention journal')
    referenced = _media_references(manifest)
    removed = 0
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Invalid take-retention journal entry')
        relative = item.get('relative')
        trash_relative = item.get('trash')
        original = _resolve_relative(project, relative)
        trashed = _resolve_relative(project, trash_relative)
        if relative in referenced:
            if trashed.exists():
                if original.exists():
                    raise OSError(f'Cannot safely restore referenced take: {relative}')
                original.parent.mkdir(parents=True, exist_ok=True)
                os.replace(trashed, original)
        else:
            if trashed.is_file():
                removed += trashed.stat().st_size
                trashed.unlink()
            if original.is_file():
                removed += original.stat().st_size
                original.unlink()
        parent = trashed.parent
        while parent != project / '.retention' and parent.is_dir():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    journal_path.unlink()
    trash_root = project / '.retention' / 'trash'
    if trash_root.is_dir():
        try:
            trash_root.rmdir()
        except OSError:
            pass
    return removed


def free_unused_takes(project: Path, referenced_takes) -> dict:
    project = project.resolve()
    repository = SharedProjectRepository(project.parent)
    retention_dir = project / '.retention'
    journal_path = retention_dir / 'pending.json'
    freed = 0
    with repository.edit(project.name) as manifest:
        freed += _recover(project, manifest, journal_path)
        used = referenced_takes(project)
        protected = {
            revision['media_ref']
            for shot in manifest.get('shots', [])
            for revision in shot.get('revisions', [])
            if revision.get('media_ref') and (
                revision.get('media_range') is not None
                or revision['revision_id'] == shot.get('active_revision_id')
                or (shot['shot_id'], revision['revision_id']) in used
            )
        }
        candidates = set()
        for shot in manifest.get('shots', []):
            kept = []
            for revision in shot.get('revisions', []):
                is_protected = (
                    revision.get('media_range') is not None
                    or revision['revision_id'] == shot.get('active_revision_id')
                    or (shot['shot_id'], revision['revision_id']) in used
                )
                if is_protected:
                    kept.append(revision)
                    continue
                relative = revision.get('media_ref')
                raw_target = project / relative if isinstance(relative, str) else None
                if relative and relative not in protected and raw_target is not None and not raw_target.is_symlink():
                    target = _resolve_relative(project, relative)
                    if target.is_file():
                        candidates.add(relative)
            shot['revisions'] = kept

        if not candidates:
            return {'freed': freed, 'mirror_freed_bytes': freed, 'cache_freed_bytes': 0, 'worker_freed_bytes': None}

        operation = uuid.uuid4().hex
        items = [
            {'relative': relative, 'trash': f'.retention/trash/{operation}/{relative}'}
            for relative in sorted(candidates)
        ]
        retention_dir.mkdir(parents=True, exist_ok=True)
        write_json(journal_path, {'operation': operation, 'items': items})
        try:
            for item in items:
                original = _resolve_relative(project, item['relative'])
                trashed = _resolve_relative(project, item['trash'])
                trashed.parent.mkdir(parents=True, exist_ok=True)
                os.replace(original, trashed)
        except OSError:
            _recover(project, json.loads((project / 'manifest.json').read_text(encoding='utf-8')), journal_path)
            raise

    freed += _recover(project, json.loads((project / 'manifest.json').read_text(encoding='utf-8')), journal_path)
    return {'freed': freed, 'mirror_freed_bytes': freed, 'cache_freed_bytes': 0, 'worker_freed_bytes': None}
