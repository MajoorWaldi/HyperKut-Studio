"""A Comfy API deployment has no ComfyUI routes: node schemas and brief texts come back as job outputs."""
import hashlib
import io
import json
import os

from comfy_sdk import ComfyError

from .artifact_transfer import BoundedSink
from .storage import write_json

SCHEMA_NODE = 'schemas'
SCHEMA_FILE = 'node-schemas.json'
MAX_SCHEMA_BYTES = 64 * 1024**2
JOB_TIMEOUT = 1800  # the first job of a deployment also waits for a cold start


def _cache_path(settings):
    # A new release is a new deployment with a new address, so the address identifies the schemas.
    key = hashlib.sha256(settings.proxy_url.encode('utf-8')).hexdigest()[:16]
    return settings.workspace/f'deployment-schemas-{key}.json'


def cached_schemas(settings):
    """The schemas already read from this deployment, or None. Never starts a GPU worker."""
    path = _cache_path(settings)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


async def fetch_schemas(client, settings):
    graph = client.workflows.from_json({SCHEMA_NODE: {'class_type': 'HyperKutNodeSchemas', 'inputs': {}}})
    handle = await client.submit(graph)
    await handle.wait(timeout=JOB_TIMEOUT)
    await handle.result()
    await handle.refresh()
    matches = [o for o in handle.get_outputs(SCHEMA_NODE) if o.type == 'file' and o.name == SCHEMA_FILE]
    if len(matches) != 1:
        raise ValueError('The deployment did not return its node schemas; check that the worker is in the Build')
    stream = io.BytesIO()
    await matches[0].to_stream(BoundedSink(stream, MAX_SCHEMA_BYTES))
    schemas = json.loads(stream.getvalue())
    if not isinstance(schemas, dict) or not schemas:
        raise ValueError('The deployment returned invalid node schemas')
    write_json(_cache_path(settings), schemas)
    return schemas


async def reachable(settings, client):
    """Whether the deployment answers this key. A worker scaled to zero still counts as reachable."""
    try:
        response = await client.get(f'{settings.proxy_url}/api/v2/health', headers={'Authorization': f"Bearer {os.environ.get('COMFY_API_KEY', '')}"})
    except OSError:
        return False
    except Exception as error:
        if type(error).__module__.startswith('httpx'):
            return False
        raise
    return response.status_code < 500 and response.status_code not in (401, 403)


async def brief_texts(client, slots, graphs, files, output_node):
    """Run each brief graph with the SDK, in order, and read the text of its output node."""
    handles = []
    try:
        for graph in graphs:
            workflow = client.workflows.from_json(graph)
            for name, path in files.items():
                for node, field in slots[name]:
                    if node in graph:
                        workflow.set_input(node, field, client.assets.from_file(path))
            handles.append(await client.submit(workflow))
        texts = []
        for handle in handles:
            await handle.wait(timeout=JOB_TIMEOUT)
            await handle.result()
            await handle.refresh()
            parts = [await output.to_bytes() for output in handle.get_outputs(output_node) if output.type == 'text']
            text = '\n'.join(part.decode('utf-8') for part in parts).strip()
            if not text:
                raise ValueError('The model returned an empty brief')
            texts.append(text)
        return texts
    except ComfyError as error:
        raise ValueError('Brief preparation failed on the deployment. No video was started.') from error
