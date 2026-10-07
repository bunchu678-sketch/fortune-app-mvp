"""Thirty-day recovery, ownership and source-FK safety using disposable histories only."""
import sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parent))
import asyncio
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import os
import tempfile
import unittest
from unittest.mock import patch
from auth_service import AuthRepository,AuthSettings
from history_repository import SQLiteHistoryRepository,HistoryError
from history_service import HistoryService
from history_cases import FORM
from auth_cases import api_request
from fortune_service import calculate_fortune
NOW=datetime(2026,10,1,12,tzinfo=timezone.utc)

class RecoveryCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.result=calculate_fortune(FORM)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/"test.db"
        self.auth=AuthRepository(self.path);self.a=self.auth.create_user("a@example.test","synthetic-password-1234")["id"]
        self.b=self.auth.create_user("b@example.test","synthetic-password-1234")["id"]
        self.repo=SQLiteHistoryRepository(self.path);self.service=HistoryService(self.repo)
        self.row=self.save();self.repo.soft_delete(self.a,self.row["id"]);self.deleted(NOW)
    def tearDown(self):self.temp.cleanup()
    def save(self,link=None):
        payload={"input_snapshot":{"form":FORM},"result_snapshot":deepcopy(self.result),"memo":"PRIVATE-MEMO","link":link or {"mode":"new_person"}}
        return self.service.create(self.a,payload)
    def deleted(self,when):
        with self.repo.connection() as db:db.execute("UPDATE readings SET deleted_at=? WHERE id=?",(when.isoformat(timespec="microseconds"),self.row["id"]))
    def test_deleted_immediately_hidden_but_recoverable(self):
        self.assertEqual(self.repo.list(self.a),[])
        with self.assertRaises(HistoryError):self.repo.detail(self.a,self.row["id"])
        self.assertEqual(self.repo.deleted_list(self.a,NOW)[0]["id"],self.row["id"])
    def test_restore_before_exact_deadline(self):
        self.repo.restore(self.a,self.row["id"],NOW+timedelta(days=30)-timedelta(microseconds=1))
        self.assertEqual(self.repo.list(self.a)[0]["id"],self.row["id"])
        self.assertEqual(self.repo.deleted_list(self.a,NOW+timedelta(days=30)),[])
    def test_at_deadline_no_recovery(self):
        due=NOW+timedelta(days=30)
        self.assertEqual(self.repo.deleted_list(self.a,due),[])
        with self.assertRaises(HistoryError):self.repo.restore(self.a,self.row["id"],due)
        self.assertEqual(self.repo.deletion_candidates(self.a,due),[{"id":self.row["id"],"has_dependents":False}])
    def test_restore_preserves_snapshots_memo_versions_and_identity(self):
        self.repo.restore(self.a,self.row["id"],NOW+timedelta(days=1))
        restored=self.repo.detail(self.a,self.row["id"])
        for key in self.row:
            if key not in ("updated_at","deleted_at"):self.assertEqual(restored[key],self.row[key])
        self.assertIsNone(restored["deleted_at"])
    def test_other_owner_cannot_list_restore_or_purge_candidate(self):
        self.assertEqual(self.repo.deleted_list(self.b,NOW),[])
        self.assertEqual(self.repo.deletion_candidates(self.b,NOW+timedelta(days=40)),[])
        with self.assertRaises(HistoryError):self.repo.restore(self.b,self.row["id"],NOW)
    def test_active_missing_or_already_restored_rejected(self):
        with self.assertRaises(HistoryError):self.repo.restore(self.a,"missing",NOW)
        self.repo.restore(self.a,self.row["id"],NOW)
        with self.assertRaises(HistoryError):self.repo.restore(self.a,self.row["id"],NOW)
    def test_clock_before_delete_rejected(self):
        self.assertEqual(self.repo.deleted_list(self.a,NOW-timedelta(seconds=1)),[])
        with self.assertRaises(HistoryError):self.repo.restore(self.a,self.row["id"],NOW-timedelta(seconds=1))
    def test_purge_candidates_are_read_only(self):
        with self.repo.connection() as db:before=[tuple(x) for x in db.execute("SELECT * FROM readings")]
        self.repo.deletion_candidates(self.a,NOW+timedelta(days=60))
        with self.repo.connection() as db:self.assertEqual(before,[tuple(x) for x in db.execute("SELECT * FROM readings")])
    def test_source_dependent_preserved_and_flagged(self):
        self.repo.restore(self.a,self.row["id"],NOW)
        child=self.save({"mode":"existing_group","person_id":self.row["person_id"],"group_id":self.row["group_id"],"source_reading_id":self.row["id"]})
        self.repo.soft_delete(self.a,self.row["id"]);self.deleted(NOW)
        self.assertTrue(self.repo.deletion_candidates(self.a,NOW+timedelta(days=30))[0]["has_dependents"])
        self.assertEqual(self.repo.detail(self.a,child["id"])["source_reading_id"],self.row["id"])
        with self.repo.connection() as db:self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(),[])
    def test_recovery_list_no_memo_or_result_content(self):
        items=self.repo.deleted_list(self.a,NOW)
        for secret in ["PRIVATE-MEMO","input_snapshot","result_snapshot","memo"]:self.assertNotIn(secret,str(items))
    def env(self):return patch.dict(os.environ,{"FORTUNE_ENV":"production","FORTUNE_PUBLIC_ORIGIN":"https://app.example.test","FORTUNE_HISTORY_DB_PATH":str(self.path)})
    def cookie(self,user):return self.auth.login(user,"synthetic-password-1234",AuthSettings(86400,900,100,1000,True,"https://app.example.test"))[1]
    def test_api_owner_restore_spoof_and_no_recalculation(self):
        self.deleted(datetime.now(timezone.utc)-timedelta(days=1))
        a=self.cookie("a@example.test");b=self.cookie("b@example.test")
        with self.env(),patch("fortune_service.calculate_fortune",side_effect=AssertionError("No recalculation")):
            self.assertEqual(asyncio.run(api_request("GET","/api/history/deleted",cookie=b))[0],200)
            self.assertEqual(asyncio.run(api_request("POST","/api/history/"+self.row["id"]+"/restore",{"owner_user_id":self.a},cookie=b))[0],404)
            self.assertEqual(asyncio.run(api_request("POST","/api/history/"+self.row["id"]+"/restore",{},cookie=a))[0],200)
            self.assertEqual(asyncio.run(api_request("GET","/api/history/"+self.row["id"],cookie=a))[0],200)
    def test_api_requires_session_and_csrf(self):
        self.deleted(datetime.now(timezone.utc)-timedelta(days=1))
        with self.env():
            self.assertEqual(asyncio.run(api_request("GET","/api/history/deleted"))[0],401)
            self.assertEqual(asyncio.run(api_request("POST","/api/history/"+self.row["id"]+"/restore",{},cookie=self.cookie("a@example.test"),origin="https://evil.test"))[0],403)

if __name__=="__main__":unittest.main(verbosity=2)
