import hashlib
import io
import json
from types import SimpleNamespace

import pytest

from backend.artifact_bundle import transfer_limit, write_bundle
from backend.artifact_contract import ArtifactRef, ProjectSnapshot
from backend.artifact_store import ArtifactIntegrityError, ArtifactQuotaError, LocalArtifactStore
from backend.artifact_transfer import download_snapshot_outputs
from backend.operation_journal import OperationJournal
from backend.project_snapshot import capture_project
from test_manual_timeline import editorial_project


def output(name, data, fail=False):
    async def send(sink):
        if fail:
            sink.write(data[:10])
            raise ConnectionError('download interrupted')
        for start in range(0, len(data), 65536):
            sink.write(data[start:start+65536])
    return SimpleNamespace(type='file', name=name, to_stream=send)


async def test_interrupted_download_retry_without_resubmitting(editorial_project, tmp_path):
    source = LocalArtifactStore(tmp_path / 'source')
    snapshot = capture_project(source, editorial_project)
    stream = io.BytesIO()
    write_bundle(source, snapshot, stream)
    data = stream.getvalue()
    descriptor = json.dumps({'artifact':ArtifactRef(hashlib.sha256(data).hexdigest(), len(data)).to_dict(), 'snapshot':snapshot.to_dict()}).encode()
    outputs = [output('result.descriptor.json', descriptor), output('result.snapshot.zip', data, fail=True)]
    handle = SimpleNamespace(get_outputs=lambda node: outputs)
    receiver = LocalArtifactStore(tmp_path / 'receiver')
    with pytest.raises(ConnectionError):
        await download_snapshot_outputs(handle, 'node', receiver, tmp_path / 'scratch')
    assert not list((tmp_path / 'scratch').glob('transfer-*'))
    outputs[1] = output('result.snapshot.zip', data)
    assert await download_snapshot_outputs(handle, 'node', receiver, tmp_path / 'scratch') == snapshot


async def test_transfer_limit_enforced_without_output_size_metadata(tmp_path):
    handle = SimpleNamespace(get_outputs=lambda node: [output('x.descriptor.json', b'x' * (16*1024*1024+1)), output('x.snapshot.zip', b'')])
    with pytest.raises(ArtifactQuotaError):
        await download_snapshot_outputs(handle, 'node', LocalArtifactStore(tmp_path/'cache'), tmp_path/'scratch')


async def test_transfer_preflights_archive_size_before_downloading(tmp_path):
    receiver = LocalArtifactStore(tmp_path / "receiver")
    maximum = transfer_limit(receiver)
    digest = hashlib.sha256(b"not-downloaded").hexdigest()
    snapshot = ProjectSnapshot(
        "p_0123456789ab", 1,
        ArtifactRef(hashlib.sha256(b"manifest").hexdigest(), len(b"manifest")),
    )
    descriptor = json.dumps({
        "artifact": ArtifactRef(digest, maximum + 1).to_dict(),
        "snapshot": snapshot.to_dict(),
    }).encode()
    calls = []

    async def download(_sink):
        calls.append(True)

    outputs = [
        output("result.descriptor.json", descriptor),
        SimpleNamespace(type="file", name="result.snapshot.zip", to_stream=download),
    ]
    handle = SimpleNamespace(get_outputs=lambda _node: outputs)
    with pytest.raises(ArtifactQuotaError, match="effective transfer limit"):
        await download_snapshot_outputs(handle, "node", receiver, tmp_path / "scratch")
    assert calls == []


def test_journal_identity_survives_restart_and_download_failure(tmp_path):
    journal = OperationJournal(tmp_path)
    record = journal.prepare('op_1', request_sha256='a'*64, project_id='p_12345678', expected_revision=0)
    journal.transition('op_1', 'prepared', 'submitting')
    journal.transition('op_1', 'submitting', 'submitted', handle_id='sdk-123')
    journal.transition('op_1', 'submitted', 'rendered')
    restored = OperationJournal(tmp_path)
    again = restored.prepare('op_1', request_sha256='a'*64, project_id='p_12345678', expected_revision=0)
    assert again['handle_id'] == 'sdk-123' and again['status'] == 'rendered'
    assert again['idempotency_key'] == record['idempotency_key']
    restored.transition('op_1', 'rendered', 'downloaded')
    restored.transition('op_1', 'downloaded', 'applied')
    assert restored.read('op_1')['handle_id'] == 'sdk-123'


def test_journal_rejects_reuse_and_wrong_handle(tmp_path):
    journal = OperationJournal(tmp_path)
    journal.prepare('op', request_sha256='a'*64, project_id='p_12345678', expected_revision=1)
    with pytest.raises(ValueError):
        journal.prepare('op', request_sha256='b'*64, project_id='p_12345678', expected_revision=1)
    journal.transition('op', 'prepared', 'submitting')
    journal.transition('op', 'submitting', 'submitted', handle_id='sdk-one')
    with pytest.raises(ValueError):
        journal.transition('op', 'submitted', 'rendered', handle_id='sdk-two')
    with pytest.raises(ValueError):
        journal.transition('op', 'prepared', 'cancelled')
