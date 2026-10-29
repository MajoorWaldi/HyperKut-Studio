"""Run a job on the studio from the command line (the same API as the interface): upload the files, start the job, follow it until it ends.

    python scripts/run_job.py remix --source clip.mp4 --ref portrait.png --prompt "..." [--quality draft] [--url http://127.0.0.1:8090]
"""
import argparse
import json
import mimetypes
import sys
from pathlib import Path

import httpx


def upload(client: httpx.Client, path: str) -> str:
    file = Path(path)
    response = client.post("/api/uploads", files={"file": (file.name, file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")})
    response.raise_for_status()
    return response.json()["id"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["remix", "text", "music"])
    parser.add_argument("--source")
    parser.add_argument("--ref", action="append", default=[])
    parser.add_argument("--music")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--quality", default="draft", choices=["draft", "standard", "max"])
    parser.add_argument("--duration", type=float, default=8.0)
    parser.add_argument("--audio", default=None, choices=["original", "new", "voice"])
    parser.add_argument("--url", default="http://127.0.0.1:8090")
    args = parser.parse_args()
    with httpx.Client(base_url=args.url, timeout=None) as client:
        body = {"mode": args.mode, "source": upload(client, args.source) if args.source else None, "refs": [upload(client, r) for r in args.ref], "music": upload(client, args.music) if args.music else None,
                "settings": {"prompt": args.prompt, "quality": args.quality, "duration": args.duration, "audio": args.audio or ("original" if args.mode == "remix" else "new")}}
        response = client.post("/api/jobs", json=body)
        if response.status_code >= 400:
            print(response.text, file=sys.stderr)
            return 1
        job = response.json()["id"]
        print("job", job)
        last = ""
        with client.stream("GET", f"/api/jobs/{job}/events") as events:
            for line in events.iter_lines():
                if not line.startswith("data: "):
                    continue
                state = json.loads(line[6:])
                shots = f" shots {sum(s['done'] for s in state['shots'])}/{len(state['shots'])}" if state["shots"] else ""
                text = f"{state['status']:9} {state['stage']:7} {state['progress'] * 100:5.1f}%{shots}"
                if text != last:
                    print(text, flush=True)
                    last = text
        print("error:" if state["error"] else "video:", state["error"] or state["output_url"])
        return 0 if state["status"] == "succeeded" else 1


if __name__ == "__main__":
    sys.exit(main())
