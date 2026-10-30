"""Explicit experimental snapshot edit client. Credentials stay in process environment.

Run in a separate process with COMFY_BASE_URL and COMFY_API_KEY configured.
No H3, automatic deployment or generation mode switching.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comfy_sdk import AsyncComfy
from backend.artifact_store import LocalArtifactStore
from backend.artifact_bundle import read_bundle
from backend.remote_connection import RemoteConnection
from backend.operation_journal import OperationJournal
from backend.snapshot_repository import SnapshotRepository
from backend.remote_operations import run_snapshot_edit


async def run(args):
    connection = RemoteConnection(os.environ.get('COMFY_BASE_URL',''),os.environ.get('COMFY_API_KEY',''))
    # This executable already is a dedicated child; never use it in the live server process.
    cache = LocalArtifactStore(args.workspace/'artifacts')
    repository = SnapshotRepository(args.workspace/'projects',cache)
    operation = json.loads(args.operation.read_text(encoding='utf-8'))
    if args.initialize:
        with args.input.open('rb') as source:
            repository.initialize(read_bundle(cache,source))
    client = AsyncComfy(api_key=connection.api_key)
    try:
        result = await run_snapshot_edit(client,operation_id=args.operation_id,input_bundle=args.input,
            operation=operation,journal=OperationJournal(args.workspace/'operations'),repository=repository,
            scratch=args.workspace/'downloads')
        print(json.dumps({'project_id':result.project_id,'revision':result.revision}))
    finally:
        await client.aclose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input',required=True,type=Path)
    parser.add_argument('--operation',required=True,type=Path)
    parser.add_argument('--operation-id',required=True)
    parser.add_argument('--workspace',required=True,type=Path)
    parser.add_argument('--initialize',action='store_true',help='Explicitly seed an empty repository from a trusted input snapshot')
    asyncio.run(run(parser.parse_args()))
