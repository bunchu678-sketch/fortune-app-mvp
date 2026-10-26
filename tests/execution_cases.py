"""Execution idempotency/PII minimization/isolation/JST, temporary synthetic data."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from uuid import uuid4
from operations_repository import OperationsRepository
from execution_repository import ExecutionRepository
from history_repository import HistoryError

class ExecutionCases(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();p=Path(self.temp.name)/"test.db"
        self.ops=OperationsRepository(p);self.auth=self.ops.auth
        self.admin=self.auth.create_user("admin@example.test","synthetic-password-1234")["id"];self.ops.bootstrap(self.admin)
        self.a=self.auth.create_user("a@example.test","synthetic-password-1234")["id"]
        self.b=self.auth.create_user("b@example.test","synthetic-password-1234")["id"]
        self.org=self.ops.create_organization(self.admin,"one","one")["id"]
        self.other=self.ops.create_organization(self.admin,"two","two")["id"]
        self.ops.assign(self.admin,self.org,self.a,"teacher");self.ops.assign(self.admin,self.org,self.b,"student",True)
        self.ops.assign(self.admin,self.other,self.a,"teacher")
        self.repo=ExecutionRepository(self.ops);self.payload={"birthDate":"1988-08-12","name":"PRIVATE-PERSON","consultation":"PRIVATE-CONTENT"}
    def tearDown(self): self.temp.cleanup()
    def record(self,owner=None,org=None,key=None,payload=None,now=None):
        return self.repo.record_success(owner or self.a,org,key or str(uuid4()),payload or self.payload,now)
    def test_unsaved_success_count_separate_from_saved(self):
        self.record(org=self.org)
        value=self.repo.personal(self.a)
        self.assertEqual((value["executions_total"],value["saved_histories_total"]),(1,0))
    def test_retries_count_once_and_payload_order_irrelevant(self):
        key=str(uuid4());self.assertTrue(self.record(org=self.org,key=key))
        self.assertFalse(self.record(org=self.org,key=key,payload=dict(reversed(list(self.payload.items())))))
        self.assertEqual(self.repo.personal(self.a)["executions_total"],1)
    def test_same_key_other_conditions_rejected(self):
        key=str(uuid4());self.record(org=self.org,key=key)
        with self.assertRaises(HistoryError):self.record(org=self.org,key=key,payload={"birthDate":"1989-01-01"})
    def test_new_conditions_and_new_execution_both_count(self):
        self.record(org=self.org);self.record(org=self.org,payload={"birthDate":"1989-01-01"})
        self.assertEqual(self.repo.organization_totals(self.org)["executions_total"],2)
    def test_concurrent_retries_only_once(self):
        key=str(uuid4())
        with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(lambda _:self.record(org=self.org,key=key),range(4)))
        self.assertEqual(results.count(True),1)
    def test_owner_keys_independent(self):
        key=str(uuid4());self.record(org=self.org,key=key);self.record(owner=self.b,org=self.org,key=key)
        self.assertEqual(self.repo.personal(self.a)["executions_total"],1);self.assertEqual(self.repo.personal(self.b)["executions_total"],1)
    def test_organization_totals_include_teacher_and_student(self):
        self.record(org=self.org);self.record(owner=self.b,org=self.org);self.record(org=self.other)
        self.assertEqual(self.repo.organization_totals(self.org)["executions_total"],2)
        self.assertEqual(self.repo.organization_totals(self.other)["executions_total"],1)
    def test_student_other_org_rejected(self):
        with self.assertRaises(HistoryError):self.record(owner=self.b,org=self.other)
    def test_b2c_independent_and_no_org_required(self):
        self.record();self.record(org=self.org)
        self.assertEqual(self.repo.personal(self.a)["executions_total"],2)
        self.assertEqual(self.repo.personal(self.a,self.org)["executions_total"],1)
    def test_teacher_projection_has_only_totals(self):
        self.record(org=self.org)
        self.assertEqual(set(self.repo.organization_totals(self.org)),{"executions_this_month","executions_total","month_timezone"})
    def test_no_plain_input_or_result_in_metrics(self):
        self.record(org=self.org)
        with self.auth.connection() as db:rows=[dict(r) for r in db.execute("SELECT * FROM successful_executions")]
        for value in ("PRIVATE-PERSON","PRIVATE-CONTENT","1988-08-12","result_snapshot","input_snapshot"):
            self.assertNotIn(value,str(rows))
    def test_jst_month_boundary_and_last_execution(self):
        before=datetime(2026,9,30,14,59,59,tzinfo=timezone.utc);after=datetime(2026,9,30,15,tzinfo=timezone.utc)
        self.record(org=self.org,now=before);self.record(org=self.org,now=after)
        value=self.repo.personal(self.a,now=datetime(2026,10,8,tzinfo=timezone.utc))
        self.assertEqual(value["executions_this_month"],1);self.assertTrue(value["last_execution_at"].startswith("2026-09-30T15:00"))
    def test_stopped_account_rejected_at_commit(self):
        self.ops.transition(self.admin,self.a,"suspend")
        with self.assertRaises(HistoryError):self.record()
        self.assertEqual(self.repo.personal(self.a)["executions_total"],0)
    def test_invalid_id_rejected(self):
        for key in ("bad","x"*1000,None,12):
            with self.assertRaises(HistoryError):self.repo.record_success(self.a,self.org,key,self.payload)
    def test_reading_metrics_does_not_increment(self):
        for _ in range(3):self.repo.personal(self.a);self.repo.organization_totals(self.org)
        self.assertEqual(self.repo.personal(self.a)["executions_total"],0)

if __name__=="__main__":unittest.main(verbosity=2)
