"""Fail-closed local/jury admission for HTTP media, API and frontend routes."""
import base64
import asyncio
import binascii
import contextvars
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import shutil
from pathlib import Path

from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from .storage import write_json

GENERATION_ROUTE = re.compile(r'^/api/jobs(/[^/]+/(resume|regenerate|approve)|/[^/]+/shots/[^/]+/ai-candidates)?$')
# What reaches the GPU without being a generation: a wider quota, but still a limit on the bill of a public instance.
ACTION_ROUTE = re.compile(r'^/api/(brief-preview|brief-treatments|jobs/[^/]+/(re-edit|manual-timeline/render)|jobs/[^/]+/shots/[^/]+/take-edit)$')
ACTIONS_PER_GENERATION = 4
VISITOR_COOKIE = 'hyperkut_visitor'
VISITOR_COOKIE_VALUE = re.compile(rf'(?:^|;\s*){VISITOR_COOKIE}=([0-9a-f]{{32}})(?:;|$)')
VISITOR_COOKIE_DAYS = 30
current_visitor: contextvars.ContextVar[str | None] = contextvars.ContextVar('hyperkut_visitor', default=None)
FORWARDING_HEADERS = ('cf-connecting-ip', 'x-forwarded-for', 'x-forwarded-host', 'forwarded', 'x-real-ip')
CLOSED_ROUTES = (
    ('POST', re.compile(r'^/api/(studio/restart|projects/import|storage/worker/cleanup|storage/cache/gc|storage/caches/clean)$')),
    ('POST', re.compile(r'^/api/jobs/[^/]+/free$')),
    ('DELETE', re.compile(r'^/api/(jobs|presets)/[^/]+$')),
    ('PATCH', re.compile(r'^/api/jobs/[^/]+$')),
    ('POST', re.compile(r'^/api/presets$')),
)


class RequestTooLarge(HTTPException):
    def __init__(self):
        super().__init__(413, "Request body exceeds its limit.")


async def acquire_upload_quota(lock, timeout=30):
    from .capacity import CapacityBusy, acquire_async
    try:
        await acquire_async(lock, timeout)
    except CapacityBusy:
        raise HTTPException(503, "Upload storage is busy. Retry shortly.") from None


class JuryQuota:
    """Generations a public jury instance may start: a cap per visitor and one in total, kept on disk across restarts."""

    def __init__(self, path: Path, per_visitor: int, total: int):
        self.path, self.per_visitor, self.total = path, per_visitor, total
        self.lock = asyncio.Lock()
        try:
            self.used = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.used = {'total': 0, 'visitors': {}}
        self.used.setdefault('actions', {'total': 0, 'visitors': {}})

    @staticmethod
    def visitor(scope, headers) -> str:
        peer = (scope.get('client') or ('unknown', 0))[0]
        try:
            behind_tunnel = ipaddress.ip_address(peer).is_loopback  # the tunnel runs on this machine; from anywhere else the header is the caller's own claim
        except ValueError:
            behind_tunnel = False
        address = (headers.get('cf-connecting-ip') if behind_tunnel else None) or peer
        return hashlib.sha256(address.encode()).hexdigest()[:16]

    async def reserve(self, visitor: str) -> str | None:
        """None when a generation was reserved, otherwise the reason it is refused."""
        async with self.lock:
            if self.used['total'] >= self.total:
                return f'The jury demonstration reached its limit of {self.total} generations.'
            if self.used['visitors'].get(visitor, 0) >= self.per_visitor:
                return f'You have used your {self.per_visitor} generations of the jury demonstration.'
            self._add(visitor, 1)
        return None

    async def refund(self, visitor: str) -> None:
        async with self.lock:
            self._add(visitor, -1)

    async def act(self, visitor: str) -> str | None:
        """The same for a lighter use of the GPU: an analysis, a direction preview or a new edit."""
        actions = self.used['actions']
        async with self.lock:
            if actions['total'] >= self.total * ACTIONS_PER_GENERATION or actions['visitors'].get(visitor, 0) >= self.per_visitor * ACTIONS_PER_GENERATION:
                return 'The jury demonstration reached its limit of previews and new edits.'
            self._add_action(visitor, 1)
        return None

    async def refund_action(self, visitor: str) -> None:
        async with self.lock:
            self._add_action(visitor, -1)

    async def trade(self, visitor: str) -> str | None:
        """Pay with an action instead of the generation this visitor holds."""
        reason = await self.act(visitor)
        if reason is None:
            await self.refund(visitor)
        return reason

    def _add(self, visitor: str, step: int) -> None:
        self.used['total'] = max(0, self.used['total'] + step)
        self.used['visitors'][visitor] = max(0, self.used['visitors'].get(visitor, 0) + step)
        write_json(self.path, self.used)

    def _add_action(self, visitor: str, step: int) -> None:
        actions = self.used['actions']
        actions['total'] = max(0, actions['total'] + step)
        actions['visitors'][visitor] = max(0, actions['visitors'].get(visitor, 0) + step)
        write_json(self.path, self.used)


