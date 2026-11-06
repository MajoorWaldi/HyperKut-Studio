"""Does the Comfy API key of ANOTHER account reach this deployment? Read-only: no job is submitted and no GPU worker is started.

    COMFY_BASE_URL=https://<your deployment> COMFY_OWNER_KEY=<your key> COMFY_OTHER_KEY=<key of a second account> \
        .venv/Scripts/python scripts/probe_second_key.py

Keys are read from the environment and never printed. For each key it prints the HTTP status of two read routes.
Reading the result: the owner key answers 200 on both. If the other key answers 401/403, a visitor's own key does NOT open your deployment
(so a bring-your-own-key Studio would need each visitor to deploy their own build). If it answers 200 on both, a visitor's key is accepted here.
"""
import os
import sys

import httpx

ROUTES = ("/api/v2/health", "/api/v2/jobs")


def main() -> int:
    base = os.environ.get("COMFY_BASE_URL", "").rstrip("/")
    keys = {"owner": os.environ.get("COMFY_OWNER_KEY", ""), "other": os.environ.get("COMFY_OTHER_KEY", "")}
    if not base.startswith("https://") or not all(keys.values()):
        print("Set COMFY_BASE_URL (https) , COMFY_OWNER_KEY and COMFY_OTHER_KEY.", file=sys.stderr)
        return 2
    styles = {"bearer": lambda key: {"Authorization": f"Bearer {key}"}, "x-api-key": lambda key: {"X-API-Key": key}}
    for who, key in keys.items():
        for style, headers in styles.items():
            for route in ROUTES:
                try:
                    status = httpx.get(base + route, headers=headers(key), timeout=30).status_code
                except httpx.HTTPError as error:
                    status = type(error).__name__
                print(f"{who:6} {style:9} {route:16} {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
