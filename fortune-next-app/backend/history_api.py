"""Separate Phase 4 routes; owner identity comes from verified server-side sessions."""
import logging
import sqlite3
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from history_repository import HistoryError
from history_service import make_service, validate_input
from auth_api import request_owner

router = APIRouter(prefix="/api/history")


async def handle(request, action, body=False):
    try:
        owner = request_owner(request)
        service = make_service()
        payload = await request.json() if body else None
        value = action(service, owner, payload)
        return {"ok": True, "data": value}
    except HistoryError as exc:
        return JSONResponse(status_code=exc.status, content={"ok": False, "error": str(exc)})
    except (sqlite3.Error, OSError):
        logging.getLogger(__name__).exception("History storage operation failed")
        return JSONResponse(status_code=503, content={"ok": False, "error": "履歴の保存先を利用できません。設定を確認してください。"})
    except (ValueError, TypeError, KeyError):
        return JSONResponse(status_code=422, content={"ok": False, "error": "履歴の入力形式が不正です。"})


@router.get("")
async def listing(request: Request, keyword: str = "", start: str = "", end: str = ""):
    from datetime import date
    def action(service, owner, _):
        for value in (start, end):
            if value:
                date.fromisoformat(value)
        if start and end and start > end:
            raise HistoryError("鑑定日の開始日と終了日を確認してください。")
        return service.repository.list(owner, keyword, start, end)
    return await handle(request, action)


@router.post("")
async def create(request: Request):
    def action(s,o,p):
        org=p.get("organization_id") if isinstance(p,dict) else None
        if org is not None:
            from product_api import identity,repositories
            identity(request)
            if not isinstance(org,str) or not org: raise HistoryError("Organizationを確認してください。",422)
            operations,_=repositories()
            operations.context(org,o)
        return s.create(o,p,organization_id=org)
    return await handle(request,action,True)


@router.post("/candidates")
async def candidates(request: Request):
    return await handle(request, lambda s, o, p: s.repository.candidates(o, validate_input({"form": p})), True)


@router.get("/groups/{group_id}/memos")
async def memos(group_id: str, request: Request):
    return await handle(request, lambda s, o, p: s.repository.memos(o, group_id))


@router.post("/persons/{person_id}")
async def update_person(person_id: str, request: Request):
    def action(service, owner, payload):
        validate_input(payload)
        service.repository.update_person(owner, person_id, payload)
        return {"updated": True}
    return await handle(request, action, True)


@router.get("/deleted")
async def deleted(request: Request):
    return await handle(request, lambda s,o,p: s.repository.deleted_list(o))


@router.post("/{reading_id}/restore")
async def restore(reading_id: str, request: Request):
    return await handle(request, lambda s,o,p: s.repository.restore(o,reading_id))


@router.get("/{reading_id}")
async def detail(reading_id: str, request: Request):
    return await handle(request, lambda s, o, p: s.detail(o, reading_id))


@router.patch("/{reading_id}/memo")
async def memo(reading_id: str, request: Request):
    def action(service, owner, payload):
        value = payload["memo"]
        if not isinstance(value, str) or len(value) > 100000:
            raise HistoryError("メモの形式が不正です。")
        return service.repository.update_memo(owner, reading_id, value, payload["updated_at"])
    return await handle(request, action, True)


@router.delete("/{reading_id}")
async def delete(reading_id: str, request: Request):
    def action(service, owner, _):
        service.repository.soft_delete(owner, reading_id)
        return {"deleted": True}
    return await handle(request, action)


@router.post("/{reading_id}/rerun")
async def rerun(reading_id: str, request: Request):
    return await handle(request, lambda s, o, p: s.prepare(o, reading_id, p["mode"]), True)
