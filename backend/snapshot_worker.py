"""CPU-only snapshot worker operations, independent of the Studio project disk.

Only verification and deterministic prompt edits are supported here. H3 nodes
are not wired to this worker yet; they require explicit project-root propagation.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import uuid

from .artifact_bundle import read_bundle, write_bundle
from .artifact_contract import ArtifactRef
from .artifact_store import LocalArtifactStore, CHUNK_SIZE
from .project_snapshot import capture_project, materialize_snapshot
from .storage import SharedProjectRepository


def transform_snapshot(source, output_root, operation, *, max_cache_bytes=20*1024**3):
    if not isinstance(operation, dict):
        raise ValueError('Worker operation must be an object')
    common = {'kind','project_id','expected_revision'}
    allowed = common if operation.get('kind') == 'verify' else common | {'shot_id','prompt'}
    if set(operation) != allowed or operation.get('kind') not in ('verify','set_prompt'):
        raise ValueError('Unsupported worker operation')
    output_root = Path(output_root)
    LocalArtifactStore(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='worker-', dir=output_root) as directory:
        root = Path(directory)
        store = LocalArtifactStore(root/'cache', max_cache_bytes=max_cache_bytes)
        incoming = read_bundle(store, source)
        if operation['project_id'] != incoming.project_id or type(operation['expected_revision']) is not int or operation['expected_revision'] != incoming.revision:
            raise ValueError('Worker operation does not match snapshot identity/revision')
        with materialize_snapshot(store, incoming, root/'projects') as project:
            if operation['kind'] == 'set_prompt':
                if not isinstance(operation['prompt'], str) or len(operation['prompt']) > 16000:
                    raise ValueError('Invalid worker prompt')
                with SharedProjectRepository(project.parent).edit(project.name, expected_revision=incoming.revision) as manifest:
                    shot = next((row for row in manifest['shots'] if row['shot_id'] == operation['shot_id']), None)
                    if shot is None:
                        raise ValueError('Unknown worker shot')
                    shot['plan'] = {**(shot.get('plan') or {}), 'prompt':operation['prompt']}
            outgoing = capture_project(store, project)
            token = uuid.uuid4().hex
            bundle = root/'result.snapshot.zip'
            with bundle.open('xb') as stream:
                write_bundle(store, outgoing, stream)
            digest = hashlib.sha256()
            with bundle.open('rb') as stream:
                while chunk := stream.read(CHUNK_SIZE):
                    digest.update(chunk)
            descriptor = {'artifact':ArtifactRef(digest.hexdigest(), bundle.stat().st_size, 'application/zip').to_dict(),
                          'snapshot':outgoing.to_dict()}
            # Move the complete ZIP first, publish its descriptor last.
            final_bundle = output_root/f'{token}.snapshot.zip'
            final_descriptor = output_root/f'{token}.descriptor.json'
            try:
                bundle.replace(final_bundle)
                final_descriptor.write_text(json.dumps(descriptor, ensure_ascii=False), encoding='utf-8')
            except BaseException:
                final_bundle.unlink(missing_ok=True)
                final_descriptor.unlink(missing_ok=True)
                raise
            return outgoing, final_bundle, final_descriptor


def publish_snapshot(store, snapshot, output_root):
    """Publish a complete archive and descriptor; no host paths in either."""
    output_root=Path(output_root)
    output_root.mkdir(parents=True,exist_ok=True)
    token=uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix='publish-',dir=output_root) as temporary:
        bundle=Path(temporary)/'result.zip'
        with bundle.open('xb') as stream:write_bundle(store,snapshot,stream)
        digest=hashlib.sha256()
        with bundle.open('rb') as stream:
            while chunk:=stream.read(CHUNK_SIZE):digest.update(chunk)
        descriptor={'artifact':ArtifactRef(digest.hexdigest(),bundle.stat().st_size,'application/zip').to_dict(),'snapshot':snapshot.to_dict()}
        final=output_root/f'{token}.snapshot.zip'
        metadata=output_root/f'{token}.descriptor.json'
        try:
            bundle.replace(final)
            from .storage import write_json
            write_json(metadata,descriptor)
        except BaseException:
            final.unlink(missing_ok=True);metadata.unlink(missing_ok=True)
            raise
        return final,metadata
