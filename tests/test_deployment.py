import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from backend.config import Settings
from backend.deployment import SCHEMA_FILE, SCHEMA_NODE, brief_texts, cached_schemas, fetch_schemas, reachable
from backend.runner import ComfyRunner


class Output:
    def __init__(self, kind, name, body):
        self.type, self.name, self.body = kind, name, body

    async def to_stream(self, sink):
        sink.write(self.body)

    async def to_bytes(self):
        return self.body


class Handle:
    def __init__(self, outputs):
        self.outputs = outputs

    async def wait(self, timeout=None):
        return self

    async def result(self):
        return self

    async def refresh(self):
        return self

    def get_outputs(self, node):
        return self.outputs.get(node, [])


class Workflow:
    def __init__(self, graph):
        self.graph, self.inputs = graph, {}

    def set_input(self, node, field, value):
        self.inputs[node, field] = value


class Client:
    def __init__(self, outputs):
        self.outputs, self.submitted, self.closed = outputs, [], False
        self.workflows = SimpleNamespace(from_json=Workflow)
        self.assets = SimpleNamespace(from_file=lambda path: f'asset:{path}')

    async def submit(self, workflow):
        self.submitted.append(workflow)
        return Handle(self.outputs)

    async def aclose(self):
        self.closed = True


def settings(tmp_path):
    return SimpleNamespace(proxy_url='https://one.run.comfy.app', workspace=tmp_path)


def test_schemas_are_read_once_per_deployment_and_kept_on_disk(tmp_path):
    body = json.dumps({'MajoorShotAssemble': {'input': {}}}).encode()
    client = Client({SCHEMA_NODE: [Output('file', SCHEMA_FILE, body)]})
    config = settings(tmp_path)
    assert cached_schemas(config) is None
    assert 'MajoorShotAssemble' in asyncio.run(fetch_schemas(client, config))
    assert cached_schemas(config) == {'MajoorShotAssemble': {'input': {}}}
    assert cached_schemas(SimpleNamespace(proxy_url='https://two.run.comfy.app', workspace=tmp_path)) is None


def test_missing_schema_output_is_reported(tmp_path):
    with pytest.raises(ValueError, match='node schemas'):
        asyncio.run(fetch_schemas(Client({}), settings(tmp_path)))


def test_brief_graphs_run_through_the_sdk_with_their_files(tmp_path):
    client = Client({'out': [Output('text', 'a.txt', 'A brief'.encode())]})
    photo = Path(tmp_path/'photo.png')
    texts = asyncio.run(brief_texts(client, {'ref1': [('12', 'image')]}, [{'12': {}}, {'3': {}}], {'ref1': photo}, 'out'))
    assert texts == ['A brief', 'A brief']
    assert client.submitted[0].inputs == {('12', 'image'): f'asset:{photo}'}
    assert client.submitted[1].inputs == {}


def test_empty_brief_is_refused(tmp_path):
    with pytest.raises(ValueError, match='empty brief'):
        asyncio.run(brief_texts(Client({}), {}, [{}], {}, 'out'))


@pytest.mark.parametrize('status,expected', [(200, True), (404, True), (401, False), (403, False), (503, False)])
def test_reachable_reads_the_answer_of_the_deployment(tmp_path, status, expected, monkeypatch):
    monkeypatch.setenv('COMFY_API_KEY', 'key')
    seen = {}

    class Probe:
        async def get(self, url, headers):
            seen.update(url=url, headers=headers)
            return httpx.Response(status)

    assert asyncio.run(reachable(settings(tmp_path), Probe())) is expected
    assert seen == {'url': 'https://one.run.comfy.app/api/v2/health', 'headers': {'Authorization': 'Bearer key'}}


def test_network_failure_is_not_reachable(tmp_path):
    class Probe:
        async def get(self, url, headers):
            raise httpx.ConnectError('down')

    assert asyncio.run(reachable(settings(tmp_path), Probe())) is False


def test_runner_sends_the_real_key_and_defaults_to_local(tmp_path, monkeypatch):
    keys = []
    monkeypatch.setattr('backend.runner.AsyncComfy', lambda api_key: keys.append(api_key))
    runner = ComfyRunner(Settings(comfyui_url='http://127.0.0.1:8188', proxy_url='http://127.0.0.1:8189', output_dir=tmp_path, workspace=tmp_path, templates_dir=tmp_path, mock=True), {})
    monkeypatch.delenv('COMFY_API_KEY', raising=False)
    runner.client_factory()
    monkeypatch.setenv('COMFY_API_KEY', 'real')
    runner.client_factory()
    assert keys == ['local', 'real']


def test_comfy_api_mode_needs_remote_storage_and_a_key(tmp_path, monkeypatch):
    monkeypatch.setenv('HYPERKUT_COMFY_API', '1')
    monkeypatch.setenv('HYPERKUT_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('HYPERKUT_STORAGE_BACKEND', 'shared_local')
    with pytest.raises(ValueError, match='remote_artifacts'):
        Settings.from_env()
    monkeypatch.setenv('HYPERKUT_STORAGE_BACKEND', 'remote_artifacts')
    monkeypatch.delenv('COMFY_API_KEY', raising=False)
    with pytest.raises(ValueError, match='COMFY_API_KEY'):
        Settings.from_env()
    monkeypatch.setenv('COMFY_API_KEY', 'key')
    assert Settings.from_env().comfy_api is True
