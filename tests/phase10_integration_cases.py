"""Connected Phase 10 A-F flows; temporary synthetic DBs, deletion in memory only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import json
import unittest
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from uuid import uuid4
from xml.etree import ElementTree as ET
import product_api_cases as api
import billing_retention_cases as billing
import final_retention_cases as retention
from history_repository import HistoryError
from service_contract_repository import content_visible
from fortune_service import calculate_fortune
from mail_delivery import MemoryMailTransport
from password_reset_service import PasswordResetService
from report_export_cases import FORM,unpack
from report_pdf_cases import RecordingConverter
from k01_k03_cases import private_keys,BASELINE


class ConnectedAPICases(unittest.TestCase):
    setUp=api.ProductAPICases.setUp
    tearDown=api.ProductAPICases.tearDown
    call=api.ProductAPICases.call
    data=api.ProductAPICases.data
    fortune=api.ProductAPICases.fortune
    @classmethod
    def setUpClass(cls):cls.result=calculate_fortune(FORM)

    def saved(self,result,form,who="student",link=None):
        return self.data("POST","/api/history",{"organization_id":self.org,
            "input_snapshot":{"form":form},"result_snapshot":deepcopy(result),
            "memo":"合成連携メモ","link":link or {"mode":"new_person"}},who=who)

    def export(self,row,who="student"):
        status,_,body=self.call("POST","/api/export/excel",{"reading_id":row["id"]},who)
        self.assertEqual(status,200);parts=unpack(body)
        adapter=RecordingConverter()
        with patch("report_pdf.get_pdf_converter",return_value=adapter):
            status,_,pdf=self.call("POST","/api/export/pdf",{"reading_id":row["id"]},who)
        self.assertEqual(status,200);self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertEqual(unpack(adapter.inputs[0]),parts)
        self.assertEqual(self.call("POST","/api/export/excel",{"reading_id":row["id"]},"teacher")[0],404)
        return "\n".join(n.text or "" for name,data in parts.items() if name.endswith(".xml") for n in ET.fromstring(data).iter() if n.tag.split("}")[-1]=="t")

    def test_A_issue_setup_login_count_save_get_rerun_export(self):
        mail=MemoryMailTransport()
        self.mail_patch=patch.object(self.app.state,"password_reset_service",PasswordResetService(self.auth,mail,"https://app.example.test"),create=True)
        self.mail_patch.start();self.addCleanup(self.mail_patch.stop)
        issued=self.data("POST","/api/operations/users",{"organization_id":self.org,
            "email":"connected@example.test","display_name":"合成新規生徒","initial_payment_confirmed":True},"admin")
        self.assertTrue(issued["setup_pending"]);self.assertEqual(len(mail.messages),1)
        token=mail.messages[0].body.split("#token=")[1].split()[0]
        self.assertEqual(self.call("POST","/api/auth/password-reset/complete",{"token":token,"password":api.PASSWORD},who=None)[0],200)
        self.assertEqual(self.call("POST","/api/auth/login",{"email":"connected@example.test","password":api.PASSWORD},who=None)[0],200)
        self.ids["new"],self.cookies["new"]=issued["id"],self.auth.login("connected@example.test",api.PASSWORD)[1]
        key=str(uuid4())
        status,_,body=self.fortune(who="new",key=key)
        self.assertEqual(status,200,body);result=json.loads(body);self.assertEqual(private_keys(result),0)
        self.assertEqual(self.data("GET","/api/account/summary",who="new")["executions_total"],1)
        # Replay is not another successful execution.
        self.assertEqual(self.fortune(who="new",key=key)[0],200)
        self.assertEqual(self.data("GET","/api/account/summary",who="new")["executions_total"],1)
        row=self.saved(result,FORM,"new")
        detail=self.data("GET",f"/api/history/{row['id']}",who="new")
        self.assertEqual(detail["result_snapshot"],row["result_snapshot"])
        self.export(row,"new")
        draft=self.data("POST",f"/api/history/{row['id']}/rerun",{"mode":"existing_group"},who="new")
        self.assertEqual(draft["organizationId"],self.org)
        status,_,body=self.fortune(who="new",payload=draft["form"],key=str(uuid4()))
        self.assertEqual(status,200)
        second=self.saved(json.loads(body),draft["form"],"new",draft["link"])
        self.assertNotEqual(second["id"],row["id"]);self.assertEqual(second["group_id"],row["group_id"])
        self.assertEqual(self.data("GET","/api/account/summary",who="new")["executions_total"],2)
        self.assertEqual(self.data("GET",f"/api/history/{row['id']}",who="new")["result_snapshot"],detail["result_snapshot"])
        self.export(second,"new")

    def test_F_2026_original_2027_unregistered_save_get_reports(self):
        for year in (2026,2027):
            form={**FORM,"readingDate":f"{year}-09-30"}
            expected=calculate_fortune(form)
            status,_,body=self.fortune(payload=form);self.assertEqual(status,200)
            result=json.loads(body);result.pop("excel_export_token",None)
            self.assertEqual(result,expected);self.assertEqual(private_keys(result),0)
            annual=result["yearly_overall"]
            if year==2026:
                self.assertEqual({k:annual[k] for k in ("theme","comment")},BASELINE["year2026"][annual["tsuhensei"]])
            else:
                self.assertEqual(annual["comment"],"");self.assertEqual(annual["interpretation_status"],"unregistered")
            row=self.saved(result,form)
            detail=self.data("GET",f"/api/history/{row['id']}")
            self.assertEqual(private_keys(detail["result_snapshot"]),0)
            self.assertEqual(detail["result_snapshot"],result)
            text=self.export(row)
            self.assertIn(annual["comment"] if year==2026 else annual["interpretation_message"],text)
            if year==2027:
                for prose in BASELINE["year2026"].values():self.assertNotIn(prose["comment"],text)


class ConnectedRetentionCases(unittest.TestCase):
    setUp=billing.BillingRetentionCases.setUp
    tearDown=billing.BillingRetentionCases.tearDown
    activate=billing.BillingRetentionCases.activate
    cancel=billing.BillingRetentionCases.cancel
    save=billing.BillingRetentionCases.save
    memory=billing.BillingRetentionCases.memory
    cancel_all=retention.FinalRetentionCases.cancel_all
    proof=retention.FinalRetentionCases.proof
    def fresh_recontract(self,org=None,now=None):
        return self.ops.retention.recontract(self.admin,"P-001",org or self.org,"owner@example.test","synthetic",identity_verified=True,monthly_payment_confirmed=True,paid_through="2027-01-31",now=now or retention.DUE)

    def test_B_activation_due_grace_pause_settle_recontract_resume(self):
        self.proof();self.activate();row=self.save(self.org)
        self.assertEqual(self.services.summary(self.org,self.owner,billing.NOW)["first_billing_date"],"2026-11-01")
        nov=datetime(2026,11,1,tzinfo=billing.JST);jan=datetime(2027,1,1,tzinfo=billing.JST)
        with patch("operations_repository.utc",side_effect=lambda value=None:(value or nov).astimezone(timezone.utc)), patch("operations_repository.timestamp",return_value=nov.astimezone(timezone.utc).isoformat()):
            due=self.ops.record_due(self.admin,self.org,self.owner,"2026-11-01",2000)["id"]
        self.assertFalse(self.services.arrears(self.admin,self.org,self.owner,jan-timedelta(microseconds=1))["suspension_due"])
        self.assertTrue(self.services.arrears(self.admin,self.org,self.owner,jan)["suspension_due"])
        self.services.suspend(self.admin,self.org,self.owner,jan)
        with self.assertRaises(HistoryError):self.fresh_recontract(now=jan)
        self.ops.settle_due(self.admin,self.owner,due)
        resumed=self.fresh_recontract(now=jan)
        self.assertFalse(resumed["initial_fee_required"])
        self.assertEqual(self.services.summary(self.org,self.owner,jan)["state"],"active")
        with self.auth.connection() as db:self.assertTrue(content_visible(db,self.owner,row["id"],jan))

    def test_C_cancel_end_recover_deadline_recontract_cancels_deletion(self):
        self.proof();row=self.save(self.org);value=self.cancel()
        end=retention.END;deadline=value["deletion_due_at"]
        self.assertEqual(self.services.summary(self.org,self.owner,end)["state"],"terminated")
        recovered=self.services.recover(self.owner,self.org,end+timedelta(days=1))
        self.assertEqual(recovered["deletion_due_at"],deadline)
        with self.auth.connection() as db:
            self.assertTrue(content_visible(db,self.owner,row["id"],retention.DUE-timedelta(microseconds=1)))
            self.assertFalse(content_visible(db,self.owner,row["id"],retention.DUE))
        self.fresh_recontract()
        self.assertIsNone(self.services.summary(self.org,self.owner,retention.DUE)["deletion_due_at"])
        with self.auth.connection() as db:self.assertTrue(content_visible(db,self.owner,row["id"],retention.DUE))

    def test_D_one_org_purge_keeps_user_other_org_b2c(self):
        a=self.save(self.org);b=self.save(self.other);c=self.save()
        self.cancel();self.ops.retention.confirm_b2c(self.admin,self.owner,"active")
        plan=self.ops.retention.user_plan(self.admin,self.owner,retention.DUE)
        self.assertFalse(plan["can_delete"]);self.assertIn("b2c_active_or_unknown",plan["blockers"])
        db=self.memory()
        try:
            self.services.purge_memory_fixture(self.admin,self.org,self.owner,db,retention.DUE)
            self.assertEqual({r[0] for r in db.execute("SELECT id FROM readings")},{b["id"],c["id"]})
            self.assertIsNotNone(db.execute("SELECT id FROM users WHERE id=?",(self.owner,)).fetchone())
            self.assertTrue(content_visible(db,self.owner,b["id"],retention.DUE))
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(),[])
        finally:db.close()

    def test_E_delete_memory_match_proof_same_product_new_identity(self):
        self.proof();self.save(self.org);self.save(self.other);self.cancel_all()
        self.ops.retention.confirm_b2c(self.admin,self.owner,"inactive");db=self.memory()
        @contextmanager
        def change(actor):
            with db:
                db.execute("BEGIN IMMEDIATE");self.ops.require_admin(db,actor);yield db
        try:
            self.ops.retention.purge_user_memory_fixture(self.admin,self.owner,db,retention.DUE)
            self.assertIsNone(db.execute("SELECT id FROM users WHERE id=?",(self.owner,)).fetchone())
            self.assertEqual(db.execute("SELECT count(*) FROM purchase_proofs").fetchone()[0],1)
            with patch.object(self.ops,"change",change):
                with self.assertRaises(HistoryError):self.fresh_recontract(org=self.other)
                result=self.fresh_recontract()
            self.assertNotEqual(result["id"],self.owner);self.assertFalse(result["initial_fee_required"])
            self.assertTrue(result["setup_pending"]);self.assertFalse(result["deleted_history_restorable"])
            self.assertEqual(db.execute("SELECT count(*) FROM readings").fetchone()[0],0)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(),[])
        finally:db.close()

if __name__=="__main__":unittest.main(verbosity=2)
