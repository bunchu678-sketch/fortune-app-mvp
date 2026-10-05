"""Cookie authentication boundary. Browser identifiers never establish ownership."""
import logging
import json
import sqlite3
from urllib.parse import urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from auth_service import AuthError, AuthRepository, AuthSettings, COOKIE_NAME, token_hash
from history_service import development_owner

router = APIRouter(prefix="/api/auth")


class AuthBoundary:
    """Pure ASGI guard, including clients that do not use the UI."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        private_response = False
        if scope["type"] == "http":
            request = Request(scope)
            path = request.url.path
            owned = path == "/api/history" or path.startswith(("/api/history/", "/api/export/"))
            private_response = owned or path.startswith("/api/auth/") or path == "/api/fortune"
            try:
                if owned:
                    await run_in_threadpool(request_owner, request)
                if request.method in ("POST", "PATCH", "PUT", "DELETE") and (
                    owned or path.startswith("/api/auth/") or (path == "/api/fortune" and request.cookies.get(COOKIE_NAME))
                ):
                    csrf_check(request)
            except (AuthError, sqlite3.Error, OSError) as exc:
                await safe_error(exc)(scope, receive, send)
                return
        async def private_send(message):
            if private_response and message["type"] == "http.response.start":
                headers = [(k,v) for k,v in message.get("headers", []) if k.lower() != b"cache-control"]
                message = {**message, "headers": headers+[(b"cache-control", b"no-store")]}
            await send(message)
        await self.app(scope, receive, private_send)


def legacy_development():
    try:
        return development_owner()
    except Exception:
        return None


def session_scope(request):
    token = request.cookies.get(COOKIE_NAME)
    return token_hash(token) if token else None


def current_user(request, optional=False):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return AuthRepository().authenticate(token)
    owner = legacy_development()
    if owner:
        return {"id": owner, "email": "開発用利用者", "development": True}
    if optional:
        return None
    raise AuthError("ログインしてください。", 401)


def request_owner(request):
    return current_user(request)["id"]


def origin_parts(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            return None
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            return None
        return parsed.scheme, parsed.hostname.lower(), parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return None


def csrf_check(request):
    # No forwarded headers are trusted here. An explicit deployment origin handles reverse proxies.
    settings = AuthSettings.load()
    expected = origin_parts(settings.public_origin) if settings.public_origin else origin_parts(str(request.base_url))
    if settings.production and (not settings.public_origin or not expected or expected[0] != "https"):
        raise AuthError("認証設定を確認してください。", 503)
    origin = request.headers.get("origin")
    if not origin:
        referer = request.headers.get("referer", "")
        try:
            parsed = urlsplit(referer)
        except ValueError:
            raise AuthError("リクエストの送信元を確認してください。", 403) from None
        if parsed.scheme and parsed.netloc:
            origin = f"{parsed.scheme}://{parsed.netloc}"
    # Existing opt-in development regression clients have no browser Origin or Cookie.
    legacy = legacy_development() and not request.cookies.get(COOKIE_NAME) and not request.url.path.startswith("/api/auth/")
    if not origin and legacy:
        return
    if not origin or origin_parts(origin) != expected or request.headers.get("sec-fetch-site") == "cross-site":
        raise AuthError("リクエストの送信元を確認してください。", 403)
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise AuthError("JSON形式で送信してください。", 415)


def safe_error(exc):
    if isinstance(exc, AuthError):
        headers = {"Cache-Control": "no-store"}
        if exc.status == 429:
            headers["Retry-After"] = str(AuthSettings.load().login_window)
        return JSONResponse(status_code=exc.status, content={"ok": False, "error": str(exc)}, headers=headers)
    logging.getLogger(__name__).error("Authentication storage/configuration unavailable")
    return JSONResponse(status_code=503, content={"ok": False, "error": "認証の保存先を利用できません。"},
                        headers={"Cache-Control": "no-store"})


@router.post("/login")
async def login(request: Request):
    try:
        csrf_check(request)
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > 8192:
                raise AuthError("ログイン入力を確認してください。", 422)
            raw.extend(chunk)
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("email"), str) or not isinstance(payload.get("password"), str):
            raise AuthError("ログイン入力を確認してください。", 422)
        settings = AuthSettings.load()
        repository = AuthRepository()
        user, token = await run_in_threadpool(repository.login, payload["email"], payload["password"],
                                             settings=settings, previous_token=request.cookies.get(COOKIE_NAME),
                                             ip=request.client.host if request.client else "unknown")
        response = JSONResponse({"ok": True, "data": {"authenticated": True, "user": user}},
                                headers={"Cache-Control": "no-store"})
        response.set_cookie(COOKIE_NAME, token, max_age=settings.ttl_seconds,
                            httponly=True, secure=settings.production, samesite="lax", path="/")
        return response
    except (AuthError, sqlite3.Error, OSError) as exc:
        return safe_error(exc)
    except (ValueError, TypeError):
        return safe_error(AuthError("ログイン入力を確認してください。", 422))


@router.post("/logout")
async def logout(request: Request):
    try:
        csrf_check(request)
        token = request.cookies.get(COOKIE_NAME)
        if token:
            await run_in_threadpool(AuthRepository().logout, token)
        response = JSONResponse({"ok": True, "data": {"authenticated": False}}, headers={"Cache-Control": "no-store"})
        response.delete_cookie(COOKIE_NAME, path="/", secure=AuthSettings.load().production, httponly=True, samesite="lax")
        return response
    except (AuthError, sqlite3.Error, OSError) as exc:
        return safe_error(exc)


@router.get("/me")
async def me(request: Request):
    try:
        user = await run_in_threadpool(current_user, request)
        return JSONResponse({"ok": True, "data": {"authenticated": True, "user": user}}, headers={"Cache-Control": "no-store"})
    except (AuthError, sqlite3.Error, OSError) as exc:
        return safe_error(exc)
