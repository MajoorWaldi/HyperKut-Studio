#!/usr/bin/env bash
# HyperKut Studio on a small RunPod pod with no GPU; generations run on a Comfy API deployment.
# The Studio stays on 127.0.0.1 and is reached only through a Cloudflare tunnel, so the pod exposes no port.
# Set these as pod environment variables, never in this file:
#   COMFY_BASE_URL, COMFY_API_KEY, CLOUDFLARE_TUNNEL_TOKEN
# Usage: bash hyperkut-pod.sh setup | start | stop | update | status | clean
set -euo pipefail

ROOT=${HYPERKUT_ROOT:-/workspace/hyperkut}
PACK=$ROOT/ComfyUI-Majoor-VideoTools
STUDIO="$PACK/HyperKut Studio"
LOGS=$ROOT/logs
PORT=8090
PUBLIC_HOST=${HYPERKUT_PUBLIC_HOST:-hyperkut.majoor.studio}
BRANCH=${HYPERKUT_BRANCH:-add/text-music-creative-pipeline}
VISITOR_LIMIT=${HYPERKUT_JURY_VISITOR_LIMIT:-5}
TOTAL_LIMIT=${HYPERKUT_JURY_TOTAL_LIMIT:-15}

NODE_VERSION=22.20.0
CLOUDFLARED_VERSION=2026.10.7
CLOUDFLARED_SHA256=1f99fb518b83dec2ba8d870a7cc991d82a77e6196295a3d2754ba17ab9f91872

checkout() { # url folder branch
    if [ ! -d "$2/.git" ]; then
        git init -q "$2"
        git -C "$2" remote add origin "$1"
    fi
    git -C "$2" fetch -q --depth 1 origin "$3"
    git -C "$2" checkout -q FETCH_HEAD
}

setup() {
    [ -d /workspace ] || { echo 'No /workspace volume on this pod' >&2; exit 1; }
    mkdir -p "$ROOT" "$LOGS"
    apt-get update -qq
    apt-get install -y -qq ffmpeg git curl xz-utils libgl1 libglib2.0-0 >/dev/null
    ffmpeg -version | head -1

    checkout https://github.com/MajoorWaldi/ComfyUI-Majoor-VideoTools "$PACK" "$BRANCH"
    checkout https://github.com/MajoorWaldi/HyperKut-Studio "$STUDIO" "$BRANCH"

    [ -x "$STUDIO/.venv/bin/python" ] || python3 -m venv "$STUDIO/.venv"
    "$STUDIO/.venv/bin/pip" install -q -r "$STUDIO/requirements.txt" -r "$PACK/requirements.txt"

    local node=node-v$NODE_VERSION-linux-x64
    if [ ! -x "$ROOT/$node/bin/node" ]; then
        curl -fsSL -o "$ROOT/$node.tar.xz" "https://nodejs.org/dist/v$NODE_VERSION/$node.tar.xz"
        curl -fsSL -o "$ROOT/node-sums.txt" "https://nodejs.org/dist/v$NODE_VERSION/SHASUMS256.txt"
        (cd "$ROOT" && grep " $node.tar.xz\$" node-sums.txt | sha256sum -c --status)
        tar -xf "$ROOT/$node.tar.xz" -C "$ROOT"
        rm -f "$ROOT/$node.tar.xz" "$ROOT/node-sums.txt"
    fi
    (cd "$STUDIO/frontend" && PATH="$ROOT/$node/bin:$PATH" npm ci --silent && PATH="$ROOT/$node/bin:$PATH" npm run build --silent)

    if [ ! -x "$ROOT/cloudflared" ]; then
        curl -fsSL -o "$ROOT/cloudflared.partial" "https://github.com/cloudflare/cloudflared/releases/download/$CLOUDFLARED_VERSION/cloudflared-linux-amd64"
        echo "$CLOUDFLARED_SHA256  $ROOT/cloudflared.partial" | sha256sum -c --status
        chmod +x "$ROOT/cloudflared.partial"
        mv "$ROOT/cloudflared.partial" "$ROOT/cloudflared"
    fi
    echo 'Setup complete. Next: bash hyperkut-pod.sh start'
}

start() {
    local name
    for name in COMFY_BASE_URL COMFY_API_KEY CLOUDFLARE_TUNNEL_TOKEN; do
        [ -n "${!name:-}" ] || { echo "$name is not set on this pod" >&2; exit 1; }
    done
    mkdir -p "$LOGS" "$ROOT/studio-workspace" "$ROOT/studio-output"

    if ! pgrep -f 'uvicorn backend.server:create_app' >/dev/null; then
        # Only the tunnel on this machine connects, and its forwarded headers are the only ones trusted.
        (cd "$STUDIO" && \
            HYPERKUT_COMFY_API=1 HYPERKUT_STORAGE_BACKEND=remote_artifacts HYPERKUT_ACCESS_MODE=jury_open \
            HYPERKUT_JURY_VISITOR_LIMIT="$VISITOR_LIMIT" HYPERKUT_JURY_TOTAL_LIMIT="$TOTAL_LIMIT" \
            HYPERKUT_WORKSPACE="$ROOT/studio-workspace" HYPERKUT_OUTPUT_DIR="$ROOT/studio-output" \
            HYPERKUT_ALLOWED_HOSTS="$PUBLIC_HOST" HYPERKUT_VIDEOTOOLS_DIR="$PACK" HYPERKUT_MAX_ACTIVE_JOBS=1 \
            nohup .venv/bin/python -m uvicorn backend.server:create_app --factory --host 127.0.0.1 --port "$PORT" \
                --proxy-headers --forwarded-allow-ips 127.0.0.1 > "$LOGS/studio.log" 2>&1 &)
    fi
    sleep 5
    pgrep -f 'uvicorn backend.server:create_app' >/dev/null || { echo "The Studio did not start, see $LOGS/studio.log" >&2; exit 1; }

    if ! pgrep -f 'cloudflared tunnel' >/dev/null; then
        (TUNNEL_TOKEN="$CLOUDFLARE_TUNNEL_TOKEN" nohup "$ROOT/cloudflared" tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" run > "$LOGS/tunnel.log" 2>&1 &)
    fi
    sleep 5
    pgrep -f 'cloudflared tunnel' >/dev/null || { echo "The tunnel did not start, see $LOGS/tunnel.log" >&2; exit 1; }
    echo "Studio: https://$PUBLIC_HOST/ ($VISITOR_LIMIT generations per visitor, $TOTAL_LIMIT in total)"
}

stop() {
    pkill -f 'cloudflared tunnel' || true
    pkill -f 'uvicorn backend.server:create_app' || true
    echo 'Services stopped. The pod is still billing: stop it from RunPod.'
}

status() {
    pgrep -f 'uvicorn backend.server:create_app' >/dev/null && echo 'Studio: running' || echo 'Studio: down'
    pgrep -f 'cloudflared tunnel' >/dev/null && echo 'Tunnel: running' || echo 'Tunnel: down'
    [ -f "$ROOT/studio-workspace/jury-quota.json" ] && cat "$ROOT/studio-workspace/jury-quota.json" && echo
    df -h "$ROOT" | tail -1
}

update() {
    stop
    setup
    start
}

clean() {
    stop
    rm -rf "$ROOT"
    echo "Removed $ROOT"
}

case "${1:-}" in
    setup|start|stop|update|status|clean) "$1" ;;
    *) echo 'Usage: bash hyperkut-pod.sh setup | start | stop | update | status | clean' >&2; exit 2 ;;
esac
