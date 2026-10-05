"""PDF capability and trusted-proxy tests; no production DB or converter launch."""
import asyncio
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
import pdf_converter as pc
from proxy_settings import proxy_settings
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from tier_b import api_app


async def request(app, client="127.0.0.1", forwarded="198.51.100.21", path="/", extra=(), method="GET", payload=None):
    output = []
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
             "query_string": b"", "root_path": "", "server": ("localhost", 8765),
             "client": (client, 12345), "headers": [(b"host", b"localhost"),
             (b"x-forwarded-for", forwarded.encode()), (b"x-forwarded-proto", b"https"), *extra]}
    async def receive(): return {"type": "http.request", "body": json.dumps(payload or {}).encode(), "more_body": False}
    async def send(message): output.append(message)
    await app(scope, receive, send)
    return output


async def echo(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": json.dumps([scope["client"][0], scope["scheme"]]).encode()})


def ip(client="127.0.0.1", forwarded="198.51.100.21", extra=()):
    settings = proxy_settings()
    app = ProxyHeadersMiddleware(echo, trusted_hosts=settings["forwarded_allow_ips"]) if settings["proxy_headers"] else echo
    output = asyncio.run(request(app, client, forwarded, extra=extra))
    return json.loads(output[-1]["body"])


class ProxyCases(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"FORTUNE_PROXY_HEADERS": "0", "FORTUNE_TRUSTED_PROXY_IPS": "127.0.0.1,::1"})
        self.env.start(); self.addCleanup(self.env.stop)

    def test_default_disabled(self):
        with patch.dict(os.environ, {}, clear=True): self.assertFalse(proxy_settings()["proxy_headers"])

    def test_disabled_ignores_forwarded(self): self.assertEqual(ip(), ["127.0.0.1", "http"])

    def test_localhost_trusted(self):
        os.environ["FORTUNE_PROXY_HEADERS"] = "1"
        self.assertEqual(ip(), ["198.51.100.21", "https"])

    def test_ipv6_localhost_trusted(self):
        os.environ["FORTUNE_PROXY_HEADERS"] = "1"
        self.assertEqual(ip("::1"), ["198.51.100.21", "https"])

    def test_untrusted_peer_cannot_spoof(self):
        os.environ["FORTUNE_PROXY_HEADERS"] = "1"
        self.assertEqual(ip("203.0.113.9", "192.0.2.99"), ["203.0.113.9", "http"])

    def test_chain_uses_nearest_untrusted_not_spoofed_leftmost(self):
        os.environ["FORTUNE_PROXY_HEADERS"] = "1"
        self.assertEqual(ip(forwarded="192.0.2.99, 198.51.100.21"), ["198.51.100.21", "https"])

    def test_x_real_ip_does_not_override(self):
        os.environ["FORTUNE_PROXY_HEADERS"] = "1"
        self.assertEqual(ip(extra=((b"x-real-ip", b"192.0.2.99"),)), ["198.51.100.21", "https"])

    def test_explicit_ipv4_excludes_ipv6(self):
        os.environ.update(FORTUNE_PROXY_HEADERS="1", FORTUNE_TRUSTED_PROXY_IPS="127.0.0.1")
        self.assertEqual(ip("::1"), ["::1", "http"])

    def test_unsafe_trust_rejected_also_in_production(self):
        for value in ("*", "0.0.0.0/0", "127.0.0.0/8", "localhost", "198.51.100.21", "", "127.0.0.1,"):
            with self.subTest(value=value), patch.dict(os.environ, {"FORTUNE_ENV": "production", "FORTUNE_TRUSTED_PROXY_IPS": value}):
                with self.assertRaises(ValueError): proxy_settings()

    def test_invalid_toggle_rejected(self):
        os.environ["FORTUNE_PROXY_HEADERS"] = "true"
        with self.assertRaises(ValueError): proxy_settings()

    def test_uvicorn_environment_cannot_expand_trust_or_workers(self):
        from uvicorn import Config
        with patch.dict(os.environ, {"FORTUNE_PROXY_HEADERS": "1", "FORWARDED_ALLOW_IPS": "*", "WEB_CONCURRENCY": "8"}):
            config = Config(echo, workers=1, **proxy_settings())
            self.assertEqual(config.forwarded_allow_ips, "127.0.0.1,::1")
            self.assertEqual(config.workers, 1)

    def test_server_start_passes_explicit_settings_and_single_worker(self):
        os.environ["FORTUNE_PROXY_HEADERS"] = "1"
        api_app()
        import server
        with patch.object(server.uvicorn, "run") as run:
            server.main()
            self.assertTrue(run.call_args.kwargs["proxy_headers"])
            self.assertEqual(run.call_args.kwargs["forwarded_allow_ips"], "127.0.0.1,::1")
            self.assertEqual(run.call_args.kwargs["workers"], 1)

    def test_login_limiter_receives_uvicorn_resolved_ip(self):
        os.environ.update(FORTUNE_PROXY_HEADERS="1", FORTUNE_ENV="production", FORTUNE_PUBLIC_ORIGIN="https://app.example.test")
        app = api_app()
        import auth_api
        wrapped = ProxyHeadersMiddleware(app, trusted_hosts=proxy_settings()["forwarded_allow_ips"])
        for client, forwarded, expected in [("127.0.0.1", "198.51.100.21", "198.51.100.21"),
                                            ("203.0.113.9", "192.0.2.99", "203.0.113.9"),
                                            ("127.0.0.1", "192.0.2.99, 198.51.100.21", "198.51.100.21")]:
            with self.subTest(client=client), patch.object(auth_api, "AuthRepository") as repository:
                repository.return_value.login.return_value = ({"id": "test-user", "email": "test@example.test"}, "synthetic-session")
                output = asyncio.run(request(wrapped, client, forwarded, path="/api/auth/login", method="POST",
                    payload={"email": "test@example.test", "password": "synthetic-password"},
                    extra=((b"origin", b"https://app.example.test"), (b"content-type", b"application/json"))))
                self.assertEqual(output[0]["status"], 200)
                self.assertEqual(repository.return_value.login.call_args.kwargs["ip"], expected)


