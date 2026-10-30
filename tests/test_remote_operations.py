import hashlib
import io
import json
from types import SimpleNamespace

import pytest

from backend.artifact_contract import ArtifactRef
from backend.artifact_store import LocalArtifactStore
from backend.artifact_bundle import write_bundle
from backend.project_snapshot import capture_project
from backend.snapshot_worker import transform_snapshot
from backend.snapshot_repository import SnapshotRepository
from backend.operation_journal import OperationJournal
from backend.remote_operations import run_snapshot_edit, SubmissionUncertain
from test_artifact_transfer import output
from test_manual_timeline import editorial_project


async def test_rendered_result_recovers_download_without_submission(editorial_project,tmp_path):
    store=LocalArtifactStore(tmp_path/'cache')
    original=capture_project(store,editorial_project)
    repo=SnapshotRepository(tmp_path/'repo',store)
    repo.initialize(original)
    source=tmp_path/'input.zip'
    with source.open('wb') as stream: write_bundle(store,original,stream)
    operation={'kind':'set_prompt','project_id':original.project_id,'expected_revision':original.revision,
               'shot_id':'SHOT_001','prompt':'A paper moon.'}
    with source.open('rb') as stream:
        result,bundle,descriptor=transform_snapshot(stream,tmp_path/'worker',operation)
    digest=hashlib.sha256(json.dumps(operation,sort_keys=True,ensure_ascii=False,allow_nan=False).encode())
    digest.update(source.read_bytes())
    journal=OperationJournal(tmp_path/'operations')
    journal.prepare('op',request_sha256=digest.hexdigest(),project_id=original.project_id,expected_revision=original.revision)
    journal.transition('op','prepared','submitting')
    journal.transition('op','submitting','submitted',handle_id='sdk-own')
    journal.transition('op','submitted','rendered')
    outputs=[output('result.descriptor.json',descriptor.read_bytes()),output('result.snapshot.zip',bundle.read_bytes(),fail=True)]
    async def refresh(): pass
    handle=SimpleNamespace(get_outputs=lambda node:outputs,refresh=refresh)
    calls=[]
    async def get(handle_id):
        calls.append(handle_id)
        return handle
    client=SimpleNamespace(jobs=SimpleNamespace(get=get))  # No submit method: retries must not call it.
    with pytest.raises(ConnectionError):
        await run_snapshot_edit(client,operation_id='op',input_bundle=source,operation=operation,
            journal=journal,repository=repo,scratch=tmp_path/'scratch')
    assert journal.read('op')['status']=='rendered'
    outputs[1]=output('result.snapshot.zip',bundle.read_bytes())
    restored=await run_snapshot_edit(client,operation_id='op',input_bundle=source,operation=operation,
        journal=journal,repository=repo,scratch=tmp_path/'scratch')
    assert restored==result and repo.head(original.project_id)==result
    assert journal.read('op')['status']=='applied' and calls==['sdk-own','sdk-own']
    # A completed replay needs no SDK request and returns this operation's result.
    replay=await run_snapshot_edit(None,operation_id='op',input_bundle=source,operation=operation,
        journal=journal,repository=repo,scratch=tmp_path/'scratch')
    assert replay==result

def pending_operation(tmp_path,status):
    operation={'kind':'set_prompt','project_id':'p_12345678','expected_revision':1,'shot_id':'SHOT_001','prompt':'A'}
    source=tmp_path/'input.zip'
    source.write_bytes(b'input')
    digest=hashlib.sha256(json.dumps(operation,sort_keys=True,ensure_ascii=False,allow_nan=False).encode())
    digest.update(source.read_bytes())
    journal=OperationJournal(tmp_path/'journal')
    journal.prepare('op',request_sha256=digest.hexdigest(),project_id=operation['project_id'],expected_revision=1)
    journal.transition('op','prepared','submitting')
    if status=='submitted': journal.transition('op','submitting','submitted',handle_id='sdk-own')
    return operation,source,journal


async def test_uncertain_acceptance_never_resubmits(tmp_path):
    operation,source,journal=pending_operation(tmp_path,'submitting')
    with pytest.raises(SubmissionUncertain):
        await run_snapshot_edit(None,operation_id='op',input_bundle=source,operation=operation,
            journal=journal,repository=None,scratch=tmp_path/'scratch')
    assert journal.read('op')['status']=='submitting'


async def test_failed_sdk_job_is_not_marked_rendered(tmp_path):
    from comfy_sdk import JobFailed
    operation,source,journal=pending_operation(tmp_path,'submitted')
    async def wait(**kwargs): pass
    async def result(): raise JobFailed('synthetic failure')
    handle=SimpleNamespace(wait=wait,result=result)
    async def get(value): return handle
    client=SimpleNamespace(jobs=SimpleNamespace(get=get))
    with pytest.raises(JobFailed):
        await run_snapshot_edit(client,operation_id='op',input_bundle=source,operation=operation,
            journal=journal,repository=None,scratch=tmp_path/'scratch')
    assert journal.read('op')['status']=='failed'
    assert journal.read('op')['handle_id']=='sdk-own'


async def test_cancel_race_does_not_claim_cancellation_of_succeeded_job(tmp_path):
    import asyncio
    operation,source,journal=pending_operation(tmp_path,'submitted')
    calls=[]
    async def wait(**kwargs):
        calls.append('wait')
        if len(calls)==1: raise asyncio.CancelledError()
    async def cancel(): pass
    handle=SimpleNamespace(wait=wait,cancel=cancel,status='succeeded')
    async def get(value): return handle
    client=SimpleNamespace(jobs=SimpleNamespace(get=get))
    with pytest.raises(asyncio.CancelledError):
        await run_snapshot_edit(client,operation_id='op',input_bundle=source,operation=operation,
            journal=journal,repository=None,scratch=tmp_path/'scratch')
    assert journal.read('op')['status']=='submitted'
