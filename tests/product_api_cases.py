"""Real ASGI permission regressions; no live SMTP or real users."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parent))
import asyncio
from copy import deepcopy
from datetime import datetime,timezone
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from auth_cases import api_request
from tier_b import api_app
from auth_service import AuthRepository
from operations_repository import OperationsRepository
from execution_repository import ExecutionRepository
from history_service import HistoryService
from fortune_service import calculate_fortune
from report_export_cases import FORM
from mail_delivery import MemoryMailTransport
from password_reset_service import PasswordResetService

PASSWORD="synthetic-password-1234"

class ProductAPICases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.result=calculate_fortune(FORM)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/"test.db"
        self.env=patch.dict(os.environ,{"FORTUNE_ENV":"production","FORTUNE_HISTORY_DB_PATH":str(self.path),"FORTUNE_PUBLIC_ORIGIN":"https://app.example.test","FORTUNE_LOGIN_ACCOUNT_LIMIT":"100","FORTUNE_LOGIN_IP_LIMIT":"1000"});self.env.start()
        self.ops=OperationsRepository(self.path);self.auth=self.ops.auth;self.ledger=ExecutionRepository(self.ops)
        self.ids={};self.cookies={}
        for who in ("admin","teacher","student","other","b2c"):
            self.ids[who]=self.auth.create_user(who+"@example.test",PASSWORD)["id"]
            self.cookies[who]=self.auth.login(who+"@example.test",PASSWORD)[1]
        self.ops.bootstrap(self.ids["admin"])
        self.org=self.ops.create_organization(self.ids["admin"],"教室一","one")["id"]
        self.second=self.ops.create_organization(self.ids["admin"],"教室二","two")["id"]
        self.ops.assign(self.ids["admin"],self.org,self.ids["teacher"],"teacher")
        self.ops.assign(self.ids["admin"],self.org,self.ids["student"],"student",True,2000)
        self.ops.assign(self.ids["admin"],self.second,self.ids["other"],"teacher")
        self.history=HistoryService(self.ops.product.history)
        self.reading=self.history.create(self.ids["student"],{"input_snapshot":{"form":FORM},"result_snapshot":deepcopy(self.result),"memo":"PRIVATE-CONTENT"})
        self.app=api_app();self.app_patch=patch("auth_cases.api_app",return_value=self.app);self.app_patch.start()
    def tearDown(self):self.app_patch.stop();self.env.stop();self.temp.cleanup()
    def call(self,method,path,body=None,who="student",headers=None,**options):
        return asyncio.run(api_request(method,path,body,cookie=self.cookies.get(who),headers=headers,**options))
    def data(self,*args,**kwargs):
        status,headers,body=self.call(*args,**kwargs);self.assertEqual(status,200,body);self.assertEqual(headers[b"cache-control"],b"no-store");return json.loads(body)["data"]
    def fortune(self,who="student",org=None,key=None,payload=None):
        return self.call("POST",f"/api/b2b/organizations/{org or self.org}/fortune",payload or FORM,who,headers={"Idempotency-Key":key or str(uuid4())})
    def test_teacher_all_operator_routes_forbidden(self):
        owner=self.ids["student"]
        for method,path,body in [("GET","/api/operations/users",None),("GET",f"/api/operations/users/{owner}",None),
            ("GET","/api/operations/organizations",None),("GET",f"/api/operations/organizations/{self.org}",None),
            ("GET","/api/operations/audit",None),("POST","/api/operations/users",{"organization_id":self.org,"email":"new@example.test","display_name":"新規","initial_payment_confirmed":True}),
            ("POST",f"/api/operations/users/{owner}/suspend",{}),("POST",f"/api/operations/users/{owner}/resume",{}),
            ("POST",f"/api/operations/users/{owner}/membership",{"organization_id":self.org,"role":"teacher"})]:
            self.assertEqual(self.call(method,path,body,"teacher")[0],403,(method,path))
    def test_teacher_response_exact_whitelist(self):
        self.fortune(who="teacher");self.fortune()
        data=self.data("GET",f"/api/b2b/organizations/{self.org}/teacher",who="teacher")
        self.assertEqual(set(data),{"organization_id","display_name","students","executions_this_month","executions_total","month_timezone"})
        self.assertEqual(data["executions_total"],2)
        self.assertEqual(set(data["students"][0]),{"display_name","account_state"})
        for prohibited in ("last_login","last_execution","email",self.ids["student"],"PRIVATE-CONTENT","password_hash"):
            self.assertNotIn(prohibited,json.dumps(data))
    def test_teacher_cannot_get_student_counts_via_queries_or_urls(self):
        self.fortune()
        own=self.data("GET",f"/api/account/summary?user_id={self.ids['student']}",who="teacher")
        self.assertEqual(own["executions_total"],0)
        self.assertEqual(self.call("GET",f"/api/b2b/organizations/{self.org}/users/{self.ids['student']}/usage",who="teacher")[0],404)
    def test_other_org_spoof_headers_and_body_denied(self):
        status,_,_=self.call("POST",f"/api/b2b/organizations/{self.second}/fortune",{**FORM,"organization_id":self.org,"user_id":self.ids["other"]},headers={"Idempotency-Key":str(uuid4()),"X-Organization-Id":self.org,"X-User-Id":self.ids["other"]})
        self.assertEqual(status,404)
        self.assertEqual(self.call("GET",f"/api/b2b/organizations/{self.second}/teacher",who="teacher")[0],404)
    def test_student_cannot_teacher(self):self.assertEqual(self.call("GET",f"/api/b2b/organizations/{self.org}/teacher")[0],403)
    def test_b2c_no_membership_existing_result_and_snapshot_preserved(self):
        old=self.ops.product.history.detail(self.ids["student"],self.reading["id"])
        status,_,body=self.call("POST","/api/fortune",FORM,"b2c",headers={"Idempotency-Key":str(uuid4())})
        self.assertEqual(status,200);result=json.loads(body);result.pop("excel_export_token",None);self.assertEqual(result,self.result)
        self.assertEqual(self.ops.product.history.detail(self.ids["student"],self.reading["id"]),old)
        self.assertEqual(self.data("GET","/api/account/summary",who="b2c")["memberships"],[])
    def test_anonymous_b2c_still_works_b2b_denied(self):
        self.assertEqual(self.call("POST","/api/fortune",FORM,who=None,origin=None)[0],200)
        self.assertEqual(self.fortune(who=None)[0],401)
    def test_suspended_user_fortune_blocked_and_no_count(self):
        self.ops.transition(self.ids["admin"],self.ids["student"],"suspend")
        self.assertEqual(self.fortune()[0],401)
        self.assertEqual(self.call("POST","/api/fortune",FORM)[0],401)
        self.assertEqual(self.ledger.personal(self.ids["student"])["executions_total"],0)
    def test_success_unsaved_and_duplicate_auto_retry_count_once(self):
        key=str(uuid4());self.assertEqual(self.fortune(key=key)[0],200);self.assertEqual(self.fortune(key=key)[0],200)
        value=self.data("GET","/api/account/summary")
        self.assertEqual(value["executions_total"],1);self.assertEqual(value["saved_histories_total"],1)
        self.assertEqual(self.fortune(key=key,payload={**FORM,"readingDate":"2027-01-01"})[0],409)
        self.assertEqual(self.fortune(payload={**FORM,"readingDate":"2027-01-01"})[0],200)
        self.assertEqual(self.data("GET","/api/account/summary")["executions_total"],2)
    def test_failure_does_not_count(self):
        self.assertEqual(self.fortune(payload={**FORM,"birthDate":"1800-01-01"})[0],422)
        self.assertEqual(self.data("GET","/api/account/summary")["executions_total"],0)
    def test_views_memo_history_and_recovery_do_not_count(self):
        self.data("GET",f"/api/history/{self.reading['id']}")
        self.data("PATCH",f"/api/history/{self.reading['id']}/memo",{"memo":"changed","updated_at":self.reading["updated_at"]})
        self.data("DELETE",f"/api/history/{self.reading['id']}")
        self.data("POST",f"/api/history/{self.reading['id']}/restore",{})
        self.assertEqual(self.data("GET","/api/account/summary")["executions_total"],0)
    def test_teacher_contract_end_does_not_stop_student(self):
        c=self.data("POST",f"/api/operations/organizations/{self.org}/teacher-contract",{"state":"terminated"},"admin")
        self.assertEqual(c["state"],"terminated");self.assertEqual(self.fortune()[0],200)
    def test_admin_projections_content_free_with_user_metrics(self):
        self.fortune();self.data("GET","/api/operations/organizations",who="admin")
        value=self.data("GET",f"/api/operations/users/{self.ids['student']}",who="admin")
        self.assertEqual(value["executions_total"],1);self.assertIsNotNone(value["last_execution_at"])
        self.assertIsNotNone(value["last_login_at"])
        for name in ("input_snapshot","result_snapshot","birthDate","PRIVATE-CONTENT","password_hash"):self.assertNotIn(name,json.dumps(value))
    def test_admin_does_not_get_other_users_history(self):
        self.assertEqual(self.call("GET",f"/api/history/{self.reading['id']}",who="admin")[0],404)
        self.assertEqual(self.call("GET",f"/api/history/{self.reading['id']}",who="teacher")[0],404)
    def test_creation_disabled_mail_safe_pending_without_secret(self):
        data=self.data("POST","/api/operations/users",{"organization_id":self.org,"email":"new@example.test","display_name":"新規","initial_payment_confirmed":True,"monthly_fee":2000},"admin")
        self.assertEqual(data["mail_status"],"disabled");self.assertTrue(data["setup_pending"])
        self.assertNotIn("password",str(data));self.assertNotIn("token",str(data))
    def test_initial_setup_mock_mail_then_login(self):
        mail=MemoryMailTransport();self.app.state.password_reset_service=PasswordResetService(self.auth,mail,"https://app.example.test")
        data=self.data("POST","/api/operations/users",{"organization_id":self.org,"email":"new@example.test","display_name":"新規","initial_payment_confirmed":True},"admin")
        self.assertEqual(data["mail_status"],"queued");self.assertEqual(len(mail.messages),1)
        token=mail.messages[0].body.split("#token=")[1].split()[0]
        status,_,body=self.call("POST","/api/auth/password-reset/complete",{"token":token,"password":PASSWORD},who=None)
        self.assertEqual(status,200);self.assertEqual(self.auth.login("new@example.test",PASSWORD)[0]["id"],data["id"])
    def test_unpaid_resume_rejected_then_settlement_allowed(self):
        owner=self.ids["student"]
        due=self.data("POST",f"/api/operations/users/{owner}/dues",{"organization_id":self.org,"due_date":"2026-08-01","amount":2000},"admin")
        self.data("POST",f"/api/operations/users/{owner}/suspend",{},"admin")
        self.assertEqual(self.call("POST",f"/api/operations/users/{owner}/resume",{},"admin")[0],409)
        self.data("POST",f"/api/operations/users/{owner}/dues/{due['id']}/settle",{},"admin")
        self.data("POST",f"/api/operations/users/{owner}/resume",{},"admin")
        entries=self.data("GET","/api/operations/audit",who="admin")
        self.assertTrue(any(row["action"]=="account-resume" for row in entries))
    def test_write_csrf_and_json_required(self):
        self.assertEqual(self.call("POST","/api/operations/organizations",{"display_name":"x","slug":"x"},"admin",origin="https://evil.test")[0],403)
        self.assertEqual(self.call("POST","/api/operations/organizations",{},"admin",raw=b'bad json')[0],422)
    def test_key_required_for_b2b_and_body_limit(self):
        self.assertEqual(self.call("POST",f"/api/b2b/organizations/{self.org}/fortune",FORM)[0],422)
        self.assertEqual(self.call("POST",f"/api/b2b/organizations/{self.org}/fortune",{"name":"x"*70000},headers={"Idempotency-Key":str(uuid4())})[0],422)
    def test_org_scoped_save_atomic_and_spoof_rejected(self):
        payload={"organization_id":self.org,"input_snapshot":{"form":FORM},"result_snapshot":deepcopy(self.result),"link":{"mode":"new_person"}}
        value=self.data("POST","/api/history",payload)
        self.assertEqual(self.ops.product.scoped_readings(self.org,self.ids["student"])[0]["id"],value["id"])
        before=self.ledger.personal(self.ids["student"])["saved_histories_total"]
        self.assertEqual(self.call("POST","/api/history",{**payload,"organization_id":self.second})[0],404)
        self.assertEqual(self.ledger.personal(self.ids["student"])["saved_histories_total"],before)
    def test_specific_datetime_b2c_preserved_b2b_pending(self):
        payload={**FORM,"specificDatetimeEnabled":True,"specificDatetimeCandidates":[{"date":"2026-10-08","time":"10:00"}]}
        status,_,body=self.call("POST","/api/fortune",payload,"b2c",headers={"Idempotency-Key":str(uuid4())})
        self.assertEqual(status,200);self.assertEqual(len(json.loads(body)["specific_datetime"]["rows"]),1)
        self.assertEqual(self.fortune(payload=payload)[0],422)
        self.assertEqual(self.ledger.personal(self.ids["student"])["executions_total"],0)
    def test_saved_org_preserved_on_detail_and_rerun(self):
        payload={"organization_id":self.org,"input_snapshot":{"form":FORM},"result_snapshot":deepcopy(self.result),"link":{"mode":"new_person"}}
        value=self.data("POST","/api/history",payload)
        detail=self.data("GET",f"/api/history/{value['id']}")
        self.assertEqual(detail["organization_id"],self.org)
        draft=self.data("POST",f"/api/history/{value['id']}/rerun",{"mode":"new_group"})
        self.assertEqual(draft["organizationId"],self.org)
        self.assertEqual(self.ledger.personal(self.ids["student"])["executions_total"],0)
    def test_cross_org_source_save_rejected_without_partial_data(self):
        self.ops.assign(self.ids["admin"],self.second,self.ids["student"],"student",True)
        source=self.history.create(self.ids["student"],{"input_snapshot":{"form":FORM},"result_snapshot":deepcopy(self.result),"link":{"mode":"new_person"}},organization_id=self.org)
        draft=self.history.prepare(self.ids["student"],source["id"],"new_group")
        before=self.ledger.personal(self.ids["student"])["saved_histories_total"]
        status,_,_=self.call("POST","/api/history",{"organization_id":self.second,"input_snapshot":{"form":draft["form"]},"result_snapshot":deepcopy(self.result),"link":draft["link"]})
        self.assertEqual(status,404);self.assertEqual(self.ledger.personal(self.ids["student"])["saved_histories_total"],before)
    def test_membership_payment_gate_and_host_not_authoritative(self):
        self.ops.assign(self.ids["admin"],self.second,self.ids["student"],"student",False)
        self.assertEqual(self.fortune(org=self.second)[0],403)
        self.assertEqual(self.call("GET",f"/api/b2b/organizations/{self.second}/me",headers={"X-Forwarded-Host":"one.hakase-uranai.jp"})[0],403)

if __name__=="__main__":unittest.main(verbosity=2)
