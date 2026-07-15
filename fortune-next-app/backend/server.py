from __future__ import annotations

import json
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

app = FastAPI()


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
        status_code = 200 if result.get("ok") else 422
        return JSONResponse(status_code=status_code, content=result)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "errors": [str(exc)]})


def main():
    uvicorn.run(app, host=HOST, port=PORT, reload=False, access_log=False)


if __name__ == "__main__":
    main()
