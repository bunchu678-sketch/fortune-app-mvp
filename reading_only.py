"""Teacher deployment: authenticated, non-persistent reading operations only."""
import json
import logging
import os
import sqlite3
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from auth_api import csrf_check, safe_error
from auth_service import AuthError
from history_repository import HistoryError
from product_api import identity, repositories
from fortune_service import calculate_fortune
from teacher_presentation import MARI_SLUG, MARI_THEMES
from mari_prototype_access import require_prototype_reader

router = APIRouter(prefix="/api/reading")


def enabled():
    return os.environ.get("FORTUNE_DEPLOYMENT_SURFACE", "combined") == "teacher"


def response(data, status=200):
    return JSONResponse(data, status_code=status, headers={"Cache-Control": "no-store", "Vary": "Cookie"})


def context(request):
    user = identity(request)  # Real session only; no development owner fallback.
    require_prototype_reader(user['id'])  # Restriction only; existing access checks still follow.
    operations, _ledger = repositories()
    slug = os.environ.get("FORTUNE_READING_ORGANIZATION_SLUG", MARI_SLUG)
    with operations.auth.connection() as db:
        row = db.execute("""SELECT o.id FROM organizations o JOIN memberships m ON m.organization_id=o.id
            WHERE o.slug=? AND m.user_id=?""", (slug, user["id"])).fetchone()
    if not row:
        raise AuthError("このアプリの利用権限がありません。", 403)
    operations.context(row["id"], user["id"])  # Existing account/contract rules stay in force.
    return user, operations, row["id"]


def display_branding(operations, org, owner):
    value = operations.product.branding(org, owner)
    return {key: value[key] for key in ("display_name", "themes", "selected_theme_key", "presentation_mode", "thinking_groups") if key in value}


def projection(user, operations, org):
    return {"enabled": True, "user": user, "organization_id": org,
            "branding": display_branding(operations, org, user["id"]),
            "default_theme": {"key": "default", **MARI_THEMES["default"]}}


async def body(request, maximum=65536):
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > maximum:
            raise HistoryError("入力内容を確認してください。", 422)
        raw.extend(chunk)
    value = json.loads(raw) if raw else {}
    if not isinstance(value, dict):
        raise HistoryError("入力内容を確認してください。", 422)
    if any(key in value for key in ("organization_id", "organizationId", "owner_user_id", "user_id", "role")):
        raise HistoryError("入力内容を確認してください。", 422)
    return value


@router.get("/bootstrap")
async def bootstrap(request: Request):
    if not enabled():
        return response({"ok": True, "data": {"enabled": False}})
    data = {"enabled": True, "user": None, "organization_id": None, "branding": None,
            "default_theme": {"key": "default", **MARI_THEMES["default"]}}
    try:
        user, operations, org = await run_in_threadpool(context, request)
        data = await run_in_threadpool(projection, user, operations, org)
    except HistoryError as exc:
        if exc.status != 401:
            data["access_error"] = "利用権限を確認できません。管理者へお問い合わせください。"
    except (sqlite3.Error, OSError):
        return safe_error(AuthError("認証の保存先を利用できません。", 503))
    return response({"ok": True, "data": data})


@router.post("/theme")
async def theme(request: Request):
    if not enabled():
        return response({"ok": False, "error": "Not found"}, 404)
    try:
        csrf_check(request)
        user, operations, org = await run_in_threadpool(context, request)
        payload = await body(request, 16384)
        await run_in_threadpool(operations.product.select_theme, org, user["id"], payload["theme_key"])
        return response({"ok": True, "data": await run_in_threadpool(display_branding, operations, org, user["id"])})
    except HistoryError as exc:
        return response({"ok": False, "error": str(exc)}, exc.status)
    except (sqlite3.Error, OSError):
        return safe_error(AuthError("保存先を利用できません。", 503))
    except (ValueError, TypeError, KeyError):
        return safe_error(AuthError("入力内容を確認してください。", 422))


@router.post("/fortune")
async def fortune(request: Request):
    if not enabled():
        return response({"ok": False, "error": "Not found"}, 404)
    try:
        csrf_check(request)
        _user, _operations, _org = await run_in_threadpool(context, request)
        payload = await body(request)
        if payload.get("specificDatetimeEnabled") or payload.get("specificDatetimeCandidates"):
            raise HistoryError("このアプリでは特定日時の鑑定は利用できません。", 422)
        result = await run_in_threadpool(calculate_fortune, payload)
        # Authorization can change while a calculation is running.
        await run_in_threadpool(context, request)
        # No history, execution fingerprint, export token, browser-persistence or input logging.
        return response(result, 200 if result.get("ok") else 422)
    except HistoryError as exc:
        return response({"ok": False, "errors": [str(exc)]}, exc.status)
    except (sqlite3.Error, OSError):
        return safe_error(AuthError("保存先を利用できません。", 503))
    except (ValueError, TypeError):
        return response({"ok": False, "errors": ["鑑定入力を確認してください。"]}, 422)
    except Exception:
        logging.getLogger(__name__).error("Reading calculation failed")
        return response({"ok": False, "errors": ["鑑定処理に失敗しました。"]}, 500)
