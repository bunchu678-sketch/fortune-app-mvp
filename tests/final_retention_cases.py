"""Synthetic isolated final retention, purchase proof and restore safety cases."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import unittest
import json
import sqlite3
from datetime import datetime,timedelta
from unittest.mock import patch
import billing_retention_cases as base
from billing_policy import JST,suspension_retention
from history_repository import HistoryError
from retention_repository import record_deletion
from service_contract_repository import content_visible

NOW=base.NOW
END=datetime(2026,11,1,tzinfo=JST)
DUE=END+timedelta(days=30)

class FinalRetentionCases(unittest.TestCase):
    setUp=base.BillingRetentionCases.setUp
    tearDown=base.BillingRetentionCases.tearDown
    memory=base.BillingRetentionCases.memory
    save=base.BillingRetentionCases.save
    def cancel_all(self):
        for org in (self.org,self.other):
            self.services.activate(self.admin,org,self.owner,NOW)
            self.services.cancel(self.owner,org,NOW)
    def proof(self,org=None):
        return self.ops.retention.register_purchase(self.admin,'P-001',org or self.org,'2026-01-01','owner@example.test',True,'2027-12-31',self.owner)
    def fresh_recontract(self,org=None,**extra):
        values=dict(identity_verified=True,monthly_payment_confirmed=True,paid_through='2027-01-31')
        values.update(extra)
        return self.ops.retention.recontract(self.admin,'P-001',org or self.org,'owner@example.test','synthetic',now=DUE,**values)
    def test_migration_idempotent_no_purchase_or_b2c_inference(self):
        from operations_repository import OperationsRepository
        OperationsRepository(self.path)
        self.assertEqual(self.ops.retention.purchases(self.admin),[])
        self.cancel_all()
        self.assertIn('b2c_active_or_unknown',self.ops.retention.user_plan(self.admin,self.owner,DUE)['blockers'])
    def test_partial_org_cancel_protects_user_and_other_data(self):
        self.save(self.other);self.services.activate(self.admin,self.org,self.owner,NOW);self.services.cancel(self.owner,self.org,NOW)
        self.ops.retention.confirm_b2c(self.admin,self.owner,'inactive')
        self.assertFalse(self.ops.retention.user_plan(self.admin,self.owner,DUE)['can_delete'])
    def test_all_org_end_after_grace_only(self):
        self.cancel_all();self.ops.retention.confirm_b2c(self.admin,self.owner,'inactive')
        self.assertFalse(self.ops.retention.user_plan(self.admin,self.owner,DUE-timedelta(microseconds=1))['can_delete'])
        self.assertTrue(self.ops.retention.user_plan(self.admin,self.owner,DUE)['can_delete'])
    def test_b2c_active_and_unknown_protect(self):
        self.cancel_all()
        for state in [None,'active']:
            if state:self.ops.retention.confirm_b2c(self.admin,self.owner,state)
            self.assertFalse(self.ops.retention.user_plan(self.admin,self.owner,DUE)['can_delete'])
    def test_b2c_history_protects_even_inactive_declaration(self):
        self.cancel_all();reading=self.save();self.ops.retention.confirm_b2c(self.admin,self.owner,'inactive')
        self.assertIn('b2c_readings',self.ops.retention.user_plan(self.admin,self.owner,DUE)['blockers'])
        with self.memory() as db:
            with self.assertRaises(HistoryError):self.ops.retention.purge_user_memory_fixture(self.admin,self.owner,db,DUE)
            self.assertIsNotNone(db.execute('SELECT id FROM readings WHERE id=?',(reading['id'],)).fetchone())
    def test_recovery_keeps_deadline_and_expires_visibility(self):
        reading=self.save(self.org);self.cancel_all()
        value=self.services.recover(self.owner,self.org,DUE-timedelta(microseconds=1))
        self.assertEqual(datetime.fromisoformat(value['deletion_due_at']),DUE);self.assertFalse(value['deletion_hold'])
        with self.auth.connection() as db:
            self.assertTrue(content_visible(db,self.owner,reading['id'],DUE-timedelta(microseconds=1)))
            self.assertFalse(content_visible(db,self.owner,reading['id'],DUE))
    def test_suspend_year_plus_pending_boundary_for_user(self):
        for org in (self.org,self.other):self.services.suspend(self.admin,org,self.owner,NOW)
        self.ops.retention.confirm_b2c(self.admin,self.owner,'inactive');_,deadline=suspension_retention(NOW)
        self.assertFalse(self.ops.retention.user_plan(self.admin,self.owner,deadline-timedelta(microseconds=1))['can_delete'])
        self.assertTrue(self.ops.retention.user_plan(self.admin,self.owner,deadline)['can_delete'])
    def test_recontract_cancels_schedule_preserves_other_org(self):
        self.proof();self.cancel_all();self.save(self.other)
        result=self.fresh_recontract();self.assertFalse(result['initial_fee_required'])
        value=self.services.summary(self.org,self.owner,DUE)
        self.assertIsNone(value['deletion_due_at']);self.assertIsNone(value['access_ends_at'])
        self.assertIsNotNone(self.services.summary(self.other,self.owner,DUE)['deletion_due_at'])
    def test_recontract_requires_manual_identity_and_monthly_payment(self):
        self.proof();self.cancel_all()
        for kwargs in [dict(identity_verified=False),dict(monthly_payment_confirmed=False),dict(paid_through='2026-11-30')]:
            with self.assertRaises(HistoryError):self.fresh_recontract(**kwargs)
    def test_different_product_does_not_waive_purchase(self):
        self.proof();self.cancel_all()
        with self.assertRaises(HistoryError):self.fresh_recontract(self.other)
    def test_wrong_email_does_not_claim_purchase(self):
        self.proof();self.cancel_all()
        with self.assertRaises(HistoryError):self.ops.retention.recontract(self.admin,'P-001',self.org,'someone@example.test','x',True,True,'2027-01-31',DUE)
    def test_duplicate_purchase_rejected_and_digest_not_projected(self):
        self.proof()
        with self.assertRaises(HistoryError):self.proof()
        self.assertNotIn('purchaser_digest',str(self.ops.retention.purchases(self.admin)))
        self.assertNotIn('owner@example.test',str(self.ops.retention.purchases(self.admin)))
    def test_purchase_requires_review_date(self):
        with self.assertRaises(HistoryError):self.ops.retention.register_purchase(self.admin,'x',self.org,'2026-01-01','owner@example.test',True,'2026-01-01')
    def test_teacher_cannot_access_purchase_or_user_plan(self):
        for action in [lambda:self.ops.retention.purchases(self.teacher),lambda:self.ops.retention.user_plan(self.teacher,self.owner,DUE),lambda:self.ops.retention.confirm_b2c(self.teacher,self.owner,'inactive')]:
            with self.assertRaises(HistoryError):action()
    def test_operator_user_never_deleted(self):
        self.ops.retention.confirm_b2c(self.admin,self.admin,'inactive')
        self.assertIn('operating_administrator',self.ops.retention.user_plan(self.admin,self.admin,DUE)['blockers'])
    def test_unknown_fk_blocks_instead_of_cascade(self):
        self.cancel_all();self.ops.retention.confirm_b2c(self.admin,self.owner,'inactive')
        with self.auth.connection() as db:db.execute('CREATE TABLE future_dependency(user_id TEXT REFERENCES users(id))')
        self.assertIn('unknown_user_reference:future_dependency',self.ops.retention.user_plan(self.admin,self.owner,DUE)['blockers'])
    def test_memory_user_delete_preserves_purchase_contract_and_accounting(self):
        self.proof();self.save(self.org);self.save(self.other)
        due=self.ops.record_due(self.admin,self.org,self.owner,'2026-09-01',2000)['id'];self.ops.settle_due(self.admin,self.owner,due)
        self.cancel_all();self.ops.retention.confirm_b2c(self.admin,self.owner,'inactive')
        db=self.memory()
        try:
            self.ops.retention.purge_user_memory_fixture(self.admin,self.owner,db,DUE)
            self.assertIsNone(db.execute('SELECT id FROM users WHERE id=?',(self.owner,)).fetchone())
            self.assertEqual(db.execute('SELECT count(*) FROM purchase_proofs').fetchone()[0],1)
            self.assertIsNone(db.execute('SELECT user_id FROM purchase_links').fetchone()[0])
            self.assertTrue(db.execute("SELECT 1 FROM retained_records WHERE record_kind='manual_dues' AND record_key=?",(due,)).fetchone())
            self.assertTrue(db.execute("SELECT 1 FROM retained_records WHERE record_kind='user_service_contracts'").fetchone())
            self.assertNotIn('PRIVATE-CONTENT',str([dict(r) for r in db.execute('SELECT * FROM retained_records')]))
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
        finally:db.close()
    def test_file_db_user_delete_rejected(self):
        self.cancel_all()
        with self.auth.connection() as db:
            with self.assertRaises(HistoryError):self.ops.retention.purge_user_memory_fixture(self.admin,self.owner,db,DUE)
    def test_recontract_after_user_deleted_uses_new_user_and_no_history_restore(self):
        self.proof();self.cancel_all();self.ops.retention.confirm_b2c(self.admin,self.owner,'inactive');db=self.memory()
        try:
            self.ops.retention.purge_user_memory_fixture(self.admin,self.owner,db,DUE)
            # Repository writes here are injected exclusively into the isolated memory fixture.
            from contextlib import contextmanager
            @contextmanager
            def change(actor):
                with db:
                    db.execute('BEGIN IMMEDIATE');self.ops.require_admin(db,actor);yield db
            with patch.object(self.ops,'change',change):result=self.fresh_recontract()
            self.assertNotEqual(result['id'],self.owner);self.assertTrue(result['setup_pending'])
            self.assertFalse(result['initial_fee_required']);self.assertFalse(result['deleted_history_restorable'])
            self.assertEqual(db.execute('SELECT paid_through FROM service_contract_terms WHERE user_id=?',(result['id'],)).fetchone()[0],'2027-01-31')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
        finally:db.close()
    def test_restore_expired_cancellation_from_pre_cancel_backup(self):
        reading=self.save(self.org)
        for org in (self.org,self.other):self.services.activate(self.admin,org,self.owner,NOW)
        db=self.memory();self.services.cancel(self.owner,self.org,NOW)
        export=self.ops.retention.restore_manifest(self.admin,DUE)
        try:
            self.ops.retention.apply_restore_memory_fixture(self.admin,db,export['manifest'],export['sha256'],DUE)
            self.assertIsNone(db.execute('SELECT id FROM readings WHERE id=?',(reading['id'],)).fetchone())
            self.assertIsNotNone(db.execute('SELECT id FROM users WHERE id=?',(self.owner,)).fetchone())
        finally:db.close()
    def test_restore_recovery_does_not_extend_original_deadline(self):
        self.save(self.org);self.cancel_all();db=self.memory();self.services.recover(self.owner,self.org,END+timedelta(days=1))
        export=self.ops.retention.restore_manifest(self.admin,DUE)
        try:
            self.ops.retention.apply_restore_memory_fixture(self.admin,db,export['manifest'],export['sha256'],DUE)
            self.assertEqual(db.execute('SELECT count(*) FROM readings').fetchone()[0],0)
        finally:db.close()
    def test_restore_recontract_requires_current_contract_reconciliation(self):
        self.proof();self.cancel_all();db=self.memory();self.fresh_recontract();export=self.ops.retention.restore_manifest(self.admin,DUE)
        try:
            with self.assertRaises(HistoryError):self.ops.retention.apply_restore_memory_fixture(self.admin,db,export['manifest'],export['sha256'],DUE)
        finally:db.close()
    def test_restore_tampered_or_wrong_origin_rejected(self):
        db=self.memory();export=self.ops.retention.restore_manifest(self.admin,DUE)
        try:
            for digest in ['', 'wrong']:
                with self.assertRaises(HistoryError):self.ops.retention.restore_preview(self.admin,db,export['manifest'],digest,DUE)
            export['manifest']['origin']='wrong'
            with self.assertRaises(HistoryError):self.ops.retention.restore_preview(self.admin,db,export['manifest'],export['sha256'],DUE)
        finally:db.close()
    def test_restore_file_db_application_rejected(self):
        export=self.ops.retention.restore_manifest(self.admin,DUE)
        with self.auth.connection() as db:
            with self.assertRaises(HistoryError):self.ops.retention.apply_restore_memory_fixture(self.admin,db,export['manifest'],export['sha256'],DUE)

    def test_b2c_unsaved_execution_protects_user(self):
        from execution_repository import ExecutionRepository
        ledger=ExecutionRepository(self.ops);self.cancel_all();self.ops.retention.confirm_b2c(self.admin,self.owner,'inactive')
        with self.auth.connection() as db:
            db.execute("INSERT INTO successful_executions VALUES ('x',?,NULL,'b2c','key','mac','comparison',?)",(self.owner,NOW.isoformat()))
        self.assertIn('b2c_execution_records',self.ops.retention.user_plan(self.admin,self.owner,DUE)['blockers'])
    def test_recontract_with_unsettled_dues_rejected(self):
        self.proof();self.ops.record_due(self.admin,self.org,self.owner,'2026-09-01',2000);self.cancel_all()
        with self.assertRaises(HistoryError):self.fresh_recontract()
    def test_new_recontract_initial_setup_preserves_confirmed_paid_period(self):
        self.proof();self.cancel_all();self.ops.retention.confirm_b2c(self.admin,self.owner,'inactive');db=self.memory()
        from contextlib import contextmanager
        @contextmanager
        def change(actor):
            with db:
                db.execute('BEGIN IMMEDIATE');yield db
        try:
            self.ops.retention.purge_user_memory_fixture(self.admin,self.owner,db,DUE)
            with patch.object(self.ops,'change',change):result=self.fresh_recontract()
            from service_contract_repository import activate_initial_contracts
            activate_initial_contracts(db,result['id'],DUE);db.commit()
            self.assertEqual(db.execute('SELECT paid_through FROM service_contract_terms WHERE user_id=?',(result['id'],)).fetchone()[0],'2027-01-31')
        finally:db.close()
    def test_restore_user_tombstone_preserves_proof_and_accounting(self):
        self.proof();self.save(self.org);self.save(self.other);self.cancel_all();self.ops.retention.confirm_b2c(self.admin,self.owner,'inactive')
        old=self.memory();fresh=self.memory()
        from contextlib import contextmanager
        @contextmanager
        def connection():yield fresh
        try:
            self.ops.retention.purge_user_memory_fixture(self.admin,self.owner,fresh,DUE)
            with patch.object(self.auth,'connection',connection):export=self.ops.retention.restore_manifest(self.admin,DUE)
            fresh.commit()
            self.ops.retention.apply_restore_memory_fixture(self.admin,old,export['manifest'],export['sha256'],DUE)
            self.assertIsNone(old.execute('SELECT id FROM users WHERE id=?',(self.owner,)).fetchone())
            self.assertEqual(old.execute('SELECT count(*) FROM purchase_proofs').fetchone()[0],1)
            self.assertTrue(old.execute('SELECT 1 FROM retained_records').fetchone())
            self.assertEqual(old.execute('PRAGMA foreign_key_check').fetchall(),[])
        finally:old.close();fresh.close()
    def test_stale_manifest_rejected_by_latest_external_digest(self):
        self.cancel_all();db=self.memory();old=self.ops.retention.restore_manifest(self.admin,NOW)
        self.services.recover(self.owner,self.org,END+timedelta(days=1));fresh=self.ops.retention.restore_manifest(self.admin,DUE)
        try:
            with self.assertRaises(HistoryError):self.ops.retention.restore_preview(self.admin,db,old['manifest'],fresh['sha256'],DUE)
        finally:db.close()
    def test_retention_review_is_operator_only_and_audited(self):
        self.proof();self.ops.retention.review(self.admin,'purchase','P-001','2028-12-31','再契約購入証明')
        self.assertEqual(self.ops.retention.purchases(self.admin)[0]['review_on'],'2028-12-31')
        with self.assertRaises(HistoryError):self.ops.retention.review(self.teacher,'purchase','P-001','2029-12-31','x')
        self.assertIn('retention-review-purchase',str(self.ops.audit_list(self.admin)))

    def test_restore_revokes_sessions_and_reset_tokens(self):
        token=self.auth.login('owner@example.test',base.PASSWORD)[1]
        from password_reset_service import PasswordResetRepository
        resets=PasswordResetRepository(self.auth);resets.issue('owner@example.test',NOW.timestamp())
        db=self.memory();export=self.ops.retention.restore_manifest(self.admin,DUE)
        try:
            self.ops.retention.apply_restore_memory_fixture(self.admin,db,export['manifest'],export['sha256'],DUE)
            self.assertEqual(db.execute('SELECT count(*) FROM auth_sessions WHERE revoked_at IS NULL').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM password_reset_tokens WHERE used_at IS NULL').fetchone()[0],0)
        finally:db.close()
    def test_internal_user_removal_file_db_also_rejected(self):
        with self.auth.connection() as db:
            with self.assertRaises(HistoryError):self.ops.retention.remove_user_records(db,self.owner,DUE)

    def test_restore_recent_suspension_does_not_restore_org_access(self):
        self.services.activate(self.admin,self.org,self.owner,NOW);db=self.memory()
        self.services.suspend(self.admin,self.org,self.owner,NOW+timedelta(days=1));export=self.ops.retention.restore_manifest(self.admin,NOW+timedelta(days=2))
        try:
            self.ops.retention.apply_restore_memory_fixture(self.admin,db,export['manifest'],export['sha256'],NOW+timedelta(days=2))
            self.assertEqual(db.execute('SELECT state FROM user_service_contracts WHERE organization_id=? AND user_id=?',(self.org,self.owner)).fetchone()[0],'suspended')
            self.assertEqual(db.execute('SELECT count(*) FROM users WHERE status!=?',('disabled',)).fetchone()[0],0)
        finally:db.close()
    def test_restore_dependency_failure_rolls_back_entire_fixture(self):
        reading=self.save(self.org);self.save(link={'mode':'existing_group','person_id':reading['person_id'],'group_id':reading['group_id'],'source_reading_id':reading['id']})
        self.services.activate(self.admin,self.org,self.owner,NOW);db=self.memory();self.services.cancel(self.owner,self.org,NOW)
        export=self.ops.retention.restore_manifest(self.admin,DUE)
        try:
            before=[tuple(r) for r in db.execute('SELECT * FROM service_contract_terms')]
            with self.assertRaises(HistoryError):self.ops.retention.apply_restore_memory_fixture(self.admin,db,export['manifest'],export['sha256'],DUE)
            self.assertEqual([tuple(r) for r in db.execute('SELECT * FROM service_contract_terms')],before)
            self.assertEqual(db.execute('SELECT count(*) FROM readings').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT count(*) FROM users WHERE status=?',('active',)).fetchone()[0],3)
        finally:db.close()

if __name__=='__main__':unittest.main()