class CapabilityCases(unittest.TestCase):
    def test_disabled(self):
        with patch.dict(os.environ, {"FORTUNE_PDF_CONVERTER": "disabled"}): self.assertFalse(pc.pdf_available())

    def test_linux_even_with_windows_converter(self):
        with patch.dict(os.environ, {"FORTUNE_PDF_CONVERTER": "windows_excel"}), patch.object(pc.sys, "platform", "linux"):
            self.assertFalse(pc.pdf_available())

    def test_unknown_converter(self):
        with patch.dict(os.environ, {"FORTUNE_PDF_CONVERTER": "unknown"}): self.assertFalse(pc.pdf_available())

    def test_windows_prerequisites_present(self):
        with patch.dict(os.environ, {"FORTUNE_PDF_CONVERTER": "windows_excel"}), patch.object(pc.sys, "platform", "win32"), patch.object(Path, "is_file", return_value=True), patch.object(pc, "windows_excel_installed", return_value=True):
            self.assertTrue(pc.pdf_available())

    def test_windows_excel_missing(self):
        with patch.dict(os.environ, {"FORTUNE_PDF_CONVERTER": "windows_excel"}), patch.object(pc.sys, "platform", "win32"), patch.object(Path, "is_file", return_value=True), patch.object(pc, "windows_excel_installed", return_value=False):
            self.assertFalse(pc.pdf_available())

    def test_windows_adapter_files_missing(self):
        with patch.dict(os.environ, {"FORTUNE_PDF_CONVERTER": "windows_excel"}), patch.object(pc.sys, "platform", "win32"), patch.object(Path, "is_file", return_value=False):
            self.assertFalse(pc.pdf_available())

    def test_read_only_api_both_states_without_db_or_converter(self):
        api_app()
        import server
        for available in (True, False):
            with self.subTest(available=available), patch.object(server, "pdf_available", return_value=available), patch("auth_service.AuthRepository", side_effect=AssertionError("No DB access")), patch.object(pc.WindowsExcelPdfConverter, "convert", side_effect=AssertionError("No conversion")):
                output = asyncio.run(request(server.app, path="/api/export-capabilities"))
                self.assertEqual(output[0]["status"], 200)
                self.assertIn((b"cache-control", b"no-store"), output[0]["headers"])
                self.assertEqual(json.loads(output[-1]["body"]), {"ok": True, "data": {"pdf_available": available}})


if __name__ == "__main__": unittest.main(verbosity=2)
