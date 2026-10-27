"""Synthetic files/keys only. Includes actual child exits and durable restart.

No network, real HDD, live DB, task registration or production key generation.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contextlib import closing
from datetime import datetime, time, timedelta, timezone
import json
import os
import secrets
import shutil
import subprocess
import unittest
from unittest.mock import patch
from research.home_backup_storage import (OwnedHomeLab, ProcessLock, LabFailure, canonical, digest, BackupSchedule, JST, slot)
from research.home_backup_jobs import SyntheticVPS, SyntheticHomeJob
from research.home_backup_ledger import DurableLedgerMock
from operations_repository import OperationsRepository
from password_reset_service import PasswordResetRepository
from retention_repository import record_deletion

NOW = datetime(2026,10,26,18,tzinfo=timezone.utc)  # Fixture 03:00 JST, not deployment policy.


class HomeBackupCases(unittest.TestCase):
    def setUp(self):
        self.lab = OwnedHomeLab(shutil.which('node') or 'synthetic-node-unavailable')
        self.addCleanup(self.lab.__exit__,None,None,None)
        self.ops = OperationsRepository(self.lab.source_lab.source)
        self.server = self.server_new()
        self.job = self.job_new()

    def server_new(self, **changes):
        return SyntheticVPS(self.lab,**({'schedule':time(3),'staging_days':3,'staging_limit_bytes':2*1024*1024}|changes))

    def job_new(self, **changes):
        return SyntheticHomeJob(self.lab,self.server,**({'schedule':time(3)}|changes))

    def day(self, day=0):
        now = NOW+timedelta(days=day)
        row = self.server.generate(now)
        result = self.job.run_daily(now+timedelta(minutes=1))
        return row,result

    def seed(self):
        password = secrets.token_urlsafe(32)
        self.admin = self.ops.auth.create_user('synthetic-admin@example.test',password)['id']
        self.owner = self.ops.auth.create_user('synthetic-owner@example.test',password)['id']
        self.ops.bootstrap(self.admin)
        self.org = self.ops.create_organization(self.admin,'合成一','one')['id']
        self.other = self.ops.create_organization(self.admin,'合成二','two')['id']
        for org in (self.org,self.other):
            self.ops.assign(self.admin,org,self.owner,'student',True,2000)
            self.ops.services.activate(self.admin,org,self.owner,NOW)
        self.ops.auth.login('synthetic-owner@example.test',password)
        PasswordResetRepository(self.ops.auth).issue('synthetic-owner@example.test',NOW.timestamp())

    def reading(self, org):
        return self.ops.product.history.create(self.owner,{
            'input_snapshot':{'form':{'surname':'合成','givenName':'検証','birthDate':'1988-08-12','readingDate':'2026-10-27'}},
            'result_snapshot':{'ok':True},'memo':'synthetic-only'},('lab','lab',1),org)['id']

    def publish(self, ledger, now=NOW):
        revision = ledger.note_change(now)
        ledger.publish(self.ops.retention.restore_manifest(self.admin,now),revision,now)
        return revision

    def crash_child(self, point, now):
        child = '''import os,sys
from datetime import datetime,time
from research.home_backup_storage import OwnedHomeLab
from research.home_backup_jobs import SyntheticVPS,SyntheticHomeJob
lab=OwnedHomeLab.attach_for_test(sys.argv[1],sys.argv[2])
server=SyntheticVPS(lab,schedule=time(3),staging_days=3,staging_limit_bytes=2*1024*1024)
def fault(stage,identifier):
    if stage==sys.argv[3]:os._exit(73)
SyntheticHomeJob(lab,server,schedule=time(3),point=fault).run_daily(datetime.fromisoformat(sys.argv[4]))
'''
        result = subprocess.run([sys.executable,'-B','-c',child,str(self.lab.root),self.lab.generation,point,now.isoformat()],
                                cwd=Path(__file__).resolve().parents[1],capture_output=True,timeout=45)
        self.assertEqual(result.returncode,73,result.stderr.decode(errors='replace'))

    def test_normal_gzip_encrypted_disk_receipt_persists_without_plain_copy(self):
        row,result = self.day()
        self.assertEqual(result['status'],'completed')
        body = self.lab.artifact('mock-hdd',row['id']).read_bytes()
        self.assertNotIn(b'SQLite format 3',body)
        self.assertEqual(self.job_new().state.rows('SELECT state FROM backups')[0]['state'],'verified')
        self.assertEqual(self.server_new().catalog()[0]['state'],'acked')
        self.assertEqual(list(self.lab.root.glob('snapshot-*.sqlite3')),[])
        self.assertEqual(list(self.lab.path('mock-hdd').glob('*.part')),[])

    def test_same_day_generation_and_restarted_job_are_idempotent(self):
        row,_ = self.day(); path = self.lab.artifact('mock-hdd',row['id']); before = path.read_bytes()
        self.assertEqual(self.server_new().generate(NOW)['id'],row['id'])
        result = self.job_new().run_daily(NOW+timedelta(minutes=2))
        self.assertEqual(result['status'],'already_completed')
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(len(self.job.state.rows('SELECT * FROM backups')),1)

    def test_explicit_schedule_before_time_and_startup_catchup(self):
        self.assertIsNone(self.server.generate(NOW-timedelta(seconds=1)))
        self.assertEqual(self.job.run_daily(NOW-timedelta(seconds=1))['status'],'not_due')
        self.server.generate(NOW)
        result = self.job_new().run_daily(NOW+timedelta(hours=23),catch_up=True)
        self.assertEqual(result['received'],1)
        with self.assertRaises(LabFailure): self.job_new(schedule=None)

    def test_clock_reversal_and_invalid_retry_count_refused(self):
        self.day()
        with self.assertRaises(LabFailure): self.job_new().run_daily(NOW)
        with self.assertRaises(LabFailure): self.server_new().generate(NOW-timedelta(seconds=1))
        with self.assertRaises(LabFailure): self.job.run_daily(NOW.replace(tzinfo=None))
        with self.assertRaises(LabFailure): self.job.run_daily(NOW,attempts=4)

    def test_thirty_generations_and_day_thirty_one_cleanup(self):
        first = None
        for day in range(31):
            row,result = self.day(day)
            self.assertEqual(result['status'],'completed')
            if first is None: first=row
        verified = self.job.state.rows("SELECT * FROM backups WHERE state='verified'")
        self.assertEqual(len(verified),30)
        self.assertFalse(self.lab.artifact('mock-hdd',first['id']).exists())
        self.assertEqual(len(list(self.lab.path('mock-hdd').glob('*.enc'))),30)

    def test_one_day_pc_stop_catches_up_without_duplicate(self):
        self.day(); self.server.generate(NOW+timedelta(days=1)); self.server.generate(NOW+timedelta(days=2))
        result = self.job_new().run_daily(NOW+timedelta(days=2,minutes=1))
        self.assertEqual(result['status'],'completed'); self.assertEqual(result['received'],2)
        self.assertEqual(len(self.job.state.rows("SELECT * FROM backups WHERE state='verified'")),3)

    def test_several_day_pc_stop_recovers_all_available_points(self):
        self.day()
        for day in (1,2,3):
            self.server.generate(NOW+timedelta(days=day)); self.server.sweep(NOW+timedelta(days=day))
        result = self.job_new().run_daily(NOW+timedelta(days=3,minutes=1))
        self.assertEqual(result['received'],3); self.assertEqual(result['warnings'],[])

    def test_staging_window_miss_is_reported_as_gap(self):
        self.day()
        for day in range(1,6):
            self.server.generate(NOW+timedelta(days=day)); self.server.sweep(NOW+timedelta(days=day))
        result = self.job_new().run_daily(NOW+timedelta(days=5,minutes=1))
        self.assertEqual(result['status'],'attention'); self.assertIn('staging_gap',result['warnings'])
        self.assertTrue(self.server.state.rows("SELECT * FROM outbox WHERE code='delivery_overdue'"))

    def test_interrupted_transfer_resumes_durable_partial_after_restart(self):
        row = self.server.generate(NOW)
        def drop(stage,identifier):
            if stage=='transfer_chunk': self.lab.link_available=False
        with self.assertRaises(LabFailure): self.job_new(point=drop).run_daily(NOW+timedelta(minutes=1))
        self.assertTrue(self.lab.artifact('mock-hdd',row['id'],'.part').exists())
        self.assertFalse(self.lab.artifact('mock-hdd',row['id']).exists())
        self.lab.link_available=True
        self.assertEqual(self.job_new().run_daily(NOW+timedelta(minutes=2))['status'],'completed')
        self.assertEqual(len(list(self.lab.path('mock-hdd').glob('*.enc'))),1)

    def test_corrupted_partial_is_safely_restarted(self):
        row = self.server.generate(NOW)
        with self.job.state.db() as db:
            db.execute("INSERT INTO backups(id,slot,created_at,metadata,sha256,size,state) VALUES (?,?,?,?,?,?,'receiving')",
                       tuple(row[k] for k in ('id','slot','created_at','metadata','sha256','size')))
        self.lab.write(self.lab.artifact('mock-hdd',row['id'],'.part'),b'corrupted partial')
        self.assertEqual(self.job.run_daily(NOW+timedelta(minutes=1))['status'],'completed')
        self.assertTrue(self.job.state.rows("SELECT * FROM events WHERE code='partial_restarted'"))

    def test_actual_process_exit_mid_transfer_releases_lock_and_resumes(self):
        row = self.server.generate(NOW)
        self.crash_child('transfer_chunk',NOW+timedelta(minutes=1))
        self.assertTrue(self.lab.artifact('mock-hdd',row['id'],'.part').exists())
        self.assertEqual(self.job_new().run_daily(NOW+timedelta(minutes=2))['status'],'completed')

    def test_actual_exit_after_rename_recovers_receipt_without_duplicate(self):
        row = self.server.generate(NOW)
        self.crash_child('received_renamed',NOW+timedelta(minutes=1))
        body = self.lab.artifact('mock-hdd',row['id']).read_bytes()
        self.assertEqual(self.job_new().state.rows('SELECT state FROM backups')[0]['state'],'receiving')
        self.assertEqual(self.job_new().run_daily(NOW+timedelta(minutes=2))['status'],'completed')
        self.assertEqual(self.lab.artifact('mock-hdd',row['id']).read_bytes(),body)

    def test_corrupt_transport_file_never_becomes_verified(self):
        row = self.server.generate(NOW)
        self.lab.write(self.lab.artifact('vps-stage',row['id']),b'broken',replace=True)
        with self.assertRaises(LabFailure): self.job.run_daily(NOW+timedelta(minutes=1))
        self.assertFalse(self.job.state.rows("SELECT * FROM backups WHERE state='verified'"))

    def test_hash_recalculation_cannot_authenticate_modified_header(self):
        row = self.server.generate(NOW)
        path = self.lab.artifact('vps-stage',row['id'])
        value = json.loads(path.read_bytes()); value['header']['raw_sha256']='0'*64
        body = canonical(value); self.lab.write(path,body,replace=True)
        with self.server.state.db() as db:
            db.execute('UPDATE backups SET metadata=?,sha256=?,size=? WHERE id=?',
                       (canonical(value['header']).decode(),digest(body),len(body),row['id']))
        with self.assertRaises(LabFailure): self.job.run_daily(NOW+timedelta(minutes=1))
        self.assertFalse(self.job.state.rows("SELECT * FROM backups WHERE state='verified'"))

    def test_missing_hdd_has_no_fallback_and_reconnect_retries(self):
        self.server.generate(NOW); self.lab.disk_available=False
        with self.assertRaises(LabFailure): self.job.run_daily(NOW+timedelta(minutes=1))
        self.assertEqual(list(self.lab.path('mock-hdd').glob('*.enc')),[])
        self.lab.disk_available=True
        self.assertEqual(self.job_new().run_daily(NOW+timedelta(minutes=2))['status'],'completed')

    def test_volume_identity_mismatch_refused(self):
        self.server.generate(NOW)
        self.lab.write(self.lab.path('mock-hdd','volume.json'),canonical({'synthetic_volume':'wrong'}),replace=True)
        with self.assertRaises(LabFailure): self.job.run_daily(NOW+timedelta(minutes=1))
        self.assertEqual(list(self.lab.path('mock-hdd').glob('*.part')),[])

    def test_hdd_capacity_failure_is_persisted(self):
        self.server.generate(NOW); self.lab.disk_free_bytes=0
        with self.assertRaises(LabFailure): self.job.run_daily(NOW+timedelta(minutes=1))
        self.assertEqual(self.job_new().state.rows('SELECT state FROM runs')[0]['state'],'failed')
        self.assertTrue(self.job.state.rows("SELECT * FROM outbox WHERE code='job_failed'"))

    def test_multiple_job_invocations_are_excluded_by_os_lock(self):
        self.server.generate(NOW)
        with ProcessLock(self.lab,'pc-state'):
            with self.assertRaisesRegex(LabFailure,'already_running'):
                self.job_new().run_daily(NOW+timedelta(minutes=1))
        self.assertEqual(self.job.run_daily(NOW+timedelta(minutes=2))['status'],'completed')

    def test_generation_failure_is_retryable_and_plain_snapshot_removed(self):
        with patch.object(self.lab.source_lab,'snapshot',side_effect=OSError('synthetic secret detail')):
            with self.assertRaises(LabFailure): self.server.generate(NOW)
        self.assertEqual(list(self.lab.root.glob('snapshot-*.sqlite3')),[])
        self.assertEqual(self.server.state.rows('SELECT state FROM backups')[0]['state'],'pending')
        self.assertEqual(self.server.generate(NOW+timedelta(seconds=1))['state'],'ready')
        self.assertNotIn('synthetic secret detail',str(self.server.state.rows('SELECT * FROM events')))

    def test_staging_capacity_failure_does_not_publish_or_leave_plain_file(self):
        with self.assertRaises(LabFailure): self.server_new(staging_limit_bytes=1).generate(NOW)
        self.assertEqual(list(self.lab.path('vps-stage').glob('*.enc')),[])
        self.assertEqual(list(self.lab.root.glob('snapshot-*.sqlite3')),[])
        self.assertEqual(self.server.generate(NOW+timedelta(seconds=1))['state'],'ready')

    def test_server_generation_stopped_is_detected_by_home(self):
        row,_ = self.day()
        result = self.job_new().run_daily(NOW+timedelta(days=2,minutes=1))
        self.assertIn('generation_stale',result['warnings'])
        self.assertTrue(self.lab.artifact('mock-hdd',row['id']).exists())

    def test_last_old_good_copy_preserved_and_overdue_then_resolved(self):
        row,_ = self.day()
        result = self.job_new().run_daily(NOW+timedelta(days=40,minutes=1))
        self.assertEqual(result['status'],'attention'); self.assertIn('retention_overdue',result['warnings'])
        self.assertTrue(self.lab.artifact('mock-hdd',row['id']).exists())
        self.server.generate(NOW+timedelta(days=41))
        result = self.job_new().run_daily(NOW+timedelta(days=41,minutes=1))
        self.assertEqual(result['status'],'attention'); self.assertIn('generation_gap',result['warnings'])
        self.assertNotIn('retention_overdue',result['warnings'])
        self.assertFalse(self.lab.artifact('mock-hdd',row['id']).exists())

    def test_unverifiable_expired_copy_is_not_destroyed_by_cleanup(self):
        row,_=self.day()
        self.lab.path('pc-key','synthetic.key').unlink()
        warnings=self.job.prune(NOW+timedelta(days=40))
        self.assertIn('retention_unverified',warnings)
        self.assertTrue(self.lab.artifact('mock-hdd',row['id']).exists())

    def test_staging_cleanup_preserves_verified_fallback_when_newest_corrupt(self):
        old=self.server.generate(NOW)
        latest=self.server.generate(NOW+timedelta(days=1))
        self.lab.write(self.lab.artifact('vps-stage',latest['id']),b'corrupt',replace=True)
        self.server.sweep(NOW+timedelta(days=5))
        self.assertTrue(self.lab.artifact('vps-stage',old['id']).exists())
        self.assertTrue(self.server.state.rows("SELECT * FROM outbox WHERE code='staging_retention_overdue'"))

    def test_generation_gap_is_reported_at_both_roles_after_new_generation(self):
        self.day()
        self.server.generate(NOW+timedelta(days=2))
        self.assertTrue(self.server.state.rows("SELECT * FROM outbox WHERE code='generation_gap'"))
        result=self.job.run_daily(NOW+timedelta(days=2,minutes=1))
        self.assertIn('generation_gap',result['warnings'])
        self.assertEqual(result['status'],'attention')

    def test_actual_second_process_cannot_acquire_live_job_lock(self):
        child='''import sys
from research.home_backup_storage import OwnedHomeLab,ProcessLock
lab=OwnedHomeLab.attach_for_test(sys.argv[1],sys.argv[2])
with ProcessLock(lab,'pc-state'):
 print('locked',flush=True)
 sys.stdin.readline()
'''
        process=subprocess.Popen([sys.executable,'-B','-c',child,str(self.lab.root),self.lab.generation],
                                 stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(),'locked')
            with self.assertRaisesRegex(LabFailure,'already_running'):
                with ProcessLock(self.lab,'pc-state'): pass
            process.communicate('\n',timeout=15)
            self.assertEqual(process.returncode,0)
        finally:
            if process.poll() is None: process.kill(); process.communicate(timeout=15)

    def test_server_publication_interruption_reuses_authenticated_orphan(self):
        def fail(stage,identifier):
            if stage=='server_published': raise RuntimeError('synthetic interruption')
        with self.assertRaises(LabFailure): self.server_new(point=fail).generate(NOW)
        pending=self.server.catalog()[0]
        self.assertEqual(pending['state'],'pending')
        body=self.lab.artifact('vps-stage',pending['id']).read_bytes()
        row=self.server_new().generate(NOW+timedelta(seconds=1))
        self.assertEqual(row['id'],pending['id'])
        self.assertEqual(body,self.lab.artifact('vps-stage',row['id']).read_bytes())
        self.assertEqual(self.job_new().run_daily(NOW+timedelta(minutes=1))['status'],'completed')

    def test_ledger_received_file_before_checkpoint_is_restartable(self):
        self.seed(); ledger=DurableLedgerMock(self.lab); self.publish(ledger)
        def fail(stage,identifier):
            if stage=='ledger_received': raise RuntimeError('synthetic interruption')
        with self.assertRaises(RuntimeError): DurableLedgerMock(self.lab,point=fail).sync(NOW)
        self.assertEqual(ledger._head()[0],0)
        self.assertEqual(DurableLedgerMock(self.lab).sync(NOW+timedelta(seconds=1)),1)

    def test_actual_exit_during_delete_resumes_without_retransfer(self):
        old,_ = self.day(); self.server.generate(NOW+timedelta(days=31))
        self.crash_child('deleted_before_record',NOW+timedelta(days=31,minutes=1))
        self.assertFalse(self.lab.artifact('mock-hdd',old['id']).exists())
        self.assertEqual(self.job_new().state.rows('SELECT state FROM backups WHERE id=?',(old['id'],))[0]['state'],'delete_pending')
        self.assertIn('generation_gap',self.job_new().run_daily(NOW+timedelta(days=31,minutes=2))['warnings'])
        self.assertEqual(self.job.state.rows('SELECT state FROM backups WHERE id=?',(old['id'],))[0]['state'],'deleted')

    def test_delete_failure_keeps_durable_pending_state_for_retry(self):
        old,_ = self.day(); self.server.generate(NOW+timedelta(days=31))
        def fail(stage,identifier):
            if stage=='delete_pending': raise PermissionError('synthetic')
        with self.assertRaises(LabFailure): self.job_new(point=fail).run_daily(NOW+timedelta(days=31,minutes=1))
        self.assertTrue(self.lab.artifact('mock-hdd',old['id']).exists())
        self.assertIn('generation_gap',self.job_new().run_daily(NOW+timedelta(days=31,minutes=2))['warnings'])

    def test_copy_mtime_does_not_extend_source_retention(self):
        old,_ = self.day()
        path = self.lab.artifact('mock-hdd',old['id']); future=(NOW+timedelta(days=100)).timestamp()
        os.utime(path,(future,future))
        self.day(31)
        self.assertFalse(path.exists())

    def test_unknown_inventory_not_deleted_or_claimed_clean(self):
        self.server.generate(NOW)
        unknown=self.lab.path('mock-hdd','unmanaged.txt'); self.lab.write(unknown,b'synthetic do not delete')
        result=self.job.run_daily(NOW+timedelta(minutes=1))
        self.assertEqual(result['status'],'attention'); self.assertIn('unknown_inventory',result['warnings'])
        self.assertTrue(unknown.exists())

    def test_scope_guards_and_audit_failure_prevent_writes(self):
        with self.assertRaises(LabFailure): self.lab.path('..','outside')
        with self.assertRaises(LabFailure): self.lab.artifact('mock-hdd','../../outside')
        with patch.object(self.server.state,'event',side_effect=OSError('audit failure')):
            with self.assertRaises(OSError): self.server.generate(NOW)
        self.assertEqual(list(self.lab.path('vps-stage').glob('*.enc')),[])

    def test_synthetic_key_loss_wrong_key_and_offline_recovery(self):
        self.server.generate(NOW)
        key=self.lab.path('pc-key','synthetic.key'); key.unlink()
        with self.assertRaises(LabFailure): self.job.run_daily(NOW+timedelta(minutes=1))
        self.lab.write(key,secrets.token_bytes(32))
        with self.assertRaises(LabFailure): self.job.run_daily(NOW+timedelta(minutes=2))
        self.lab.recover_synthetic_pc_key()
        self.assertEqual(self.job_new().run_daily(NOW+timedelta(minutes=3))['status'],'completed')

    def test_ledger_revision_chain_persists_across_new_instances(self):
        self.seed(); ledger=DurableLedgerMock(self.lab); self.publish(ledger); ledger.sync(NOW)
        self.publish(ledger,NOW+timedelta(seconds=1)); ledger.sync(NOW+timedelta(seconds=1))
        truth,_,_=DurableLedgerMock(self.lab).approved(NOW+timedelta(seconds=2))
        self.assertEqual(truth['revision'],2)

    def test_ledger_publication_requires_vps_process_lock(self):
        self.seed(); ledger=DurableLedgerMock(self.lab)
        with ProcessLock(self.lab,'vps-state'):
            with self.assertRaisesRegex(LabFailure,'already_running'): ledger.note_change(NOW)
        revision=ledger.note_change(NOW)
        with ProcessLock(self.lab,'vps-state'):
            with self.assertRaisesRegex(LabFailure,'already_running'):
                ledger.publish(self.ops.retention.restore_manifest(self.admin,NOW),revision,NOW)
        ledger.publish(self.ops.retention.restore_manifest(self.admin,NOW),revision,NOW)
        self.assertEqual(ledger.sync(NOW),1)

    def test_offline_change_and_unavailable_independent_authority_block_restore(self):
        self.seed(); row,_=self.day(); ledger=DurableLedgerMock(self.lab)
        self.publish(ledger); ledger.sync(NOW+timedelta(minutes=1))
        self.publish(ledger,NOW+timedelta(minutes=2)); self.lab.link_available=False
        with self.assertRaises(LabFailure): ledger.sync(NOW+timedelta(minutes=3))
        with self.assertRaises(LabFailure): ledger.restore_memory(self.job,row['id'],self.ops,self.admin,NOW+timedelta(minutes=3))
        self.lab.link_available=True; ledger.sync(NOW+timedelta(minutes=4)); self.lab.truth_available=False
        with self.assertRaises(LabFailure): ledger.restore_memory(self.job,row['id'],self.ops,self.admin,NOW+timedelta(minutes=5))

    def test_ledger_missing_revision_refused_then_complete_chain_can_resume(self):
        self.seed(); ledger=DurableLedgerMock(self.lab)
        self.publish(ledger); ledger.sync(NOW)
        self.publish(ledger,NOW+timedelta(seconds=1)); missing=ledger._file('vps-state',2)
        saved=missing.read_bytes(); missing.unlink()
        self.publish(ledger,NOW+timedelta(seconds=2))
        with self.assertRaisesRegex(LabFailure,'revision_missing'): ledger.sync(NOW+timedelta(seconds=3))
        self.lab.write(missing,saved)
        self.assertEqual(ledger.sync(NOW+timedelta(seconds=4)),3)

    def test_incomplete_or_modified_ledger_refused(self):
        self.seed(); ledger=DurableLedgerMock(self.lab); revision=ledger.note_change(NOW)
        with self.assertRaises(LabFailure): ledger.sync(NOW)
        ledger.publish(self.ops.retention.restore_manifest(self.admin,NOW),revision,NOW)
        path=ledger._file('vps-state',1); self.lab.write(path,b'tampered',replace=True)
        with self.assertRaises(LabFailure): ledger.sync(NOW)
        self.assertEqual(ledger._head()[0],0)

    def test_old_checkpoint_substitution_or_missing_home_ledger_refused(self):
        self.seed(); ledger=DurableLedgerMock(self.lab); self.publish(ledger); ledger.sync(NOW)
        old=ledger._file('pc-state',1).read_bytes()
        self.publish(ledger,NOW+timedelta(seconds=1)); ledger.sync(NOW+timedelta(seconds=1))
        latest=ledger._file('pc-state',2); self.lab.write(latest,old,replace=True)
        with self.assertRaises(LabFailure): ledger.approved(NOW+timedelta(seconds=2))
        latest.unlink()
        with self.assertRaises(LabFailure): ledger.approved(NOW+timedelta(seconds=2))

    def test_ledger_replay_deletes_target_preserves_b2c_other_org_locks_auth(self):
        self.seed(); deleted=self.reading(self.org); b2c=self.reading(None); other=self.reading(self.other)
        row,_=self.day()
        with self.ops.auth.connection() as db: record_deletion(db,'scope',self.owner,self.org,[deleted],NOW)
        ledger=DurableLedgerMock(self.lab); self.publish(ledger); ledger.sync(NOW+timedelta(minutes=1))
        with closing(ledger.restore_memory(self.job,row['id'],self.ops,self.admin,NOW+timedelta(minutes=2))) as db:
            self.assertIsNone(db.execute('SELECT id FROM readings WHERE id=?',(deleted,)).fetchone())
            for rid in (b2c,other): self.assertIsNotNone(db.execute('SELECT id FROM readings WHERE id=?',(rid,)).fetchone())
            self.assertEqual(db.execute("SELECT count(*) FROM users WHERE status!='disabled'").fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM auth_sessions WHERE revoked_at IS NULL').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM password_reset_tokens WHERE used_at IS NULL').fetchone()[0],0)
            self.assertEqual(db.execute('PRAGMA database_list').fetchone()[2],'')

    def test_contract_generation_mismatch_blocks_restore(self):
        self.seed(); row,_=self.day()
        with self.ops.auth.connection() as db: db.execute("UPDATE service_contract_terms SET cycle_id='synthetic-new-generation'")
        ledger=DurableLedgerMock(self.lab); self.publish(ledger); ledger.sync(NOW+timedelta(minutes=1))
        with self.assertRaises(LabFailure): ledger.restore_memory(self.job,row['id'],self.ops,self.admin,NOW+timedelta(minutes=2))

    def test_new_change_during_restore_never_returns_connection(self):
        self.seed(); row,_=self.day(); ledger=DurableLedgerMock(self.lab)
        self.publish(ledger); ledger.sync(NOW+timedelta(minutes=1))
        def changed(stage,identifier):
            if stage=='restore_replayed': ledger.note_change(NOW+timedelta(minutes=2))
        ledger.point=changed
        with self.assertRaises(LabFailure): ledger.restore_memory(self.job,row['id'],self.ops,self.admin,NOW+timedelta(minutes=2))
        self.assertTrue(ledger.state.rows("SELECT * FROM outbox WHERE code='restore_denied'"))


class FourSlotBackupCases(unittest.TestCase):
    def setUp(self):
        self.plan=BackupSchedule.parse('07:00,12:00,17:00,23:00',10)
        HomeBackupCases.setUp(self)

    def server_new(self, **changes):
        return SyntheticVPS(self.lab,**({'schedule':self.plan,'staging_days':3,'staging_limit_bytes':256*1024*1024}|changes))

    def job_new(self, **changes):
        return SyntheticHomeJob(self.lab,self.server,**({'schedule':self.plan}|changes))

    seed=HomeBackupCases.seed
    reading=HomeBackupCases.reading
    publish=HomeBackupCases.publish

    def moment(self, day=0, index=0):
        return datetime.combine(datetime(2026,10,27).date()+timedelta(days=day),self.plan.times[index],JST)

    def take(self, day=0, index=0):
        now=self.moment(day,index)
        self.server.sweep(now)
        row=self.server.generate(now)
        result=self.job.run_slot(now+self.plan.pull_delay)
        return row,result

    def crash(self, phase, now, *, source=False):
        child='''import os,sys
from datetime import datetime
from research.home_backup_storage import OwnedHomeLab,BackupSchedule
from research.home_backup_jobs import SyntheticVPS,SyntheticHomeJob
lab=OwnedHomeLab.attach_for_test(sys.argv[1],sys.argv[2])
plan=BackupSchedule.parse(sys.argv[5],10)
def fault(stage,identifier):
 if stage==sys.argv[3]:os._exit(73)
server=SyntheticVPS(lab,schedule=plan,staging_days=3,staging_limit_bytes=256*1024*1024,point=fault)
now=datetime.fromisoformat(sys.argv[4])
if sys.argv[6]=='source':server.generate(now)
else:SyntheticHomeJob(lab,server,schedule=plan,point=fault).run_slot(now)
'''
        result=subprocess.run([sys.executable,'-B','-c',child,str(self.lab.root),self.lab.generation,
                               phase,now.isoformat(),','.join(t.isoformat(timespec='minutes') for t in self.plan.times),
                               'source' if source else 'home'],capture_output=True,timeout=45)
        self.assertEqual(result.returncode,73,result.stderr.decode(errors='replace'))

    def test_four_real_copies_received_with_distinct_slots_and_changed_content(self):
        ids=[]; hashes=[]
        for index in range(4):
            self.ops.auth.create_user(f'synthetic-{index}@example.test',secrets.token_urlsafe(32))
            row,result=self.take(index=index)
            self.assertEqual(result['status'],'completed'); self.assertEqual(result['received'],1)
            ids.append(row['id']); hashes.append(json.loads(row['metadata'])['raw_sha256'])
            with closing(self.lab.decode_backup(self.job.verify_file(row),json.loads(row['metadata']))) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],index+1)
        self.assertEqual(len(set(ids)),4); self.assertEqual(len(set(hashes)),4)
        self.assertEqual(len(self.job.state.rows("SELECT * FROM runs WHERE state='completed'")),4)
        self.assertEqual([r['slot'] for r in self.server.catalog()],
                         [self.plan.key(self.moment(index=i)) for i in range(4)])

    def test_same_slot_retry_and_new_slot_are_distinct(self):
        first,_=self.take()
        self.assertEqual(self.server_new().generate(self.moment()+timedelta(minutes=20))['id'],first['id'])
        self.assertEqual(self.job_new().run_slot(self.moment()+timedelta(minutes=20))['status'],'already_completed')
        self.assertEqual(self.server_new().generate(self.moment()+timedelta(minutes=50))['id'],first['id'])
        second,_=self.take(index=1)
        self.assertNotEqual(first['id'],second['id'])

    def test_late_generation_is_skipped_and_never_backdated(self):
        now=self.moment()+timedelta(hours=1)
        self.assertIsNone(self.server.generate(now)); self.assertEqual(self.server.catalog(),[])
        row=self.server.generate(self.moment(index=1)+timedelta(minutes=3))
        self.assertEqual(datetime.fromisoformat(row['created_at']),self.moment(index=1)+timedelta(minutes=3))
        self.assertEqual(len(self.server.catalog()),1)
        self.assertTrue(self.server.state.rows("SELECT * FROM outbox WHERE code='generation_window_missed'"))

    def test_cross_midnight_and_long_night_interval_do_not_raise_false_stale(self):
        for index in range(4): self.take(index=index)
        self.assertEqual(slot(self.moment(1)-timedelta(minutes=1),self.plan),self.plan.key(self.moment(index=3)))
        result=self.job_new().run_slot(self.moment(1)-timedelta(minutes=1),catch_up=True)
        self.assertEqual(result['status'],'already_completed')
        row,result=self.take(1)
        self.assertEqual(row['slot'],'2026-10-28T07:00+09:00'); self.assertEqual(result['warnings'],[])

    def test_pull_delay_and_missing_latest_generation_detected_in_same_day(self):
        self.take()
        now=self.moment(index=1)
        self.assertEqual(self.job.run_slot(now+timedelta(minutes=5))['status'],'not_due')
        waiting=self.job.run_slot(now+timedelta(minutes=10))
        self.assertIn('generation_pending',waiting['warnings'])
        overdue=self.job.run_slot(now+timedelta(minutes=26))
        self.assertIn('generation_stale',overdue['warnings']); self.assertIn('offsite_backup_stale',overdue['warnings'])
        self.server.sweep(now+timedelta(minutes=26))
        self.server.generate(now+timedelta(minutes=27))
        self.assertEqual(self.job.run_slot(now+timedelta(minutes=28))['status'],'completed')

    def test_skipped_midday_slot_is_detected_at_both_roles(self):
        self.take(); _,result=self.take(index=2)
        self.assertIn('generation_gap',result['warnings'])
        self.assertTrue(self.server.state.rows("SELECT * FROM outbox WHERE code='generation_gap'"))

    def test_pc_restart_recovers_eight_existing_points_without_fabrication(self):
        for index in range(4): self.take(index=index)
        for day in (1,2):
            for index in range(4):
                now=self.moment(day,index); self.server.sweep(now); self.server.generate(now)
        result=self.job_new().run_slot(self.moment(2,3)+timedelta(minutes=10),catch_up=True)
        self.assertEqual(result['received'],8); self.assertEqual(result['warnings'],[])
        self.assertEqual(len(list(self.lab.path('mock-hdd').glob('*.enc'))),12)

    def test_staging_window_loss_and_unacknowledged_points_are_reported(self):
        self.take()
        for day in range(1,5):
            for index in range(4):
                now=self.moment(day,index); self.server.sweep(now); self.server.generate(now)
        result=self.job_new().run_slot(self.moment(4,3)+timedelta(minutes=10),catch_up=True)
        self.assertIn('staging_gap',result['warnings'])
        self.assertTrue(self.server.state.rows("SELECT * FROM outbox WHERE code='delivery_overdue'"))

    def test_thirty_days_keep_120_by_timestamp_and_expire_within_day(self):
        first=[]
        for day in range(30):
            for index in range(4):
                row,result=self.take(day,index)
                self.assertEqual(result['status'],'completed')
                if day==0:first.append(row)
        self.assertEqual(len(list(self.lab.path('mock-hdd').glob('*.enc'))),120)
        _,result=self.take(30)
        self.assertEqual(result['warnings'],[])
        self.assertEqual(len(list(self.lab.path('mock-hdd').glob('*.enc'))),120)
        self.assertFalse(self.lab.artifact('mock-hdd',first[0]['id']).exists())
        self.assertTrue(self.lab.artifact('mock-hdd',first[1]['id']).exists())
        _,result=self.take(30,1)
        self.assertFalse(self.lab.artifact('mock-hdd',first[1]['id']).exists())
        self.assertEqual(len(list(self.lab.path('mock-hdd').glob('*.enc'))),120)

    def test_actual_source_and_receive_crashes_recover_same_slot(self):
        now=self.moment()
        self.crash('server_published',now,source=True)
        pending=self.server.catalog()[0]
        row=self.server.generate(now+timedelta(minutes=1))
        self.assertEqual(row['id'],pending['id'])
        self.crash('transfer_chunk',now+timedelta(minutes=10))
        self.assertTrue(self.lab.artifact('mock-hdd',row['id'],'.part').exists())
        self.assertEqual(self.job_new().run_slot(now+timedelta(minutes=11))['status'],'completed')
        self.assertEqual(len(list(self.lab.path('mock-hdd').glob('*.enc'))),1)

    def test_actual_deletion_crash_resumes_without_retransfer(self):
        old,_=self.take(); self.server.generate(self.moment(31))
        self.crash('deleted_before_record',self.moment(31)+timedelta(minutes=10))
        self.assertFalse(self.lab.artifact('mock-hdd',old['id']).exists())
        self.job_new().run_slot(self.moment(31)+timedelta(minutes=11))
        self.assertEqual(self.job.state.rows('SELECT state FROM backups WHERE id=?',(old['id'],))[0]['state'],'deleted')

    def test_partial_link_failure_capacity_and_corruption_fail_closed(self):
        now=self.moment(); row=self.server.generate(now)
        def disconnect(stage,identifier):
            if stage=='transfer_chunk':self.lab.link_available=False
        with self.assertRaises(LabFailure): self.job_new(point=disconnect).run_slot(now+timedelta(minutes=10))
        self.lab.link_available=True
        self.assertEqual(self.job_new().run_slot(now+timedelta(minutes=11))['status'],'completed')
        self.lab.write(self.lab.artifact('vps-stage',row['id']),b'corrupt',replace=True)
        with self.assertRaises(LabFailure): self.server.generate(now+timedelta(minutes=12))
        self.assertFalse(self.job.state.rows("SELECT * FROM backups WHERE state='receiving'"))

    def test_stage_capacity_failure_does_not_delete_last_good_copy(self):
        old,_=self.take(); used=self.lab.usage()['stage_bytes']
        limited=self.server_new(staging_limit_bytes=used)
        with self.assertRaises(LabFailure): limited.generate(self.moment(index=1))
        self.assertTrue(self.lab.artifact('mock-hdd',old['id']).exists())
        self.assertTrue(self.lab.artifact('vps-stage',old['id']).exists())

    def test_failed_new_capture_preserves_expired_last_good_as_warning(self):
        old,_=self.take(); now=self.moment(40)
        with patch.object(self.lab.source_lab,'snapshot',side_effect=OSError('synthetic failure')):
            with self.assertRaises(LabFailure):self.server.generate(now)
        result=self.job.run_slot(now+timedelta(minutes=10))
        self.assertEqual(result['status'],'attention'); self.assertIn('retention_overdue',result['warnings'])
        self.assertTrue(self.lab.artifact('mock-hdd',old['id']).exists())

    def test_four_slot_restore_keeps_existing_ledger_gate_and_scope_protection(self):
        self.seed(); deleted=self.reading(self.org); b2c=self.reading(None); other=self.reading(self.other)
        row,_=self.take()
        changed=self.moment(index=1)
        with self.ops.auth.connection() as db:record_deletion(db,'scope',self.owner,self.org,[deleted],changed)
        ledger=DurableLedgerMock(self.lab); self.publish(ledger,changed)
        with self.assertRaises(LabFailure):ledger.restore_memory(self.job,row['id'],self.ops,self.admin,changed)
        ledger.sync(changed)
        with closing(ledger.restore_memory(self.job,row['id'],self.ops,self.admin,changed)) as db:
            self.assertIsNone(db.execute('SELECT id FROM readings WHERE id=?',(deleted,)).fetchone())
            for identifier in (b2c,other):self.assertIsNotNone(db.execute('SELECT id FROM readings WHERE id=?',(identifier,)).fetchone())
            self.assertEqual(db.execute("SELECT count(*) FROM users WHERE status!='disabled'").fetchone()[0],0)
        self.lab.truth_available=False
        with self.assertRaises(LabFailure):ledger.restore_memory(self.job,row['id'],self.ops,self.admin,changed)

    def test_schedule_validation_and_storage_metrics(self):
        for text in ('07:00,07:00','12:00,07:00','24:00','7:00','07:00,08:00,09:00,10:00,11:00'):
            with self.assertRaises(LabFailure):BackupSchedule.parse(text,10)
        with self.assertRaises(LabFailure):BackupSchedule.parse('07:00,12:00,17:00,23:00',-1)
        with self.assertRaises(LabFailure):self.job_new(schedule=BackupSchedule.parse('06:00,12:00,17:00,23:00',10))
        _,first=self.take(); _,second=self.take(index=1)
        self.assertGreater(first['storage']['mock_host_free_bytes'],0)
        self.assertGreater(second['storage']['retained_delta_bytes'],0)
        self.assertEqual(second['storage']['partial_bytes'],0)


if __name__=='__main__': unittest.main(verbosity=2)
