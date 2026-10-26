"""JST billing, scoped cancellation and memory-only purge. Synthetic fixture DBs."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import sqlite3
import tempfile
import unittest
from datetime import datetime,date,timedelta,timezone
from copy import deepcopy
from unittest.mock import patch
from operations_repository import OperationsRepository
from history_repository import HistoryError
from history_service import HistoryService
from execution_repository import ExecutionRepository
from service_contract_repository import terms,content_visible,effective_state
from billing_policy import JST,first_billing_date,billing_preview,paid_access_end,suspension_retention,arrears_preview

PASSWORD='synthetic-password-1234'
NOW=datetime(2026,10,20,10,tzinfo=JST)


class BillingPolicyCases(unittest.TestCase):
    def test_first_billing_calendar_boundaries(self):
        for value,expected in [('2026-10-01','2026-11-01'),('2026-10-31','2026-11-01'),
            ('2026-02-28','2026-03-01'),('2028-02-29','2028-03-01'),('2026-12-31','2027-01-01')]:
            with self.subTest(value=value):
                self.assertEqual(first_billing_date(datetime.fromisoformat(value).replace(tzinfo=JST)).isoformat(),expected)
    def test_activation_uses_jst_not_utc_month(self):
        self.assertEqual(first_billing_date(datetime(2026,10,31,15,tzinfo=timezone.utc)),date(2026,12,1))
    def test_no_initial_month_charge_or_unknown_legacy_date(self):
        self.assertEqual(billing_preview(NOW,'active',NOW),date(2026,11,1))
        self.assertIsNone(billing_preview(None,'active',NOW))
    def test_month_anchor_and_no_historical_invoice(self):
        self.assertEqual(billing_preview(NOW,'active',datetime(2026,11,1,tzinfo=JST)),date(2026,11,1))
        self.assertEqual(billing_preview(NOW,'active',datetime(2026,11,1,0,0,1,tzinfo=JST)),date(2026,12,1))
    def test_suspension_never_charges(self):
        for state in ['suspended','terminated','deletion_pending','deleted']:
            self.assertIsNone(billing_preview(NOW,state,NOW))
    def test_resume_no_missed_suspension_invoice(self):
        self.assertEqual(billing_preview(NOW,'active',datetime(2027,3,20,tzinfo=JST),resumed_at=datetime(2027,3,20,tzinfo=JST)),date(2027,4,1))
    def test_cancellation_stops_next_anchor(self):
        self.assertIsNone(billing_preview(NOW,'active',NOW,access_ends_at=paid_access_end(date(2026,10,31))))
    def test_november_unpaid_january_boundary(self):
        due=datetime(2026,11,1,tzinfo=JST)
        for instant,expected in [(datetime(2026,12,31,23,59,59,tzinfo=JST),False),(datetime(2027,1,1,tzinfo=JST),True)]:
            self.assertEqual(arrears_preview(due,due,instant)['suspension_due'],expected)
    def test_retention_jst_leap_anniversary(self):
        start=datetime(2028,2,29,tzinfo=JST);pending,delete=suspension_retention(start)
        self.assertEqual(pending,datetime(2029,2,28,tzinfo=JST));self.assertEqual(delete,pending+timedelta(days=30))
    def test_paid_period_end_is_exclusive_jst_midnight(self):
        self.assertEqual(paid_access_end(date(2026,12,31)),datetime(2027,1,1,tzinfo=JST))


class BillingRetentionCases(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'test.db'
        self.ops=OperationsRepository(self.path);self.auth=self.ops.auth;self.services=self.ops.services
        self.admin=self.auth.create_user('admin@example.test',PASSWORD)['id']
        self.owner=self.auth.create_user('owner@example.test',PASSWORD)['id']
        self.teacher=self.auth.create_user('teacher@example.test',PASSWORD)['id']
        self.ops.bootstrap(self.admin)
        self.org=self.ops.create_organization(self.admin,'one','one')['id'];self.other=self.ops.create_organization(self.admin,'two','two')['id']
        for org in (self.org,self.other):self.ops.assign(self.admin,org,self.owner,'student',True,2000)
        self.ops.assign(self.admin,self.org,self.teacher,'teacher')
        self.history=self.ops.product.history
    def tearDown(self):self.temp.cleanup()
    def activate(self):return self.services.activate(self.admin,self.org,self.owner,NOW)
    def cancel(self):
        self.activate();return self.services.cancel(self.owner,self.org,NOW)
    def save(self,org=None,link=None):
        payload={'input_snapshot':{'form':{'surname':'合成','givenName':'利用者','birthDate':'1988-08-12','readingDate':'2026-10-20'}},'result_snapshot':{'ok':True},'memo':'PRIVATE-CONTENT'}
        if link:payload['link']=link
        return self.history.create(self.owner,payload,('test','test',1),org)
    def memory(self):
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
        with self.auth.connection() as source:source.backup(db)
        db.execute('PRAGMA foreign_keys=ON');return db
    def test_migration_idempotent_legacy_no_backfill(self):
        OperationsRepository(self.path)
        value=self.services.summary(self.org,self.owner,NOW)
        self.assertIsNone(value['activated_at']);self.assertIsNone(value['next_billing_date'])
        with self.auth.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM service_contract_terms').fetchone()[0],0)
    def test_explicit_activation_and_initial_month_included(self):
        value=self.activate();self.assertEqual(value['first_billing_date'],'2026-11-01');self.assertEqual(value['paid_through'],'2026-10-31')
        self.assertEqual(self.services.activate(self.admin,self.org,self.owner,NOW+timedelta(days=2))['activated_at'],value['activated_at'])
    def test_pending_password_cannot_activate(self):
        owner=self.ops.issue_account(self.admin,self.org,'new@example.test','new',True)['id']
        with self.assertRaises(HistoryError):self.services.activate(self.admin,self.org,owner,NOW)
    def test_new_initial_setup_records_actual_activation_once(self):
        from password_reset_service import PasswordResetRepository
        from auth_service import normalized_email
        issued=self.ops.issue_account(self.admin,self.org,'new@example.test','new',True)
        self.ops.assign(self.admin,self.other,issued['id'],'student',True,activate_new=True)
        resets=PasswordResetRepository(self.auth)
        result=resets.issue(normalized_email(issued['email']),NOW.timestamp())
        resets.complete(result[1],PASSWORD,NOW.timestamp())
        value=self.services.summary(self.org,issued['id'],NOW)
        self.assertEqual(datetime.fromisoformat(value['activated_at']),NOW)
        self.assertEqual(value['first_billing_date'],'2026-11-01')
        self.assertEqual(self.services.summary(self.other,issued['id'],NOW)['activated_at'],value['activated_at'])
        result=resets.issue(normalized_email(issued['email']),(NOW+timedelta(days=2)).timestamp())
        resets.complete(result[1],PASSWORD,(NOW+timedelta(days=2)).timestamp())
        self.assertEqual(self.services.summary(self.org,issued['id'],NOW)['activated_at'],value['activated_at'])
    def test_legacy_password_reset_does_not_invent_activation(self):
        from password_reset_service import PasswordResetRepository
        resets=PasswordResetRepository(self.auth);result=resets.issue('owner@example.test',NOW.timestamp())
        resets.complete(result[1],PASSWORD,NOW.timestamp())
        self.assertIsNone(self.services.summary(self.org,self.owner,NOW)['activated_at'])
    def test_teacher_cannot_mutate_service(self):
        with self.assertRaises(HistoryError):self.services.activate(self.teacher,self.org,self.owner,NOW)
    def test_payment_requires_month_end_and_cannot_decrease(self):
        self.activate()
        with self.assertRaises(HistoryError):self.services.paid_period(self.admin,self.org,self.owner,'2026-11-20',NOW)
        value=self.services.paid_period(self.admin,self.org,self.owner,'2026-11-30',NOW)
        self.assertEqual(value['next_billing_date'],'2026-12-01')
        with self.assertRaises(HistoryError):self.services.paid_period(self.admin,self.org,self.owner,'2026-10-31',NOW)
    def test_unknown_paid_period_only_request_no_termination(self):
        value=self.services.cancel(self.owner,self.org,NOW)
        self.assertTrue(value['cancellation_needs_review']);self.assertIsNone(value['access_ends_at']);self.assertIsNone(value['deletion_due_at'])
    def test_cancel_access_paid_through_then_30_days(self):
        value=self.cancel();end=datetime(2026,11,1,tzinfo=JST)
        self.assertEqual(datetime.fromisoformat(value['access_ends_at']),end)
        self.assertEqual(datetime.fromisoformat(value['deletion_due_at']),end+timedelta(days=30))
        self.assertEqual(self.services.summary(self.org,self.owner,end-timedelta(microseconds=1))['state'],'active')
        self.assertEqual(self.services.summary(self.org,self.owner,end)['state'],'terminated')
    def test_cancel_minimum_term_needs_review(self):
        self.activate();self.services.suspend(self.admin,self.org,self.owner,NOW)
        self.services.resume(self.admin,self.org,self.owner,NOW+timedelta(days=1))
        with self.assertRaises(HistoryError):self.services.cancel(self.owner,self.org,NOW+timedelta(days=2))
    def test_suspend_scoped_keeps_other_org_b2c_session(self):
        token=self.auth.login('owner@example.test',PASSWORD)[1]
        self.activate();self.services.suspend(self.admin,self.org,self.owner,NOW)
        self.assertEqual(self.auth.authenticate(token)['id'],self.owner)
        self.ops.context(self.other,self.owner)
        with self.assertRaises(HistoryError):self.ops.context(self.org,self.owner)
        self.assertIsNone(self.services.summary(self.org,self.owner,NOW)['next_billing_date'])
    def test_repeat_suspend_keeps_original_anniversary(self):
        self.services.suspend(self.admin,self.org,self.owner,NOW)
        self.services.suspend(self.admin,self.org,self.owner,NOW+timedelta(days=100))
        self.assertEqual(datetime.fromisoformat(self.services.summary(self.org,self.owner,NOW)['suspended_at']),NOW)
    def test_resume_scoped_requires_full_settlement(self):
        due=self.ops.record_due(self.admin,self.org,self.owner,'2026-09-01',2000)['id']
        self.services.suspend(self.admin,self.org,self.owner,NOW)
        with self.assertRaises(HistoryError):self.services.resume(self.admin,self.org,self.owner,NOW)
        self.ops.settle_due(self.admin,self.owner,due)
        value=self.services.resume(self.admin,self.org,self.owner,NOW)
        self.assertEqual(value['state'],'active');self.assertEqual(datetime.fromisoformat(value['minimum_term_until']),datetime(2026,12,20,10,tzinfo=JST))
    def test_other_org_dues_do_not_block_scoped_resume(self):
        self.ops.record_due(self.admin,self.other,self.owner,'2026-09-01',2000)
        self.services.suspend(self.admin,self.org,self.owner,NOW)
        self.assertEqual(self.services.resume(self.admin,self.org,self.owner,NOW)['state'],'active')
    def test_no_new_dues_during_pause(self):
        self.services.suspend(self.admin,self.org,self.owner,NOW)
        with self.assertRaises(HistoryError):self.ops.record_due(self.admin,self.org,self.owner,'2026-10-01',2000)
    def test_resumed_contract_cannot_record_suspended_month_due(self):
        self.services.suspend(self.admin,self.org,self.owner,datetime(2026,7,20,tzinfo=JST))
        self.services.resume(self.admin,self.org,self.owner,datetime(2026,9,20,tzinfo=JST))
        with self.assertRaises(HistoryError):self.ops.record_due(self.admin,self.org,self.owner,'2026-08-01',2000)
    def test_settled_accounting_rows_preserved_by_memory_purge(self):
        due=self.ops.record_due(self.admin,self.org,self.owner,'2026-09-01',2000)['id']
        self.ops.settle_due(self.admin,self.owner,due);self.cancel();db=self.memory()
        try:
            self.services.purge_memory_fixture(self.admin,self.org,self.owner,db,datetime(2026,12,1,tzinfo=JST))
            self.assertIsNotNone(db.execute('SELECT settled_at FROM manual_dues WHERE id=?',(due,)).fetchone()[0])
        finally:db.close()
    def test_purge_shared_person_group_survivor_retained(self):
        a=self.save();b=self.save(self.org,{'mode':'existing_group','person_id':a['person_id'],'group_id':a['group_id'],'source_reading_id':a['id']})
        self.cancel();db=self.memory()
        try:
            self.services.purge_memory_fixture(self.admin,self.org,self.owner,db,datetime(2026,12,1,tzinfo=JST))
            self.assertEqual(db.execute('SELECT id FROM readings').fetchone()[0],a['id'])
            self.assertEqual(db.execute('SELECT id FROM persons').fetchone()[0],a['person_id'])
            self.assertEqual(db.execute('SELECT id FROM reading_groups').fetchone()[0],a['group_id'])
        finally:db.close()
    def test_initial_month_dues_rejected(self):
        self.activate()
        with self.assertRaises(HistoryError):self.ops.record_due(self.admin,self.org,self.owner,'2026-10-01',2000)
    def test_confirmed_paid_period_cannot_be_marked_unpaid(self):
        self.services.paid_period(self.admin,self.org,self.owner,'2026-09-30',NOW)
        with self.assertRaises(HistoryError):self.ops.record_due(self.admin,self.org,self.owner,'2026-09-01',2000)
    def test_future_due_cannot_be_marked_unpaid(self):
        with self.assertRaises(HistoryError):self.ops.record_due(self.admin,self.org,self.owner,'2099-01-01',2000)
    def test_unconfirmed_payment_never_unpaid(self):
        self.activate();self.assertFalse(self.services.arrears(self.admin,self.org,self.owner,NOW)['suspension_due'])
    def test_suspension_one_year_and_30_day_boundary(self):
        self.services.suspend(self.admin,self.org,self.owner,NOW)
        pending,delete=suspension_retention(NOW)
        self.assertEqual(self.services.summary(self.org,self.owner,pending-timedelta(microseconds=1))['state'],'suspended')
        self.assertEqual(self.services.summary(self.org,self.owner,pending)['state'],'deletion_pending')
        with self.assertRaises(HistoryError):self.services.resume(self.admin,self.org,self.owner,pending)
        self.assertFalse(self.services.deletion_plan(self.admin,self.org,self.owner,delete-timedelta(microseconds=1))['eligible'])
        self.assertTrue(self.services.deletion_plan(self.admin,self.org,self.owner,delete)['eligible'])
    def test_recovery_window_and_no_app_resume(self):
        self.cancel();end=datetime(2026,11,1,tzinfo=JST)
        with self.assertRaises(HistoryError):self.services.recover(self.owner,self.org,end-timedelta(microseconds=1))
        value=self.services.recover(self.owner,self.org,end+timedelta(days=30)-timedelta(microseconds=1))
        self.assertEqual(value['state'],'terminated');self.assertFalse(value['deletion_hold'])
        with self.assertRaises(HistoryError):self.services.recover(self.owner,self.org,end+timedelta(days=30))
        with self.assertRaises(HistoryError):self.services.resume(self.admin,self.org,self.owner,end+timedelta(days=2))
    def test_cancel_and_recovery_other_owner_org_denied(self):
        with self.assertRaises(HistoryError):self.services.cancel(self.teacher,self.org,NOW)
        with self.assertRaises(HistoryError):self.services.cancel(self.owner,'unknown',NOW)
    def test_history_hidden_after_end_other_org_b2c_intact(self):
        scoped=self.save(self.org);other=self.save(self.other);b2c=self.save();self.cancel()
        end=datetime(2026,11,1,tzinfo=JST)
        with patch('service_contract_repository.utc',side_effect=lambda v=None:(v or end).astimezone(timezone.utc)):
            self.assertEqual({r['id'] for r in self.history.list(self.owner)},{other['id'],b2c['id']})
            with self.assertRaises(HistoryError):self.history.detail(self.owner,scoped['id'])
        self.services.recover(self.owner,self.org,end+timedelta(days=1))
        with self.auth.connection() as db:self.assertTrue(content_visible(db,self.owner,scoped['id'],end))
    def test_memory_purge_preserves_other_org_b2c_accounting_user(self):
        a=self.save(self.org);b=self.save(self.other);c=self.save();self.cancel()
        db=self.memory()
        try:
            plan=self.services.purge_memory_fixture(self.admin,self.org,self.owner,db,datetime(2026,12,1,tzinfo=JST))
            self.assertEqual(plan['reading_ids'],[a['id']])
            self.assertEqual({r[0] for r in db.execute('SELECT id FROM readings')},{b['id'],c['id']})
            self.assertEqual(db.execute('SELECT count(*) FROM users WHERE id=?',(self.owner,)).fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM user_service_contracts').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT count(*) FROM memberships').fetchone()[0],3)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
        finally:db.close()
    def test_file_database_purge_always_rejected(self):
        self.cancel()
        with self.auth.connection() as db:
            with self.assertRaises(HistoryError):self.services.purge_memory_fixture(self.admin,self.org,self.owner,db,datetime(2026,12,1,tzinfo=JST))
    def test_external_source_dependency_blocks_purge(self):
        a=self.save(self.org)
        b=self.save(link={'mode':'existing_group','person_id':a['person_id'],'group_id':a['group_id'],'source_reading_id':a['id']})
        self.cancel();plan=self.services.deletion_plan(self.admin,self.org,self.owner,datetime(2026,12,1,tzinfo=JST))
        self.assertFalse(plan['can_delete']);self.assertEqual(plan['blocked_dependencies'][0]['dependent_id'],b['id'])
    def test_recovered_data_keeps_original_purge_deadline(self):
        self.cancel();self.services.recover(self.owner,self.org,datetime(2026,11,2,tzinfo=JST))
        self.assertTrue(self.services.deletion_plan(self.admin,self.org,self.owner,datetime(2026,12,1,tzinfo=JST))['eligible'])
    def test_teacher_contract_termination_has_no_student_effect(self):
        self.activate();self.ops.teacher_contract(self.admin,self.org,'terminated');self.ops.context(self.org,self.owner)
    def test_audit_and_admin_dry_run_has_no_content(self):
        self.activate();plan=self.services.deletion_plan(self.admin,self.org,self.owner,NOW)
        for value in (plan,self.ops.audit_list(self.admin)):
            self.assertNotIn('PRIVATE-CONTENT',str(value));self.assertNotIn('password_hash',str(value))
        with self.assertRaises(HistoryError):self.services.deletion_plan(self.teacher,self.org,self.owner,NOW)


if __name__=='__main__':unittest.main(verbosity=2)
