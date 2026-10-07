"""Reset endpoints are inert for mail requests until a trusted service is explicitly configured."""
import json
import sqlite3
from fastapi import APIRouter, Request, BackgroundTasks
from starlette.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from auth_service import AuthRepository, AuthError, AuthSettings, COOKIE_NAME
from auth_api import csrf_check, safe_error
from password_reset_service import PasswordResetService, ACCEPTED_MESSAGE

router=APIRouter(prefix="/api/auth/password-reset")


async def bounded_payload(request):
    raw=bytearray()
    async for chunk in request.stream():
        if len(raw)+len(chunk)>8192: raise AuthError("再設定の入力内容を確認してください。",422)
        raw.extend(chunk)
    try:
        payload=json.loads(raw)
        if not isinstance(payload,dict): raise ValueError()
        return payload
    except (ValueError,TypeError): raise AuthError("再設定の入力内容を確認してください。",422) from None


@router.post("/request")
async def reset_request(request: Request, background: BackgroundTasks):
    try:
        csrf_check(request); payload=await bounded_payload(request)
        if not isinstance(payload.get("email"),str): raise AuthError("メールアドレスを確認してください。",422)
        service=getattr(request.app.state,"password_reset_service",None)
        if service is None: raise AuthError("再設定メールはまだ利用できません。",503)
        normalized=await run_in_threadpool(service.admit_request,payload["email"],request.client.host if request.client else "unknown")
        background.add_task(service.deliver,normalized)
        return JSONResponse({"ok":True,"message":ACCEPTED_MESSAGE},status_code=202,headers={"Cache-Control":"no-store"})
    except (AuthError,sqlite3.Error,OSError) as exc: return safe_error(exc)


@router.post("/complete")
async def reset_complete(request: Request):
    try:
        csrf_check(request); payload=await bounded_payload(request)
        if not isinstance(payload.get("token"),str) or not isinstance(payload.get("password"),str):
            raise AuthError("再設定の入力内容を確認してください。",422)
        service=PasswordResetService(AuthRepository())
        result=await run_in_threadpool(service.complete,payload["token"],payload["password"],request.client.host if request.client else "unknown")
        response=JSONResponse(result,headers={"Cache-Control":"no-store"})
        response.delete_cookie(COOKIE_NAME,path="/",secure=AuthSettings.load().production,httponly=True,samesite="lax")
        return response
    except (AuthError,sqlite3.Error,OSError) as exc: return safe_error(exc)