class JuryOwners:
    """Who made what on a public instance: a visitor reaches only their own uploads and projects."""

    def __init__(self, path: Path):
        self.path = path
        try:
            self.owned = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.owned = {}

    def claim(self, item: str) -> None:
        self.owned[item] = current_visitor.get()
        write_json(self.path, self.owned)

    def allows(self, item: str) -> bool:
        return item in self.owned and self.owned[item] == current_visitor.get()


def validate_access(settings):
    if settings.access_mode not in ("local", "jury", "jury_open"):
        raise ValueError("ACCESS_MODE must be local, jury or jury_open")
    if settings.access_mode == "jury_open":
        if "*" in settings.allowed_hosts:
            raise ValueError("Jury access requires explicit ALLOWED_HOSTS, never a wildcard")
        if settings.output_dir is None:
            raise ValueError("Jury access requires a dedicated OUTPUT_DIR")
        if settings.jury_visitor_limit < 1 or settings.jury_total_limit < settings.jury_visitor_limit:
            raise ValueError("JURY_VISITOR_LIMIT must be at least 1 and JURY_TOTAL_LIMIT at least that large")
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
        self.quota = JuryQuota(settings.workspace / 'jury-quota.json', settings.jury_visitor_limit, settings.jury_total_limit) if settings.access_mode == 'jury_open' else None

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
            if local and any(name in headers for name in FORWARDING_HEADERS):
                local = False  # a local tunnel or reverse proxy makes remote callers look like loopback
            if not local:
                status, message = 403, "Remote access is disabled. Configure a dedicated authenticated jury instance."
        elif scope.get("scheme") not in ("https", "wss"):
            status, message = 403, "Jury access requires HTTPS."
        elif settings.access_mode == "jury_open":
            if scope["type"] == "http" and any(scope["method"] == method and route.match(scope["path"]) for method, route in CLOSED_ROUTES):
                status, message = 403, "Not available on the public jury instance."
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
        media_upload = scope["path"] == "/api/uploads"
        project_import = scope["path"] == "/api/projects/import"
        body_limit = max(settings.max_upload_bytes, settings.max_workspace_bytes) if project_import else settings.max_upload_bytes if media_upload else 16 * 1024**2
        maximum = body_limit + 1024**2 if media_upload or project_import else body_limit
        length = headers.get("content-length")
        if length is not None and (not length.isascii() or not length.isdecimal()
                                   or len(length) > 20 or int(length) > maximum):
            await JSONResponse({"detail": "Request body exceeds its limit."}, status_code=413)(scope, receive, send)
            return
        if scope["method"] in ("POST", "PUT", "PATCH") and shutil.disk_usage(settings.workspace).free < settings.min_free_disk_bytes:
            await JSONResponse({"detail": "Not enough free disk space."}, status_code=507)(scope, receive, send)
            return
        new_owner = None
        if self.quota:
            known = VISITOR_COOKIE_VALUE.search(headers.get('cookie', ''))
            new_owner = None if known else secrets.token_hex(16)  # a random cookie and not the address: people on one network keep their projects apart
            current_visitor.set(known.group(1) if known else new_owner)
        hold: dict = {}  # what this request holds of the quota: the endpoint of a plan that waits for approval trades it
        if self.quota and scope["method"] == "POST" and (GENERATION_ROUTE.match(scope["path"]) or ACTION_ROUTE.match(scope["path"])):
            generation = GENERATION_ROUTE.match(scope["path"])
            hold = {"visitor": self.quota.visitor(scope, headers), "quota": self.quota, "refund": self.quota.refund if generation else self.quota.refund_action}
            reason = await (self.quota.reserve if generation else self.quota.act)(hold["visitor"])
            if reason:
                await JSONResponse({"detail": reason}, status_code=429)(scope, receive, send)
                return
            scope["jury_hold"] = hold
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
                if hold.get("visitor") and event["status"] >= 400:
                    await hold["refund"](hold.pop("visitor"))
                if new_owner:
                    cookie = f'{VISITOR_COOKIE}={new_owner}; Path=/; Max-Age={VISITOR_COOKIE_DAYS * 86400}; HttpOnly; Secure; SameSite=Lax'
                    event = {**event, 'headers': [*event.get('headers', []), (b'set-cookie', cookie.encode())]}
            await send(event)
        try:
            await self.app(scope, limited_receive, tracked_send)
        except RequestTooLarge:
            if started:
                raise
            if hold.get("visitor"):
                await hold["refund"](hold.pop("visitor"))
            await JSONResponse({"detail": "Request body exceeds its limit."}, status_code=413)(scope, receive, send)
