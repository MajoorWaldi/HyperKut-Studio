"""Remote transport configuration and SDK-only capability checks.

The connection belongs in a dedicated SDK process. It is never applied to the
live local runner or written to project metadata.
"""
from dataclasses import dataclass, field
import io
from urllib.parse import urlsplit

from .artifact_transfer import BoundedSink
from .project_snapshot import read_json


class CapabilityError(ValueError):
    pass


@dataclass(frozen=True)
class RemoteConnection:
    endpoint: str
    api_key: str = field(repr=False)

    def __post_init__(self):
        parsed = urlsplit(self.endpoint)
        local = parsed.hostname in ('localhost','127.0.0.1','::1')
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Remote endpoint must be an origin/path without credentials or query parameters')
        if parsed.scheme != 'https' and not (local and parsed.scheme == 'http'):
            raise ValueError('Remote endpoint requires HTTPS outside loopback')
        if not isinstance(self.api_key, str) or not self.api_key or any(ord(c) < 32 for c in self.api_key):
            raise ValueError('A server-side API credential is required')

    def child_environment(self, parent):
        # Give this to a child process; never mutate the parent SDK endpoint.
        return {**parent, 'COMFY_BASE_URL':self.endpoint.rstrip('/'), 'COMFY_API_KEY':self.api_key}


def require_capabilities(payload, *, operation='verify', generation=False):
    if not isinstance(payload, dict) or payload.get('protocol') != 1 or type(payload.get('protocol')) is not int:
        raise CapabilityError('Worker snapshot protocol is incompatible')
    if payload.get('outputs') != 'file' or payload.get('isolated_workspace') is not True:
        raise CapabilityError('Worker does not guarantee file transport and isolated workspaces')
    operations = payload.get('operations')
    if not isinstance(operations, list) or any(not isinstance(item, str) for item in operations) or operation not in operations:
        raise CapabilityError('Worker does not support the requested operation')
    if generation and payload.get('generation') is not True:
        raise CapabilityError('This worker supports transport tests only; H3 execution is not enabled')
    return payload


async def probe_capabilities(client):
    """One explicit CPU-only graph. Does not depend on native /object_info routes."""
    graph = client.workflows.from_json({'capabilities':{'class_type':'HyperKutSnapshotCapabilities','inputs':{}}})
    handle = await client.submit(graph)
    await handle.wait(timeout=60)
    await handle.result()
    await handle.refresh()
    outputs = handle.get_outputs('capabilities')
    matches = [o for o in outputs if o.type == 'file' and o.name == 'capabilities.json']
    if len(matches) != 1:
        raise CapabilityError('Worker did not return a unique capabilities file')
    stream = io.BytesIO()
    await matches[0].to_stream(BoundedSink(stream, 64*1024))
    return require_capabilities(read_json(stream.getvalue()))
