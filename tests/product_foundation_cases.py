"""Product models, organization/user double scope and theme persistence, temporary DB only."""
import sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); sys.path.insert(0,str(Path(__file__).resolve().parent))
import tempfile
import unittest
import sqlite3
from copy import deepcopy
from auth_service import AuthRepository
from history_service import HistoryService
from product_repository import ProductRepository
from history_repository import HistoryError, SQLiteHistoryRepository
from history_cases import FORM
from fortune_service import calculate_fortune
from account_lifecycle import AccountLifecycleRepository

class FoundationCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.result=calculate_fortune(FORM)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.path=Path(self.temp.name)/"test.db"
        self.auth=AuthRepository(self.path)
        self.a=self.auth.create_user("a@example.test","synthetic-password-1234")["id"]
        self.b=self.auth.create_user("b@example.test","synthetic-password-1234")["id"]
        self.legacy=SQLiteHistoryRepository(self.path)
        self.reading=HistoryService(self.legacy).create(self.a,{"input_snapshot":{"form":FORM},"result_snapshot":deepcopy(self.result),"memo":"PRIVATE-CONTENT"})
        self.repo=ProductRepository(self.path)
        self.org=self.repo.create_organization("Teacher One","teacher-one")["id"]
        self.second=self.repo.create_organization("Teacher Two","teacher-two")["id"]
        self.repo.add_membership(self.org,self.a,"teacher"); self.repo.add_membership(self.org,self.b,"student")
        self.repo.add_membership(self.second,self.a,"student")
    def tearDown(self): self.temp.cleanup()
    def test_legacy_snapshot_and_user_id_preserved_and_unassigned(self):
        self.assertEqual(self.legacy.detail(self.a,self.reading["id"]),self.reading)
        self.assertEqual(self.repo.scoped_readings(self.org,self.a),[])
        with self.repo.auth.connection() as db:
            self.assertEqual(db.execute("SELECT id FROM users WHERE email='a@example.test'").fetchone()[0],self.a)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(),[])
    def test_repeated_migration_is_idempotent(self):
        ProductRepository(self.path)
        with self.auth.connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM schema_migrations WHERE migration_key IN ('auth-lifecycle-001','product-foundation-001')").fetchone()[0],2)
            self.assertEqual(db.execute("SELECT count(*) FROM organizations").fetchone()[0],2)
    def test_one_user_multiple_org_roles(self):
        self.assertEqual(self.repo.resolve_context(self.org,self.a).role,"teacher")
        self.assertEqual(self.repo.resolve_context(self.second,self.a).role,"student")
    def test_no_membership_no_context(self):
        with self.assertRaises(HistoryError): self.repo.resolve_context(self.second,self.b)
    def test_same_org_other_user_never_sees_history(self):
        self.repo.bind_reading(self.org,self.a,self.reading["id"])
        self.assertEqual(self.repo.scoped_readings(self.org,self.b),[])
        with self.assertRaises(HistoryError): self.repo.scoped_detail(self.org,self.b,self.reading["id"])
        with self.assertRaises(HistoryError): self.repo.bind_reading(self.org,self.b,self.reading["id"])
    def test_same_user_other_org_isolated_and_reassignment_rejected(self):
        self.repo.bind_reading(self.org,self.a,self.reading["id"])
        self.assertEqual(self.repo.scoped_readings(self.second,self.a),[])
        with self.assertRaises(HistoryError): self.repo.scoped_detail(self.second,self.a,self.reading["id"])
        with self.assertRaises(HistoryError): self.repo.bind_reading(self.second,self.a,self.reading["id"])
    def test_duplicate_bind_is_idempotent(self):
        self.repo.bind_reading(self.org,self.a,self.reading["id"]); self.repo.bind_reading(self.org,self.a,self.reading["id"])
        self.assertEqual(len(self.repo.scoped_readings(self.org,self.a)),1)
    def test_suspended_membership_cannot_resolve_context(self):
        AccountLifecycleRepository(self.path).suspend(self.a)
        with self.assertRaises(HistoryError): self.repo.resolve_context(self.org,self.a)
    def test_soft_deleted_reading_cannot_be_bound_or_read(self):
        self.repo.bind_reading(self.org,self.a,self.reading["id"]); self.legacy.soft_delete(self.a,self.reading["id"])
        with self.assertRaises(HistoryError): self.repo.scoped_detail(self.org,self.a,self.reading["id"])
        self.assertEqual(self.repo.scoped_readings(self.org,self.a),[])
    def test_theme_persists_per_membership(self):
        self.repo.add_theme(self.org,"alternate","Alternate",{"background":"black","foreground":"white"})
        self.repo.select_theme(self.org,self.a,"alternate")
        reopened=ProductRepository(self.path)
        self.assertEqual(reopened.branding(self.org,self.a)["selected_theme_key"],"alternate")
        self.assertEqual(reopened.branding(self.org,self.b)["selected_theme_key"],"default")
        self.assertEqual(reopened.branding(self.second,self.a)["selected_theme_key"],"default")
    def test_theme_from_other_org_rejected(self):
        self.repo.add_theme(self.second,"private-theme","Only second",{})
        with self.assertRaises(HistoryError): self.repo.select_theme(self.org,self.a,"private-theme")
    def test_default_only_white_black_and_brand_labels(self):
        brand=self.repo.branding(self.org,self.a)
        self.assertEqual(brand["themes"][0]["definition"],{"background":"white","foreground":"black"})
        self.assertEqual(brand["service_name"],"占い師向け鑑定支援システム")
        self.assertNotIn("PRIVATE-CONTENT",str(brand))
    def test_contract_states_do_not_delete_org_or_users(self):
        contract=self.repo.create_contract(self.org,"active","2026-01-01",None,"future-plan")
        for state in ["suspended","terminated"]: self.repo.set_contract_state(self.org,contract,state)
        self.assertEqual(self.repo.resolve_context(self.org,self.a).user_id,self.a)
        self.assertEqual(self.legacy.detail(self.a,self.reading["id"]),self.reading)
    def test_contract_other_org_and_invalid_dates_rejected(self):
        contract=self.repo.create_contract(self.org,"active")
        with self.assertRaises(HistoryError): self.repo.set_contract_state(self.second,contract,"terminated")
        for args in [("invalid",None,None),("active","2026-02-30",None),("active","2026-02-01","2026-01-01")]:
            with self.assertRaises(HistoryError): self.repo.create_contract(self.org,*args)
    def test_fk_duplicate_membership_and_slug_constraints(self):
        with self.assertRaises(HistoryError): self.repo.add_membership(self.org,self.a,"student")
        with self.assertRaises(HistoryError): self.repo.create_organization("Duplicate","teacher-one")
        with self.repo.auth.connection() as db:
            with self.assertRaises(sqlite3.IntegrityError): db.execute("INSERT INTO reading_organization_scopes VALUES ('missing',?,?)",(self.org,self.a))
    def test_key_injection_invalid(self):
        with self.assertRaises(HistoryError): self.repo.create_organization("Name","../bad")
        with self.assertRaises(HistoryError): self.repo.add_membership(self.org,self.a,"admin;DROP TABLE users")

if __name__=="__main__": unittest.main(verbosity=2)
