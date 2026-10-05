"""Excel report endpoint. No arbitrary client-supplied comments or templates."""
import logging
import sqlite3
from urllib.parse import quote
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from history_repository import HistoryError
from history_service import development_owner, make_service
from report_data import ReportError
from report_export_service import export_reading

router=APIRouter(prefix="/api/export")


@router.post("/excel")
async def excel_report(request: Request):
    try:
        owner=development_owner()
        payload=await request.json()
        repository=make_service().repository if isinstance(payload,dict) and "reading_id" in payload else None
        filename,body=await run_in_threadpool(export_reading,owner,payload,repository)
        return Response(content=body,media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition":"attachment; filename=\"reading-report.xlsx\"; filename*=UTF-8''"+quote(filename,safe=""),
                                 "Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})
    except (HistoryError,ReportError) as exc:
        return JSONResponse(status_code=exc.status,content={"ok":False,"error":str(exc)})
    except (ValueError,TypeError,KeyError):
        return JSONResponse(status_code=422,content={"ok":False,"error":"鑑定書の入力形式が不正です。"})
    except (OSError,sqlite3.Error):
        logging.getLogger(__name__).exception("Excel report export failed")
        return JSONResponse(status_code=503,content={"ok":False,"error":"鑑定書の出力元を利用できません。"})
