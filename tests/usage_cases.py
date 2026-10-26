"""Derived usage is content-free, organization-scoped and based on JST save timestamps."""
import sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parent))
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from copy import deepcopy
from auth_service import AuthRepository,AuthSettings
from account_lifecycle import AccountLifecycleRepository,anniversary
from product_repository import ProductRepository
from usage_repository import UsageRepository,month_window
from history_service import HistoryService
from history_repository import HistoryError
from history_cases import FORM
from fortune_service import calculate_fortune

NOW=datetime(2026,10,15,tzinfo=timezone.utc)

class UsageCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.result=calculate_fortune(FORM)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/"test.db"
        self.auth=AuthRepository(self.path)
        self.a=self.auth.create_user("a@example.test","synthetic-password-1234")["id"]
        self.b=self.auth.create_user("b@example.test","synthetic-password-1234")["id"]
        self.product=ProductRepository(self.path)
        self.org=self.product.create_organization("First","first")["id"]
        self.second=self.product.create_organization("Second","second")["id"]
        for org,user in [(self.org,self.a),(self.org,self.b),(self.second,self.a)]: self.product.add_membership(org,user,"member")
        self.repo=UsageRepository(self.product)
    def tearDown(self): self.temp.cleanup()
    def save(self,user,org,when):
        reading=HistoryService(self.product.history).create(user,{"input_snapshot":{"form":FORM},"result_snapshot":deepcopy(self.result),"memo":"PRIVATE-SENTINEL","link":{"mode":"new_person"}})
        if org:self.product.bind_reading(org,user,reading["id"])
        with self.auth.connection() as db: db.execute("UPDATE readings SET saved_at=? WHERE id=?",(when.isoformat(timespec="microseconds"),reading["id"]))
        return reading["id"]
    def test_organization_user_counts_and_state(self):
        self.save(self.a,self.org,NOW);self.save(self.b,self.org,NOW)
        self.save(self.a,self.second,NOW);self.save(self.a,None,NOW)
        AccountLifecycleRepository(self.path).suspend(self.b,NOW)
        stats=self.repo.organization(self.org,NOW)
        self.assertEqual((stats["registered_users"],stats["active_users"],stats["suspended_users"]),(2,1,1))
        self.assertEqual(stats["saved_readings_total"],2);self.assertEqual(stats["saved_readings_this_month"],2)
        self.assertEqual(self.repo.user(self.org,self.a,NOW)["saved_readings_total"],1)
        self.assertEqual(self.repo.user(self.second,self.a,NOW)["saved_readings_total"],1)
    def test_jst_boundary_uses_saved_at_not_reading_date(self):
        start,end=month_window(NOW)
        boundary=datetime.fromisoformat(start)
        self.save(self.a,self.org,boundary-timedelta(microseconds=1));self.save(self.a,self.org,boundary)
        self.save(self.a,self.org,datetime.fromisoformat(end))
        stats=self.repo.user(self.org,self.a,NOW)
        self.assertEqual(stats["saved_readings_total"],3);self.assertEqual(stats["saved_readings_this_month"],1)
        self.assertEqual(start,"2026-09-30T15:00:00.000000+00:00")
    def test_soft_delete_does_not_rewrite_cumulative_saved_count(self):
        reading=self.save(self.a,self.org,NOW);self.product.history.soft_delete(self.a,reading)
        self.assertEqual(self.repo.organization(self.org,NOW)["saved_readings_total"],1)
        self.assertEqual(self.repo.organization(self.org,NOW)["count_basis"],"saved_history_including_soft_deleted")
    def test_no_private_content_or_password_in_stats(self):
        self.save(self.a,self.org,NOW)
        for value in [self.repo.organization(self.org,NOW),self.repo.user(self.org,self.a,NOW)]:
            for secret in ["PRIVATE-SENTINEL","password_hash","input_snapshot","result_snapshot","memo"]:self.assertNotIn(secret,str(value))
    def test_empty_org_and_no_login(self):
        self.assertIsNone(self.repo.user(self.org,self.a,NOW)["last_login_at"])
        self.assertIsNone(self.repo.organization(self.org,NOW)["last_saved_reading_at"])
        self.assertEqual(self.repo.organization(self.org,NOW)["saved_readings_total"],0)
    def test_last_login_single_value(self):
        settings=AuthSettings(86400,900,100,1000,False,"")
        self.auth.login("a@example.test","synthetic-password-1234",settings,clock=lambda:NOW.timestamp())
        self.assertEqual(self.repo.user(self.org,self.a,NOW)["last_login_at"],NOW.isoformat(timespec="microseconds"))
    def test_pending_state_and_legacy_disabled(self):
        lifecycle=AccountLifecycleRepository(self.path);lifecycle.suspend(self.a,NOW);lifecycle.advance_due(anniversary(NOW))
        with self.auth.connection() as db:db.execute("UPDATE users SET status='disabled' WHERE id=?",(self.b,))
        stats=self.repo.organization(self.org,NOW)
        self.assertEqual(stats["deletion_pending_users"],1);self.assertEqual(stats["suspended_users"],1)
    def test_other_org_user_and_sql_injection_rejected(self):
        with self.assertRaises(HistoryError):self.repo.user(self.second,self.b,NOW)
        with self.assertRaises(HistoryError):self.repo.organization("' OR 1=1 --",NOW)
    def test_month_rollover_and_timezone_validation(self):
        self.assertEqual(month_window(datetime(2026,12,15,tzinfo=timezone.utc))[1],"2026-12-31T15:00:00.000000+00:00")
        with self.assertRaises(ValueError):month_window(datetime(2026,12,15))

if __name__=="__main__":unittest.main(verbosity=2)
