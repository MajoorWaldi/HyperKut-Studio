"""First contact with the Comfy SDK against a local ComfyUI behind comfy-api-proxy: submit an API-format prompt of ours, follow its events, read its outputs.

    COMFY_BASE_URL=http://127.0.0.1:8189 .venv/Scripts/python scripts/spike_sdk.py <workflow_api.json> [node_id ...]
"""
import asyncio
import sys

from comfy_sdk import AsyncComfy, ComfyError


async def main(path: str, nodes: list[str]) -> None:
    client = AsyncComfy(api_key="local")
    try:
        workflow = client.workflows.from_file(path)
        job = await client.submit(workflow)
        print("submitted", job.id if hasattr(job, "id") else job)
        async for event in job.events():
            print("event", type(event).__name__, str(event)[:160])
        print("status", await job.wait() if hasattr(job, "wait") else "?")
        for node in nodes:
            outputs = job.get_outputs(node)
            print("outputs of", node, [type(o).__name__ + ":" + str(getattr(o, "name", "")) for o in outputs])
    except ComfyError as error:
        print("COMFY ERROR", type(error).__name__, str(error)[:600])
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2:]))
