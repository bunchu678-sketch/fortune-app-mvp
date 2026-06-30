from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fortune_service import calculate_fortune  # noqa: E402


HOST = "127.0.0.1"
PORT = 8765


class FortuneApiHandler(BaseHTTPRequestHandler):
    server_version = "FortuneApi/0.1"

    def log_message(self, format, *args):
        return

    def _send_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:3000")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(200, {"ok": True})

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"ok": True, "service": "fortune-api"})
            return
        self._send_json(404, {"ok": False, "error": "Not found"})

    def do_POST(self):
        if self.path != "/api/fortune":
            self._send_json(404, {"ok": False, "error": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body) if raw_body else {}
            result = calculate_fortune(payload)
            status_code = 200 if result.get("ok") else 422
            self._send_json(status_code, result)
        except Exception as exc:
            self._send_json(500, {"ok": False, "errors": [str(exc)]})


def main():
    server = ThreadingHTTPServer((HOST, PORT), FortuneApiHandler)
    print(f"Fortune API listening on http://{HOST}:{PORT}")
    print("Health check: http://127.0.0.1:8765/health")
    server.serve_forever()


if __name__ == "__main__":
    main()
