"""Password reset security contracts. Synthetic users, memory mail and temporary DBs only."""
import sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); sys.path.insert(0,str(Path(__file__).resolve().parent))
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
from auth_service import AuthRepository,AuthSettings,AuthError,token_hash,PASSWORD_HASHER
from account_lifecycle import AccountLifecycleRepository
from mail_delivery import MemoryMailTransport
from password_reset_service import PasswordResetService,RESET_TTL_SECONDS,ACCEPTED_MESSAGE,INVALID_LINK_MESSAGE
from auth_cases import api_request
from tier_b import api_app

PASSWORD="synthetic-password-1234"; NEW="replacement-password-5678"
SETTINGS=AuthSettings(86400,900,100,1000,True,"https://app.example.test")

class ResetCases(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.path=Path(self.temp.name)/"test.db"
        self.auth=AuthRepository(self.path); self.user=self.auth.create_user("Known@example.test",PASSWORD)
        self.now=time.time(); self.mail=MemoryMailTransport()
        self.service=PasswordResetService(self.auth,self.mail,"https://app.example.test",SETTINGS,clock=lambda:self.now)
    def tearDown(self): self.temp.cleanup()
    def issue(self):
        self.service.request(self.user["email"])
        link=next(line for line in self.mail.messages[-1].body.splitlines() if line.startswith("https://"))
        return urlsplit(link).fragment.partition("token=")[2]
    def login(self,password=PASSWORD):
        return self.auth.login(self.user["email"],password,SETTINGS,clock=lambda:self.now)[1]
    def test_token_only_hash_persisted_and_no_public_token(self):
        token=self.issue()
        with self.auth.connection() as db:
            rows=[tuple(r) for r in db.execute("SELECT * FROM password_reset_tokens")]
            self.assertNotIn(token,str(rows)); self.assertEqual(rows[0][0],token_hash(token))
            self.assertEqual(rows[0][4]-self.now,1800)
        response=self.service.request("missing@example.test")
        self.assertEqual(response,{"ok":True,"message":ACCEPTED_MESSAGE}); self.assertNotIn(token,str(response))
    def test_present_absent_suspended_same_public_response(self):
        present=self.service.request(self.user["email"]); absent=self.service.request("missing@example.test")
        AccountLifecycleRepository(self.path).suspend(self.user["id"])
        suspended=self.service.request(self.user["email"])
        self.assertEqual(present,absent); self.assertEqual(present,suspended); self.assertEqual(len(self.mail.messages),1)
    def test_password_update_revokes_all_existing_sessions(self):
        first=self.login(); second=self.login(); token=self.issue()
        self.service.complete(token,NEW)
        for raw in [first,second]:
            with self.assertRaises(AuthError): self.auth.authenticate(raw,clock=lambda:self.now)
        with self.assertRaises(AuthError): self.login()
        self.login(NEW)
        with self.auth.connection() as db:
            encoded=db.execute("SELECT password_hash FROM users WHERE id=?",(self.user["id"],)).fetchone()[0]
            self.assertTrue(encoded.startswith("$argon2id$")); self.assertTrue(PASSWORD_HASHER.verify(encoded,NEW))
    def test_single_use(self):
        token=self.issue(); self.service.complete(token,NEW)
        with self.assertRaises(AuthError) as caught: self.service.complete(token,PASSWORD)
        self.assertEqual(str(caught.exception),INVALID_LINK_MESSAGE)
    def test_thirty_minutes_exact_expiry(self):
        token=self.issue(); self.now+=RESET_TTL_SECONDS
        with self.assertRaises(AuthError): self.service.complete(token,NEW)
        self.login()
    def test_before_expiry_accepted(self):
        token=self.issue(); self.now+=RESET_TTL_SECONDS-0.01; self.service.complete(token,NEW); self.login(NEW)
    def test_new_request_invalidates_previous(self):
        first=self.issue(); second=self.issue()
        with self.assertRaises(AuthError): self.service.complete(first,NEW)
        self.service.complete(second,NEW)
    def test_admin_password_change_invalidates_token(self):
        token=self.issue(); self.auth.change_user(self.user["email"],"set-password",NEW)
        with self.assertRaises(AuthError): self.service.complete(token,PASSWORD)
    def test_suspend_resume_does_not_revive_token(self):
        token=self.issue(); lifecycle=AccountLifecycleRepository(self.path); lifecycle.suspend(self.user["id"]); lifecycle.resume(self.user["id"])
        with self.assertRaises(AuthError): self.service.complete(token,NEW)
    def test_invalid_password_does_not_consume_token(self):
        token=self.issue()
        with self.assertRaises(AuthError): self.service.complete(token,"short")
        self.service.complete(token,NEW)
    def test_unknown_and_expired_link_have_same_message(self):
        token=self.issue(); self.now+=RESET_TTL_SECONDS
        messages=[]
        for value in [token,"x"*43]:
            with self.assertRaises(AuthError) as caught: self.service.complete(value,NEW)
            messages.append(str(caught.exception))
        self.assertEqual(messages[0],messages[1])
    def test_concurrent_consumption_has_one_winner(self):
        token=self.issue()
        def consume():
            try: self.service.complete(token,NEW); return True
            except AuthError: return False
        with ThreadPoolExecutor(max_workers=2) as workers: results=list(workers.map(lambda _:consume(),range(2)))
        self.assertEqual(sorted(results),[False,True]); self.login(NEW)
    def test_rate_limit_persisted_for_known_unknown_accounts(self):
        settings=AuthSettings(86400,900,2,100,True,"https://app.example.test")
        for email in [self.user["email"],"missing@example.test"]:
            service=PasswordResetService(self.auth,self.mail,"https://app.example.test",settings,clock=lambda:self.now)
            service.admit_request(email,"one"); service.admit_request(email,"two")
            service=PasswordResetService(AuthRepository(self.path),self.mail,"https://app.example.test",settings,clock=lambda:self.now)
            with self.assertRaises(AuthError) as caught: service.admit_request(email,"three")
            self.assertEqual(caught.exception.status,429)
    def test_ip_rate_limit_applies_to_distinct_missing_accounts(self):
        settings=AuthSettings(86400,900,100,2,True,"https://app.example.test")
        self.service.settings=settings
        for email in ["missing1@example.test","missing2@example.test"]: self.service.admit_request(email,"one")
        with self.assertRaises(AuthError): self.service.admit_request("missing3@example.test","one")
    def test_untrusted_origin_rejected_before_issuance(self):
        for origin in ["http://evil.test","https://evil.test/path","https://user:pass@host.test","https://[", "https://host.test#bad"]:
            self.service.public_origin=origin
            with self.assertRaises(AuthError): self.service.request(self.user["email"])
        self.assertEqual(self.mail.messages,[])
    def test_unconfigured_mail_is_uniform_unavailable(self):
        service=PasswordResetService(self.auth,settings=SETTINGS)
        for email in [self.user["email"],"missing@example.test"]:
            with self.assertRaises(AuthError) as caught: service.request(email)
            self.assertEqual(caught.exception.status,503)
    def test_delivery_error_does_not_leak_and_token_revoked(self):
        class Broken:
            def send(self,message): raise RuntimeError("SECRET-CREDENTIAL")
        self.service.mailer=Broken()
        with self.assertLogs("password_reset_service",level="ERROR") as logs: result=self.service.request(self.user["email"])
        self.assertTrue(result["ok"]); self.assertNotIn("SECRET-CREDENTIAL",str(logs.output))
        with self.auth.connection() as db: self.assertIsNotNone(db.execute("SELECT used_at FROM password_reset_tokens").fetchone()[0])
    def test_additive_restart_preserves_user(self):
        self.issue(); AuthRepository(self.path)
        self.assertEqual(self.auth.change_user(self.user["email"],"enable")["id"],self.user["id"])
        with self.auth.connection() as db: self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(),[])
    def api_environment(self):
        return patch.dict(os.environ,{"FORTUNE_ENV":"production","FORTUNE_PUBLIC_ORIGIN":"https://app.example.test","FORTUNE_HISTORY_DB_PATH":str(self.path),"FORTUNE_LOGIN_ACCOUNT_LIMIT":"100","FORTUNE_LOGIN_IP_LIMIT":"1000"})
    def test_api_disabled_known_unknown_same_503(self):
        with self.api_environment():
            results=[asyncio.run(api_request("POST","/api/auth/password-reset/request",{"email":email})) for email in [self.user["email"],"missing@example.test"]]
            self.assertEqual(results[0],results[1]); self.assertEqual(results[0][0],503)
    def test_api_generic_202_background_fake_delivery(self):
        with self.api_environment(),patch.object(api_app().state,"password_reset_service",self.service,create=True):
            results=[asyncio.run(api_request("POST","/api/auth/password-reset/request",{"email":email})) for email in [self.user["email"],"missing@example.test"]]
            self.assertEqual(results[0],results[1]); self.assertEqual(results[0][0],202)
            self.assertEqual(results[0][1][b"cache-control"],b"no-store"); self.assertEqual(len(self.mail.messages),1)
    def test_api_csrf_and_payload_limits(self):
        with self.api_environment():
            for path in ["request","complete"]:
                self.assertEqual(asyncio.run(api_request("POST","/api/auth/password-reset/"+path,{},origin="https://evil.test"))[0],403)
                self.assertEqual(asyncio.run(api_request("POST","/api/auth/password-reset/"+path,raw=b"x"*9000))[0],422)
                self.assertEqual(asyncio.run(api_request("POST","/api/auth/password-reset/"+path,raw=b"[]"))[0],422)
    def test_api_completion_cookie_clear_and_session_revocation(self):
        token=self.issue(); cookie=self.login()
        with self.api_environment():
            status,headers,body=asyncio.run(api_request("POST","/api/auth/password-reset/complete",{"token":token,"password":NEW},cookie=cookie))
            self.assertEqual(status,200); self.assertIn(b"Max-Age=0",headers[b"set-cookie"])
            self.assertNotIn(token,body.decode())
            self.assertEqual(asyncio.run(api_request("GET","/api/auth/me",cookie=cookie))[0],401)

if __name__=="__main__": unittest.main(verbosity=2)
