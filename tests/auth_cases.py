"""Phase 7A contracts using disposable databases and synthetic users only."""
import asyncio
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from auth_service import AuthError, AuthRepository, AuthSettings, COOKIE_NAME, PASSWORD_HASHER, token_hash
from history_repository import SQLiteHistoryRepository
from history_service import HistoryService
from report_export_cases import FORM, unpack
from fortune_service import calculate_fortune
from tier_b import api_app


async def api_request(method, path, payload=None, cookie=None, origin="https://app.example.test",
                      headers=None, content_type="application/json", raw=None):
    output = []; sent = False
    data = raw if raw is not None else json.dumps(payload or {}).encode()
    async def receive():
        nonlocal sent
        if sent: return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": data, "more_body": False}
    async def send(message): output.append(message)
    values = [(b"host", b"app.example.test"), (b"content-type", content_type.encode())]
    if origin is not None: values.append((b"origin", origin.encode()))
    if cookie: values.append((b"cookie", f"{COOKIE_NAME}={cookie}".encode()))
    values.extend([(k.lower().encode(), v.encode()) for k,v in (headers or {}).items()])
    parsed = urlsplit(path)
    scope = {"type":"http", "asgi":{"version":"3.0", "spec_version":"2.3"},
             "http_version":"1.1", "method":method, "scheme":"https", "path":parsed.path,
             "raw_path":parsed.path.encode(), "query_string":parsed.query.encode(), "root_path":"",
             "headers":values, "server":("app.example.test",443), "client":("127.0.0.1",12345)}
    await api_app()(scope, receive, send)
    start = next(x for x in output if x["type"] == "http.response.start")
    body = b"".join(x.get("body", b"") for x in output if x["type"] == "http.response.body")
    return start["status"], dict(start["headers"]), body


class AuthCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = calculate_fortune(FORM)
        cls.password = secrets.token_urlsafe(24)
        cls.other_password = secrets.token_urlsafe(24)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "test.sqlite3"
        self.env = patch.dict(os.environ, {
            "FORTUNE_ENV":"production", "FORTUNE_HISTORY_DB_PATH":str(self.path),
            "FORTUNE_HISTORY_DEV_USER_ID":"must-not-be-used",
            "FORTUNE_PUBLIC_ORIGIN":"https://app.example.test",
            "FORTUNE_SESSION_TTL_HOURS":"24", "FORTUNE_LOGIN_ACCOUNT_LIMIT":"100",
            "FORTUNE_LOGIN_IP_LIMIT":"1000", "FORTUNE_LOGIN_WINDOW_SECONDS":"900",
        })
        self.env.start()
        self.repo = AuthRepository()
        self.a = self.repo.create_user("UserA@example.test", self.password)
        self.b = self.repo.create_user("userb@example.test", self.password)
        self.history = SQLiteHistoryRepository(self.path)
        self.service = HistoryService(self.history)
        self.reading = self.service.create(self.a["id"], {
            "input_snapshot":{"form":FORM}, "result_snapshot":deepcopy(self.result), "memo":"synthetic-private-memo",
        })

    def tearDown(self):
        self.env.stop(); self.temp.cleanup()

    def call(self, method, path, payload=None, **options):
        return asyncio.run(api_request(method, path, payload, **options))

    def login(self, who="a", **options):
        user = self.a if who == "a" else self.b
        status, headers, body = self.call("POST", "/api/auth/login", {"email":user["email"],"password":self.password}, **options)
        self.assertEqual(status, 200)
        return headers[b"set-cookie"].decode().split(";", 1)[0].split("=", 1)[1]

    def test_user_has_stable_internal_id(self):
        self.assertNotEqual(self.a["id"], self.a["email"])
        reopened = AuthRepository(self.path)
        self.assertEqual(reopened.change_user(self.a["email"], "enable")["id"], self.a["id"])

    def test_duplicate_email_and_normalization(self):
        with self.assertRaises(AuthError) as error:
            self.repo.create_user("  USERA@EXAMPLE.TEST  ", self.password)
        self.assertEqual(error.exception.status, 409)
        status, _, body = self.call("POST", "/api/auth/login", {"email":" USERA@EXAMPLE.TEST ","password":self.password})
        self.assertEqual(status, 200); self.assertEqual(json.loads(body)["data"]["user"]["id"], self.a["id"])

    def test_no_excessive_email_normalization(self):
        user = self.repo.create_user("User.A+tag@example.test", self.password)
        self.assertNotEqual(user["id"], self.a["id"])

    def test_password_hash_only_and_argon2id(self):
        with self.repo.connection() as db:
            row = db.execute("SELECT * FROM users WHERE id=?", (self.a["id"],)).fetchone()
            self.assertTrue(row["password_hash"].startswith("$argon2id$"))
            self.assertTrue(PASSWORD_HASHER.verify(row["password_hash"], self.password))
            self.assertNotIn(self.password, str(dict(row)))

    def test_password_length_and_email_validation(self):
        for email, password in [("invalid",self.password),("a@example.test","short"),("a@example.test","x"*1025)]:
            with self.assertRaises(AuthError): self.repo.create_user(email,password)

    def test_disable_and_enable(self):
        self.repo.change_user(self.a["email"], "disable")
        self.assertEqual(self.call("POST","/api/auth/login",{"email":self.a["email"],"password":self.password})[0],401)
        self.repo.change_user(self.a["email"], "enable")
        self.login()

    def test_password_change_revokes_sessions(self):
        cookie = self.login()
        self.repo.change_user(self.a["email"], "set-password", self.other_password)
        self.assertEqual(self.call("GET","/api/auth/me",cookie=cookie)[0],401)
        self.assertEqual(self.call("POST","/api/auth/login",{"email":self.a["email"],"password":self.password})[0],401)
        self.assertEqual(self.call("POST","/api/auth/login",{"email":self.a["email"],"password":self.other_password})[0],200)
        self.assertEqual(self.repo.change_user(self.a["email"],"enable")["id"],self.a["id"])

    def test_wrong_email_password_and_disabled_same_message(self):
        failures = []
        for email,password in [("missing@example.test",self.password),(self.a["email"],self.other_password)]:
            status, _, body = self.call("POST","/api/auth/login",{"email":email,"password":password})
            self.assertEqual(status,401); failures.append(json.loads(body)["error"])
        self.repo.change_user(self.a["email"],"disable")
        status,_,body = self.call("POST","/api/auth/login",{"email":self.a["email"],"password":self.password})
        self.assertEqual(status,401); self.assertEqual(failures,[json.loads(body)["error"]]*2)

    def test_cookie_security_and_no_secret_in_response(self):
        status, headers, body = self.call("POST","/api/auth/login",{"email":self.a["email"],"password":self.password})
        self.assertEqual(status,200)
        cookie = headers[b"set-cookie"].decode()
        for attribute in ("HttpOnly","Secure","SameSite=lax","Path=/","Max-Age=86400"):
            self.assertIn(attribute,cookie)
        self.assertEqual(headers[b"cache-control"],b"no-store")
        token = cookie.split(";",1)[0].split("=",1)[1]
        self.assertGreaterEqual(len(token),43)
        for secret in (token,self.password,"password_hash"):
            self.assertNotIn(secret,body.decode())
        with self.repo.connection() as db:
            row = db.execute("SELECT * FROM auth_sessions").fetchone()
            self.assertEqual(row["token_hash"],token_hash(token)); self.assertNotIn(token,str(dict(row)))

    def test_session_foreign_key(self):
        with self.repo.connection() as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO auth_sessions VALUES (?,?,?,?,NULL)",("missing", "not-a-user", "test",9999999999))

    def test_me_authenticated_and_minimal(self):
        status,_,body = self.call("GET","/api/auth/me",cookie=self.login())
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)["data"],{"authenticated":True,"user":self.a})

    def test_me_unauthenticated(self):
        self.assertEqual(self.call("GET","/api/auth/me")[0],401)
        self.assertEqual(self.call("GET","/api/auth/me",cookie="unknown-session-token-0123456789")[0],401)

    def test_session_expiry(self):
        cookie = self.login()
        with self.repo.connection() as db: db.execute("UPDATE auth_sessions SET expires_at=0")
        self.assertEqual(self.call("GET","/api/auth/me",cookie=cookie)[0],401)

    def test_configurable_ttl(self):
        with patch.dict(os.environ,{"FORTUNE_SESSION_TTL_HOURS":"2"}):
            _,headers,_ = self.call("POST","/api/auth/login",{"email":self.a["email"],"password":self.password})
            self.assertIn(b"Max-Age=7200",headers[b"set-cookie"])

    def test_invalid_ttl_fails_safely(self):
        with patch.dict(os.environ,{"FORTUNE_SESSION_TTL_HOURS":"-1"}):
            status,_,body = self.call("POST","/api/auth/login",{"email":self.a["email"],"password":self.password})
        self.assertEqual(status,503); self.assertNotIn(str(self.path).encode(),body)

    def test_logout_revokes_and_clears_cookie(self):
        cookie = self.login()
        status,headers,_ = self.call("POST","/api/auth/logout",{},cookie=cookie)
        self.assertEqual(status,200); self.assertIn(b"Max-Age=0",headers[b"set-cookie"])
        self.assertEqual(self.call("GET","/api/auth/me",cookie=cookie)[0],401)
        self.assertEqual(self.call("POST","/api/auth/logout",{})[0],200)

    def test_disabled_existing_session_and_enable_does_not_revive(self):
        cookie = self.login()
        self.repo.change_user(self.a["email"],"disable")
        self.assertEqual(self.call("GET","/api/auth/me",cookie=cookie)[0],401)
        self.repo.change_user(self.a["email"],"enable")
        self.assertEqual(self.call("GET","/api/auth/me",cookie=cookie)[0],401)

    def test_disabled_status_checked_each_request_even_without_revocation(self):
        cookie = self.login()
        with self.repo.connection() as db: db.execute("UPDATE users SET status='disabled' WHERE id=?",(self.a["id"],))
        self.assertEqual(self.call("GET","/api/auth/me",cookie=cookie)[0],401)

    def test_login_rotates_and_revokes_previous_session(self):
        old = self.login(); new = self.login(cookie=old)
        self.assertNotEqual(old,new); self.assertEqual(self.call("GET","/api/auth/me",cookie=old)[0],401)
        self.assertEqual(self.call("GET","/api/auth/me",cookie=new)[0],200)

    def test_production_never_development_fallback(self):
        for method,path,payload in [("GET","/api/history",None),("POST","/api/history",{}),
                                    ("POST","/api/export/excel",{}),("POST","/api/export/pdf",{})]:
            self.assertEqual(self.call(method,path,payload)[0],401)

    def test_anonymous_fortune_works_without_db_or_auth_settings(self):
        with patch.dict(os.environ,{"FORTUNE_HISTORY_DB_PATH":self.temp.name,"FORTUNE_PUBLIC_ORIGIN":""}):
            status,_,body = self.call("POST","/api/fortune",FORM,origin=None)
        self.assertEqual(status,200); self.assertTrue(json.loads(body)["ok"])
        self.assertNotIn("excel_export_token",json.loads(body))

    def test_spoof_body_query_and_headers_do_not_change_owner(self):
        cookie = self.login("b")
        payload = {"input_snapshot":{"form":FORM},"result_snapshot":self.result,"user_id":self.a["id"]}
        status,_,body = self.call("POST","/api/history?user_id="+self.a["id"],payload,cookie=cookie,
                                 headers={"X-User-Id":self.a["id"],"user_id":self.a["id"]})
        self.assertEqual(status,200); self.assertEqual(json.loads(body)["data"]["owner_user_id"],self.b["id"])
        self.assertEqual(self.call("GET","/api/history/"+self.reading["id"]+"?user_id="+self.a["id"],cookie=cookie,
                                   headers={"X-User-Id":self.a["id"]})[0],404)

    def test_b_list_excludes_a(self):
        status,headers,body = self.call("GET","/api/history",cookie=self.login("b"))
        self.assertEqual(status,200); self.assertEqual(json.loads(body)["data"],[])
        self.assertEqual(headers[b"cache-control"],b"no-store")

    def test_b_detail_memo_delete_rerun_are_rejected(self):
        cookie = self.login("b"); prefix = "/api/history/"+self.reading["id"]
        for method,path,payload in [("GET",prefix,None),("PATCH",prefix+"/memo",{"memo":"attack","updated_at":self.reading["updated_at"]}),
                                    ("DELETE",prefix,None),("POST",prefix+"/rerun",{"mode":"new_group"})]:
            self.assertEqual(self.call(method,path,payload,cookie=cookie)[0],404)
        self.assertEqual(self.history.detail(self.a["id"],self.reading["id"]),self.reading)

    def test_b_person_group_and_save_link_rejected(self):
        cookie = self.login("b")
        self.assertEqual(self.call("GET","/api/history/groups/"+self.reading["group_id"]+"/memos",cookie=cookie)[0],404)
        self.assertEqual(self.call("POST","/api/history/persons/"+self.reading["person_id"],{"form":FORM},cookie=cookie)[0],404)
        payload = {"input_snapshot":{"form":FORM},"result_snapshot":self.result,
                   "link":{"mode":"existing_group","person_id":self.reading["person_id"],"group_id":self.reading["group_id"]}}
        self.assertEqual(self.call("POST","/api/history",payload,cookie=cookie)[0],404)

    def test_b_saved_excel_and_pdf_rejected_before_conversion(self):
        cookie = self.login("b")
        with patch("pdf_converter.get_pdf_converter",side_effect=AssertionError("must not convert")):
            for fmt in ("excel","pdf"):
                self.assertEqual(self.call("POST","/api/export/"+fmt,{"reading_id":self.reading["id"]},cookie=cookie)[0],404)

    def test_unsaved_token_user_and_session_isolation(self):
        cookie = self.login()
        status,_,body = self.call("POST","/api/fortune",FORM,cookie=cookie)
        self.assertEqual(status,200); payload = {"export_token":json.loads(body)["excel_export_token"]}
        status,_,xlsx = self.call("POST","/api/export/excel",payload,cookie=cookie)
        self.assertEqual(status,200); unpack(xlsx)
        for other in (self.login("b"),self.login()):
            for fmt in ("excel","pdf"):
                self.assertEqual(self.call("POST","/api/export/"+fmt,payload,cookie=other)[0],404)
        self.call("POST","/api/auth/logout",{},cookie=cookie)
        self.assertEqual(self.call("POST","/api/export/excel",payload,cookie=cookie)[0],401)

    def test_saved_exports_use_snapshot_without_calculation(self):
        cookie = self.login()
        with patch("fortune_service.calculate_fortune",side_effect=AssertionError("no recalculation")):
            status,_,xlsx = self.call("POST","/api/export/excel",{"reading_id":self.reading["id"]},cookie=cookie)
        self.assertEqual(status,200); self.assertNotIn(b"synthetic-private-memo",b"".join(unpack(xlsx).values()))
        with patch("report_pdf.get_pdf_converter") as factory:
            factory.return_value.convert.return_value = b"%PDF-1.7\nsynthetic\n%%EOF"
            status,_,body = self.call("POST","/api/export/pdf",{"reading_id":self.reading["id"]},cookie=cookie)
            self.assertEqual(status,200); self.assertTrue(body.startswith(b"%PDF-"))
            self.assertEqual(unpack(factory.return_value.convert.call_args.args[0]),unpack(xlsx))

    def test_csrf_origin_missing_wrong_and_null(self):
        cookie = self.login()
        for origin in (None,"null","https://evil.example.test","https://app.example.test.evil.test","http://app.example.test"):
            self.assertEqual(self.call("POST","/api/auth/logout",{},cookie=cookie,origin=origin)[0],403)
        self.assertEqual(self.call("GET","/api/auth/me",cookie=cookie)[0],200)

    def test_login_csrf_rejected(self):
        self.assertEqual(self.call("POST","/api/auth/login",{"email":self.a["email"],"password":self.password},origin="https://evil.test")[0],403)

    def test_csrf_referer_same_origin_fallback(self):
        self.assertEqual(self.call("POST","/api/auth/logout",{},cookie=self.login(),origin=None,
                                   headers={"Referer":"https://app.example.test/history"})[0],200)

    def test_malformed_referer_is_controlled(self):
        self.assertEqual(self.call("POST","/api/auth/logout",{},cookie=self.login(),origin=None,
                                   headers={"Referer":"https://["})[0],403)

    def test_csrf_json_required_and_cross_site_fetch_rejected(self):
        cookie = self.login()
        for content_type in ("text/plain","application/x-www-form-urlencoded","multipart/form-data"):
            self.assertEqual(self.call("POST","/api/auth/logout",{},cookie=cookie,content_type=content_type)[0],415)
        self.assertEqual(self.call("POST","/api/auth/logout",{},cookie=cookie,headers={"Sec-Fetch-Site":"cross-site"})[0],403)

    def test_csrf_guards_history_export_and_authenticated_fortune(self):
        cookie = self.login()
        for path in ("/api/history","/api/export/excel","/api/export/pdf","/api/fortune"):
            self.assertEqual(self.call("POST",path,{},cookie=cookie,origin="https://evil.test")[0],403)

    def test_forwarded_headers_cannot_override_configured_origin(self):
        self.assertEqual(self.call("POST","/api/auth/logout",{},cookie=self.login(),origin="https://evil.test",
                                   headers={"X-Forwarded-Host":"evil.test","X-Forwarded-Proto":"https"})[0],403)

    def test_production_origin_required_and_must_be_https(self):
        for origin in ("","http://app.example.test","https://app.example.test/path"):
            with patch.dict(os.environ,{"FORTUNE_PUBLIC_ORIGIN":origin}):
                self.assertEqual(self.call("POST","/api/auth/login",{})[0],503)

    def test_persisted_login_rate_limit_and_window(self):
        with patch.dict(os.environ,{"FORTUNE_LOGIN_ACCOUNT_LIMIT":"2"}):
            for _ in range(2): self.assertEqual(self.call("POST","/api/auth/login",{"email":self.a["email"],"password":self.other_password})[0],401)
            status,headers,_ = self.call("POST","/api/auth/login",{"email":self.a["email"],"password":self.password})
            self.assertEqual(status,429); self.assertIn(b"retry-after",headers)
            AuthRepository(self.path)
            self.assertEqual(self.call("POST","/api/auth/login",{"email":self.a["email"],"password":self.password})[0],429)
            with self.repo.connection() as db: db.execute("UPDATE auth_login_attempts SET attempted_at=0")
            self.login()

    def test_ip_rate_limit_includes_unknown_accounts(self):
        with patch.dict(os.environ,{"FORTUNE_LOGIN_IP_LIMIT":"2"}):
            for index in range(3):
                expected = 401 if index < 2 else 429
                self.assertEqual(self.call("POST","/api/auth/login",{"email":f"unknown{index}@example.test","password":self.password})[0],expected)

    def test_malformed_login_is_safe(self):
        for raw in (b"{",b"[]",b"null",b"{\"email\":1,\"password\":true}",b"x"*8193):
            status,_,body = self.call("POST","/api/auth/login",raw=raw)
            self.assertEqual(status,422); self.assertNotIn(b"Traceback",body)

    def test_storage_failure_is_safe(self):
        with patch.dict(os.environ,{"FORTUNE_HISTORY_DB_PATH":self.temp.name}):
            status,_,body = self.call("POST","/api/auth/login",{"email":self.a["email"],"password":self.password})
        self.assertEqual(status,503)
        for value in (str(self.path),self.password,"Traceback","SQL"):
            self.assertNotIn(value.encode(),body)

    def test_additive_migration_preserves_legacy_snapshot(self):
        legacy = Path(self.temp.name)/"legacy.sqlite3"
        repository = SQLiteHistoryRepository(legacy)
        saved = HistoryService(repository).create("legacy-dev-owner",{"input_snapshot":{"form":FORM},"result_snapshot":self.result,"memo":"legacy"})
        with repository.connection() as db:
            before = {name:[tuple(r) for r in db.execute("SELECT * FROM "+name)] for name in ("persons","reading_groups","readings")}
        AuthRepository(legacy); AuthRepository(legacy)
        with repository.connection() as db:
            after = {name:[tuple(r) for r in db.execute("SELECT * FROM "+name)] for name in before}
        self.assertEqual(before,after); self.assertEqual(repository.detail("legacy-dev-owner",saved["id"]),saved)

    def test_cli_create_disable_enable_password_and_no_secret_output(self):
        import contextlib
        import io
        spec = importlib.util.spec_from_file_location("manage_test",ROOT/"scripts"/"manage_user.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        output = io.StringIO()
        for action in ("create","disable","enable","set-password"):
            with patch.object(sys,"argv",["manage_user.py",action,"--email","cli@example.test"]), patch.object(sys.stdin,"isatty",return_value=True), patch.object(module,"getpass",return_value=self.password), contextlib.redirect_stdout(output):
                self.assertEqual(module.main(),0)
        self.assertNotIn(self.password,output.getvalue()); self.assertNotIn("$argon2",output.getvalue())

    def test_cli_refuses_password_without_interactive_terminal(self):
        import contextlib
        import io
        spec = importlib.util.spec_from_file_location("manage_test",ROOT/"scripts"/"manage_user.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with patch.object(sys,"argv",["manage_user.py","create","--email","cli@example.test"]), patch.object(sys.stdin,"isatty",return_value=False), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(module.main(),1)

    def test_cli_refuses_echo_fallback(self):
        import contextlib
        import io
        from getpass import GetPassWarning
        spec = importlib.util.spec_from_file_location("manage_test",ROOT/"scripts"/"manage_user.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with patch.object(sys,"argv",["manage_user.py","create","--email","cli@example.test"]), patch.object(sys.stdin,"isatty",return_value=True), patch.object(module,"getpass",side_effect=GetPassWarning()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(module.main(),1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
