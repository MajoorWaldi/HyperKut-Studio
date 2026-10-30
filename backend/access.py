"""Fail-closed local/jury admission for HTTP media, API and frontend routes."""
import base64
import asyncio
import binascii
import hmac
import ipaddress
import shutil
import time

from filelock import Timeout
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


class RequestTooLarge(HTTPException):
    def __init__(self):
        super().__init__(413, "Request body exceeds its limit.")


async def acquire_upload_quota(lock, timeout=30):
    started = time.monotonic()
    while True:
        try:
            lock.acquire(timeout=0)
            return
        except Timeout:
            if time.monotonic() - started >= timeout:
                raise HTTPException(503, "Upload storage is busy. Retry shortly.") from None
            await asyncio.sleep(.05)


def validate_access(settings):
    if settings.access_mode not in ("local", "jury"):
        raise ValueError("ACCESS_MODE must be local or jury")
    if settings.access_mode == "jury":
        if not settings.access_username or ":" in settings.access_username or len(settings.access_password) < 24:
            raise ValueError("Jury access requires ACCESS_USERNAME and an ACCESS_PASSWORD of at least 24 characters")
        if "*" in settings.allowed_hosts:
            raise ValueError("Jury access requires explicit ALLOWED_HOSTS, never a wildcard")
        if settings.output_dir is None:
            raise ValueError("Jury access requires a dedicated OUTPUT_DIR")
    for name in ("max_workspace_bytes", "min_free_disk_bytes"):
        value = getattr(settings, name)
        if type(value) is not int or value < 1:
            raise ValueError(f"{name} must be a positive integer")


class AccessMiddleware:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        settings = self.settings
        headers = Headers(scope=scope)
        status, message = None, ""
        if settings.access_mode == "local":
            host = (scope.get("client") or ("", 0))[0]
            try:
                local = ipaddress.ip_address(host).is_loopback
            except ValueError:
                local = host == "testclient"
            if not local:
                status, message = 403, "Remote access is disabled. Configure a dedicated authenticated jury instance."
        else:
            if scope.get("scheme") not in ("https", "wss"):
                status, message = 403, "Jury access requires HTTPS."
            else:
                encoded = headers.get("authorization", "")
                valid = False
                if encoded.startswith("Basic ") and len(encoded) <= 1024:
                    try:
                        decoded = base64.b64decode(encoded[6:], validate=True)
                        expected = (settings.access_username + ":" + settings.access_password).encode("utf-8")
                        valid = hmac.compare_digest(decoded, expected)
                    except (ValueError, binascii.Error):
                        valid = False
                if not valid:
                    status, message = 401, "Authentication required."
                elif scope["path"] == "/api/studio/restart":
                    status, message = 403, "Studio restart is restricted to the local operator."
        if status:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            else:
                challenge = {"WWW-Authenticate": 'Basic realm="HyperKut jury", charset="UTF-8"'} if status == 401 else {}
                await JSONResponse({"detail": message}, status_code=status, headers=challenge)(scope, receive, send)
            return
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        upload = scope["path"] == "/api/uploads"
        maximum = settings.max_upload_bytes + 1024**2 if upload else 16 * 1024**2
        length = headers.get("content-length")
        if length is not None and (not length.isascii() or not length.isdecimal()
                                   or len(length) > 20 or int(length) > maximum):
            await JSONResponse({"detail": "Request body exceeds its limit."}, status_code=413)(scope, receive, send)
            return
        if scope["method"] in ("POST", "PUT", "PATCH") and shutil.disk_usage(settings.workspace).free < settings.min_free_disk_bytes:
            await JSONResponse({"detail": "Not enough free disk space."}, status_code=507)(scope, receive, send)
            return
        received, started = 0, False
        async def limited_receive():
            nonlocal received
            event = await receive()
            if event["type"] == "http.request":
                received += len(event.get("body", b""))
                if received > maximum:
                    raise RequestTooLarge()
            return event
        async def tracked_send(event):
            nonlocal started
            if event["type"] == "http.response.start":
                started = True
            await send(event)
        try:
            await self.app(scope, limited_receive, tracked_send)
        except RequestTooLarge:
            if started:
                raise
            await JSONResponse({"detail": "Request body exceeds its limit."}, status_code=413)(scope, receive, send)
