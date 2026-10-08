"""W calculation endpoint; existing fortune interpretation is delegated unchanged."""
import json
import logging
import sqlite3
from uuid import uuid4
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from fortune_service import calculate_fortune
from auth_service import COOKIE_NAME,AuthError,database_path
from auth_api import current_user,request_owner,session_scope,safe_error
from history_repository import HistoryError
from report_export_service import export_tokens
from product_api import identity,repositories
from execution_repository import execution_key


async def calculation(request,org=None):
    try:
        # Existing anonymous B2C remains available without DB. Cookie-bearing calls must be valid.
        user=await run_in_threadpool(identity if org else current_user,request,**({} if org else {"optional":True}))
        operations=ledger=None
        if user and not user.get("development"):
            operations,ledger=await run_in_threadpool(repositories)
        if org:
            await run_in_threadpool(operations.context,org,user["id"])
        raw=bytearray()
        async for chunk in request.stream():
            if len(raw)+len(chunk)>65536:raise HistoryError("鑑定入力を確認してください。",422)
            raw.extend(chunk)
        payload=json.loads(raw) if raw else {}
        if not isinstance(payload,dict):raise HistoryError("鑑定入力を確認してください。",422)
        supplied=request.headers.get("idempotency-key")
        if org and supplied is None:raise HistoryError("鑑定実行IDを指定してください。",422)
        key=execution_key(supplied) if supplied is not None else str(uuid4())
        result=await run_in_threadpool(calculate_fortune,payload)
        if result.get("ok"):
            if ledger:
                await run_in_threadpool(ledger.record_success,user["id"],org,key,payload)
            if payload.get("includeGogyoVariants"):
                owner=user["id"] if user else None
                if owner:result={**result,"excel_export_token":export_tokens.issue(owner,payload,result,session_scope(request))}
        return JSONResponse(result,status_code=200 if result.get("ok") else 422,headers={"Cache-Control":"no-store"})
    except HistoryError as exc:
        # Preserve the W error shape, including auth errors, without echoing personal input.
        return JSONResponse({"ok":False,"errors":[str(exc)]},status_code=exc.status,headers={"Cache-Control":"no-store"})
    except (sqlite3.Error,OSError):return safe_error(AuthError("保存先を利用できません。",503))
    except (ValueError,TypeError):return JSONResponse({"ok":False,"errors":["鑑定入力を確認してください。"]},status_code=422)
    except Exception:
        logging.getLogger(__name__).error("Calculation request failed")
        return JSONResponse({"ok":False,"errors":["鑑定処理に失敗しました。"]},status_code=500)
