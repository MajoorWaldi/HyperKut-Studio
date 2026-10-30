"""Experimental remote prompt edits with durable submission and artifact recovery.

This transport service is not the H3 generation runner. Callers must run its SDK
client in the dedicated endpoint process described by RemoteConnection.
"""
import asyncio
import hashlib
import json

from comfy_sdk import JobFailed

from .artifact_bundle import read_bundle
from .artifact_transfer import download_snapshot_outputs
from .remote_connection import probe_capabilities, require_capabilities
from .snapshot_repository import RevisionConflict
from .artifact_contract import ProjectSnapshot
from .project_snapshot import validate_snapshot


class SubmissionUncertain(RuntimeError):
    pass


async def run_snapshot_edit(client, *, operation_id, input_bundle, operation, journal, repository, scratch):
    if operation.get('kind') != 'set_prompt':
        raise ValueError('This service only supports explicit snapshot prompt edits')
    digest = hashlib.sha256(json.dumps(operation, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8'))
    with input_bundle.open('rb') as source:
        while chunk := source.read(65536):
            digest.update(chunk)
    record = journal.prepare(operation_id, request_sha256=digest.hexdigest(), project_id=operation['project_id'],
                             expected_revision=operation['expected_revision'])
    if record['status'] in ('cancelled','conflict','failed'):
        raise ValueError('Operation ended; use its retained result or start an explicit new operation')
    if record['status'] == 'applied':
        result = ProjectSnapshot.from_dict(record['result_snapshot'])
        validate_snapshot(repository.artifacts, result)
        return result
    if record['status'] == 'submitting':
        # A timeout may follow server acceptance. Do not guess or re-bill a render.
        raise SubmissionUncertain('Submission acceptance is unknown; reconcile its stable idempotency key before retrying')
    if record['status'] == 'prepared':
        capabilities = await probe_capabilities(client)
        require_capabilities(capabilities, operation='set_prompt')
        with input_bundle.open('rb') as source:
            incoming = read_bundle(repository.artifacts, source)
        if incoming.project_id != operation['project_id'] or incoming.revision != operation['expected_revision']:
            raise ValueError('Operation does not match its input snapshot')
        if repository.head(incoming.project_id) != incoming:
            raise RevisionConflict('Input snapshot is not the authoritative current project')
        workflow = client.workflows.from_json({'snapshot':{'class_type':'HyperKutSnapshotTransform',
                     'inputs':{'archive':'','operation_json':json.dumps(operation,ensure_ascii=False)}}})
        workflow.set_input('snapshot','archive',client.assets.from_file(input_bundle))
        journal.transition(operation_id,'prepared','submitting')
        submitting = asyncio.ensure_future(client.submit(workflow,idempotency_key=record['idempotency_key']))
        try:
            handle = await asyncio.shield(submitting)
        except asyncio.CancelledError:
            # Submission is shielded so the accepted handle can be retained.
            handle = await asyncio.shield(submitting)
            journal.transition(operation_id,'submitting','submitted',handle_id=handle.id)
            try:
                await asyncio.shield(handle.cancel())
                await asyncio.shield(handle.wait(timeout=10))
            except Exception:
                pass  # Persisted handle remains available for reconciliation.
            else:
                if handle.status == 'canceled':
                    journal.transition(operation_id,'submitted','cancelled')
            raise
        record = journal.transition(operation_id,'submitting','submitted',handle_id=handle.id)
    else:
        handle = await client.jobs.get(record['handle_id'])
    if record['status'] == 'submitted':
        try:
            await handle.wait(timeout=3600)
            await handle.result()
        except JobFailed:
            journal.transition(operation_id,'submitted','failed')
            raise
        except asyncio.CancelledError:
            try:
                await asyncio.shield(handle.cancel())
                await asyncio.shield(handle.wait(timeout=10))
            except Exception:
                pass
            else:
                if handle.status == 'canceled':
                    journal.transition(operation_id,'submitted','cancelled')
            raise
        record = journal.transition(operation_id,'submitted','rendered')
    await handle.refresh()
    result = await download_snapshot_outputs(handle,'snapshot',repository.artifacts,scratch)
    if result.project_id != record['project_id'] or result.revision != record['expected_revision']+1:
        raise ValueError('Worker result identity/revision differs from the requested operation')
    if record['status'] == 'rendered':
        record = journal.transition(operation_id,'rendered','downloaded',result_snapshot=result.to_dict())
    try:
        repository.commit(result,expected_revision=record['expected_revision'])
    except RevisionConflict:
        journal.transition(operation_id,'downloaded','conflict')
        raise
    journal.transition(operation_id,'downloaded','applied')
    return result
