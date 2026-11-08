"""Local operator authentication. Not a public-hosting or OS security boundary."""
import hmac
import json
import secrets
import time
from pathlib import Path

from fastapi.responses import FileResponse, JSONResponse


class BodyLimit:
    """Bound mutation bodies before a JSON decoder or upload parser sees them."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] in ('GET', 'HEAD', 'OPTIONS'):
            return await self.app(scope, receive, send)
        limit = 5 * 1024 * 1024 if scope['path'] == '/api/import' else 16384
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body.extend(message.get('body', b''))
            if len(body) > limit:
                response = JSONResponse({'detail': 'Request body is too large'}, status_code=413)
                return await response(scope, receive, send)
            if not message.get('more_body', False):
                break
        delivered = False
        async def bounded_receive():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
        await self.app(scope, bounded_receive, send)


class LocalAccess:
    def __init__(self, name, static, key=None, clock=time.monotonic):
        self.key = key or secrets.token_urlsafe(32)
        if not isinstance(self.key, str) or len(self.key) < 32:
            raise ValueError("Local access key must contain at least 32 characters")
        self.cookie = name + "_session"
        self.static = Path(static)
        self.clock = clock
        self.sessions = {}
        self.failures = 0
        self.blocked_until = 0
        self.ttl = 8 * 60 * 60

    async def guard(self, request, call_next):
        now = self.clock()
        self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
        path = request.url.path
        origin = request.headers.get("origin")
        foreign = origin and origin != str(request.base_url).rstrip("/")
        foreign = foreign or request.headers.get("sec-fetch-site") == "cross-site"
        if foreign and path == "/" and request.method == "GET":
            response = FileResponse(self.static / "unlock.html")
        elif foreign and path not in ("/static/unlock.js", "/static/unlock.css"):
            response = JSONResponse({"detail": "Cross-origin access rejected"}, status_code=403)
        elif path == "/auth/login" and request.method == "POST":
            response = await self.login(request)
        elif path == "/auth/logout" and request.method == "POST":
            self.sessions.pop(request.cookies.get(self.cookie, ""), None)
            response = JSONResponse({"status": "locked"})
            response.delete_cookie(self.cookie, path="/", httponly=True, samesite="strict")
        elif path in ("/static/unlock.js", "/static/unlock.css") or path == "/healthz":
            response = await call_next(request)
        elif request.cookies.get(self.cookie, "") not in self.sessions:
            if path == "/" and request.method == "GET":
                response = FileResponse(self.static / "unlock.html")
            else:
                response = JSONResponse({"detail": "Unlock this local app first"}, status_code=401)
        else:
            response = await call_next(request)
        response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        return response

    async def login(self, request):
        if self.clock() < self.blocked_until:
            return JSONResponse({"detail": "Too many attempts. Wait 30 seconds and try again."}, status_code=429, headers={"Retry-After": "30"})
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"detail": "Expected JSON containing an access key"}, status_code=415)
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 4096:
                return JSONResponse({"detail": "Login request is too large"}, status_code=413)
        try:
            value = json.loads(raw)
            if not isinstance(value, dict) or set(value) != {"key"} or not isinstance(value["key"], str) or not 1 <= len(value["key"]) <= 256:
                raise ValueError()
            supplied = value["key"]
        except (ValueError, UnicodeError, RecursionError):
            return JSONResponse({"detail": "Enter the access key shown in the app terminal"}, status_code=400)
        if not hmac.compare_digest(supplied.encode("utf-8", errors="replace"), self.key.encode()):
            self.failures += 1
            if self.failures >= 5:
                self.blocked_until = self.clock() + 30
                self.failures = 0
            return JSONResponse({"detail": "Incorrect access key"}, status_code=401)
        self.failures = 0
        if len(self.sessions) >= 8:
            del self.sessions[next(iter(self.sessions))]
        session = secrets.token_urlsafe(32)
        self.sessions[session] = self.clock() + self.ttl
        response = JSONResponse({"status": "unlocked"})
        # HTTP is restricted to loopback. HTTPS/public deployment is unsupported.
        response.set_cookie(self.cookie, session, httponly=True, samesite="strict", max_age=self.ttl, path="/")
        return response
