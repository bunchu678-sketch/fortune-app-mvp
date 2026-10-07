from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fortune_service import calculate_fortune  # noqa: E402


HOST = "127.0.0.1"
PORT = 8765

BACKEND_ROOT = str(Path(__file__).parent)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)
from history_api import router as history_router
from export_api import router as export_router
from history_repository import HistoryError
from auth_api import router as auth_router, AuthBoundary, request_owner, session_scope
from report_export_service import export_tokens
from pdf_converter import pdf_available
from proxy_settings import proxy_settings
from password_reset_api import router as password_reset_router

app = FastAPI()
app.add_middleware(AuthBoundary)
app.include_router(auth_router)
app.include_router(password_reset_router)
app.include_router(history_router)
app.include_router(export_router)


@app.get("/api/export-capabilities")
def export_capabilities():
    # Public capability only: no DB access, user data, converter launch, or migration.
    return JSONResponse({"ok": True, "data": {"pdf_available": pdf_available()}},
                        headers={"Cache-Control": "no-store"})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Not found"})
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/health")
async def health():
    return {"ok": True, "service": "fortune-api"}


@app.post("/api/fortune")
async def fortune(request: Request):
    try:
        raw_body = (await request.body()).decode("utf-8")
        payload = json.loads(raw_body) if raw_body else {}
        result = calculate_fortune(payload)
        if result.get("ok") and payload.get("includeGogyoVariants"):
            try:
                owner = request_owner(request)
            except (HistoryError, OSError, sqlite3.Error):
                owner = None
            if owner:
                result = {**result, "excel_export_token": export_tokens.issue(owner, payload, result, session_scope(request))}
        status_code = 200 if result.get("ok") else 422
        return JSONResponse(status_code=status_code, content=result)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "errors": [str(exc)]})


def main():
    uvicorn.run(app, host=HOST, port=PORT, reload=False, access_log=False, workers=1, **proxy_settings())


if __name__ == "__main__":
    main()
