"""Synthetic encrypted backup orchestration. No real DB, SMTP, storage or key."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contextlib import closing
from dataclasses import replace
from datetime import datetime, time, timedelta, timezone
import errno
import secrets
import shutil
import sqlite3
import unittest
from unittest.mock import patch

from research.backup_foundation_lab import (SyntheticBackupFoundation, SyntheticNodeAEAD,
    LatestLedgerMock, Copy, LabFailure)
from operations_repository import OperationsRepository
from password_reset_service import PasswordResetRepository
from retention_repository import record_deletion

NOW = datetime(2026, 10, 26, 18, tzinfo=timezone.utc)  # 10/27 03:00 JST; test choice only.


class BackupFoundationCases(unittest.TestCase):
    def setUp(self):
        self.cipher = SyntheticNodeAEAD(shutil.which('node') or 'node-unavailable')
        self.f = SyntheticBackupFoundation(sealer=self.cipher, schedule=time(3))
        self.addCleanup(self.f.__exit__, None, None, None)
        self.ops = OperationsRepository(self.f.lab.source)

    def backup(self, now=NOW):
        return self.f.run_due(now)

    def seed(self):
        password = secrets.token_urlsafe(32)
        self.admin = self.ops.auth.create_user('admin@example.test', password)['id']
        self.owner = self.ops.auth.create_user('owner@example.test', password)['id']
        self.ops.bootstrap(self.admin)
        self.org = self.ops.create_organization(self.admin, '合成', 'synthetic')['id']
        self.other = self.ops.create_organization(self.admin, '別合成', 'synthetic-other')['id']
        for org in (self.org, self.other):
            self.ops.assign(self.admin, org, self.owner, 'student', True, 2000)
            self.ops.services.activate(self.admin, org, self.owner, NOW)
        self.ops.auth.login('owner@example.test', password)
        PasswordResetRepository(self.ops.auth).issue('owner@example.test', NOW.timestamp())

    def reading(self, org):
        return self.ops.product.history.create(self.owner, {
            'input_snapshot': {'form': {'surname': '合成', 'givenName': '試験',
                'birthDate': '1988-08-12', 'readingDate': '2026-10-27'}},
            'result_snapshot': {'ok': True}, 'memo': 'synthetic-only'}, ('lab', 'lab', 1), org)['id']

    def ledger(self, now=NOW):
        ledger = LatestLedgerMock()
        ledger.note_change(now)
        ledger.publish(self.ops.retention.restore_manifest(self.admin, now), now, complete=True)
        return ledger

    def restore(self, receipt, ledger, now=NOW):
        return self.f.restore_memory(receipt, ledger=ledger, operations=self.ops, actor=self.admin, now=now)

    def test_no_db_path_input_or_default_schedule(self):
        with self.assertRaises(TypeError):
            SyntheticBackupFoundation('/var/lib/fortune-app/history.sqlite3')
        self.f.schedule = None
        with self.assertRaisesRegex(LabFailure, 'schedule_not_decided'):
            self.backup()
        self.assertEqual(self.f.store.copies, {})

    def test_daily_boundary_and_next_day_with_timezone_equivalence(self):
        self.assertIsNone(self.backup(NOW - timedelta(microseconds=1)))
        first = self.backup()
        self.assertIsNone(self.backup(NOW.astimezone(timezone(timedelta(hours=9)))))
        self.assertIsNone(self.backup(NOW + timedelta(hours=23)))
        second = self.backup(NOW + timedelta(days=1))
        self.assertNotEqual(first.backup_id, second.backup_id)
        self.assertEqual(len(self.f.store.copies), 2)

    def test_naive_or_reversed_clock_and_retry_limit_rejected(self):
        for value in (NOW.replace(tzinfo=None), '2026-10-27'):
            with self.assertRaises(LabFailure): self.backup(value)
        self.backup()
        with self.assertRaisesRegex(LabFailure, 'clock_reversed'): self.backup(NOW-timedelta(seconds=1))
        for attempts in (0, 4, True):
            with self.assertRaises(LabFailure): self.f.run_due(NOW, attempts=attempts)

    def test_real_aead_roundtrip_unique_nonce_and_no_key_repr(self):
        a = self.cipher.seal(b'synthetic private text', b'metadata')
        b = self.cipher.seal(b'synthetic private text', b'metadata')
        self.assertNotEqual(a[:12], b[:12])
        self.assertEqual(self.cipher.open(a, b'metadata'), b'synthetic private text')
        self.assertNotIn(b'synthetic private text', a)
        self.assertNotIn(self.cipher._key.hex(), repr(self.cipher))

    def test_aead_wrong_key_metadata_tag_and_truncation_rejected(self):
        sealed = self.cipher.seal(b'synthetic', b'metadata')
        other = SyntheticNodeAEAD(shutil.which('node'))
        for cipher, data, aad in ((other, sealed, b'metadata'), (self.cipher, sealed, b'changed'),
                (self.cipher, sealed[:12]+bytes([sealed[12]^1])+sealed[13:], b'metadata'),
                (self.cipher, sealed[:27], b'metadata'), (self.cipher, sealed[:-1], b'metadata')):
            with self.assertRaises(LabFailure): cipher.open(data, aad)

    def test_crypto_unavailable_never_stores_plaintext(self):
        self.f.sealer = None
        with self.assertRaises(LabFailure): self.backup()
        self.f.sealer = SyntheticNodeAEAD('synthetic-nonexistent-executable')
        with self.assertRaises(LabFailure): self.backup()
        self.assertEqual(self.f.store.copies, {})
        self.assertEqual(self.f._completed_dates, set())

    def test_wal_commits_encrypted_and_uncommitted_data_excluded(self):
        with closing(sqlite3.connect(self.f.lab.source)) as writer:
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute('CREATE TABLE wal_probe (id INTEGER)')
            writer.execute('INSERT INTO wal_probe VALUES (1)'); writer.commit()
            writer.execute('INSERT INTO wal_probe VALUES (2)')
            receipt = self.backup()
            sealed = self.f.store.read_primary(receipt.backup_id)
            self.assertNotIn(b'SQLite format 3', sealed)
            with closing(self.f._decode(receipt, sealed)) as restored:
                self.assertEqual([tuple(r) for r in restored.execute('SELECT * FROM wal_probe')], [(1,)])

    def test_permission_capacity_and_interruption_are_bounded_and_sanitized(self):
        for error in (PermissionError('synthetic-secret'), OSError(errno.ENOSPC, 'synthetic-secret'),
                      InterruptedError('synthetic-secret')):
            with self.subTest(error=type(error).__name__):
                with patch.object(self.f.store, 'put_once', side_effect=error) as put:
                    with self.assertRaisesRegex(LabFailure, 'backup_not_verified'): self.backup()
                    self.assertEqual(put.call_count, 3)
                self.assertEqual(self.f._completed_dates, set())
                self.assertNotIn('synthetic-secret', str(self.f.audit))
        self.assertIsNotNone(self.backup())

    def test_ambiguous_put_success_retry_uses_identical_object_without_duplicate(self):
        put = self.f.store.put_once
        def ambiguous(*args):
            put(*args)
            if ambiguous.first:
                ambiguous.first = False
                raise TimeoutError('ack lost')
        ambiguous.first = True
        with patch.object(self.f.store, 'put_once', side_effect=ambiguous) as mocked:
            self.backup()
            self.assertEqual(mocked.call_count, 2)
        self.assertEqual(len(self.f.store.copies), 1)

    def test_read_failure_cannot_mark_schedule_complete_and_retry_safe(self):
        with patch.object(self.f.store, 'read_primary', side_effect=PermissionError('synthetic')):
            with self.assertRaises(LabFailure): self.backup()
        self.assertFalse(self.f._completed_dates)
        self.backup()
        self.assertEqual(len(self.f.store.copies), 1)

    def test_corrupted_saved_ciphertext_not_verified(self):
        put = self.f.store.put_once
        def corrupted(identifier, created, data):
            put(identifier, created, data)
            key = (identifier, 'v1', 'primary')
            self.f.store.copies[key] = replace(self.f.store.copies[key], payload=b'broken')
        with patch.object(self.f.store, 'put_once', side_effect=corrupted):
            with self.assertRaises(LabFailure): self.backup()
        self.assertFalse(self.f._verified)
        self.assertFalse(self.f._completed_dates)

    def test_capture_failure_does_not_publish_and_is_audited(self):
        with patch.object(self.f.lab, 'snapshot', side_effect=TimeoutError('synthetic raw detail')):
            with self.assertRaises(LabFailure): self.backup()
        self.assertEqual(self.f.store.copies, {})
        self.assertTrue(any(e['stage']=='acquire' and e['code']=='failed' for e in self.f.audit))

    def test_audit_unavailable_blocks_before_storage(self):
        with patch.object(self.f, 'event', side_effect=OSError('audit full')):
            with self.assertRaises(OSError): self.backup()
        self.assertEqual(self.f.store.copies, {})

    def test_thirty_day_exact_boundary_and_rerun(self):
        receipt = self.backup()
        self.assertEqual(self.f.expire(NOW+timedelta(days=30)-timedelta(microseconds=1)), 0)
        self.assertEqual(self.f.expire(NOW+timedelta(days=30)), 1)
        self.assertEqual(self.f.expire(NOW+timedelta(days=30)), 0)
        self.assertEqual(self.f.store.copies, {})

    def test_all_versions_and_replicas_deleted_but_younger_backup_kept(self):
        receipt = self.backup()
        original = next(iter(self.f.store.copies.values()))
        for version, replica in (('v0', 'primary'), ('v1', 'replica'), ('v0', 'replica')):
            self.f.store.copies[(receipt.backup_id, version, replica)] = replace(original, version=version, replica=replica)
        self.f.store.revision += 1
        newer = self.backup(NOW+timedelta(days=1))
        self.assertEqual(self.f.expire(NOW+timedelta(days=30)), 4)
        self.assertEqual({c.backup_id for c in self.f.store.copies.values()}, {newer.backup_id})

    def test_incomplete_inventory_or_unknown_copy_refuses_deletion(self):
        self.backup()
        self.f.store.complete = False
        with self.assertRaises(LabFailure): self.f.expire(NOW+timedelta(days=30))
        self.f.store.complete = True
        self.f.store.copies[('unknown', 'v1', 'replica')] = Copy('unknown', 'v1', 'replica', NOW, b'opaque')
        with self.assertRaises(LabFailure): self.f.expire(NOW+timedelta(days=30))
        self.assertEqual(len(self.f.store.copies), 2)

    def test_replica_timestamp_cannot_restart_retention_clock(self):
        self.backup()
        key, original = next(iter(self.f.store.copies.items()))
        self.f.store.copies[key] = replace(original, created_at=NOW+timedelta(days=1))
        with self.assertRaises(LabFailure): self.f.expire(NOW+timedelta(days=30))
        self.assertEqual(len(self.f.store.copies), 1)

    def test_delete_denied_is_audited_and_retry_finishes(self):
        self.backup()
        with patch.object(self.f.store, 'delete_version', side_effect=PermissionError('synthetic-secret')):
            with self.assertRaises(LabFailure): self.f.expire(NOW+timedelta(days=30))
        self.assertTrue(self.f.store.copies)
        self.assertEqual(self.f.audit[-1]['code'], 'failed')
        self.assertNotIn('synthetic-secret', str(self.f.audit))
        self.assertEqual(self.f.expire(NOW+timedelta(days=30)), 1)

    def test_delete_marker_that_leaves_versions_is_failure(self):
        self.backup()
        with patch.object(self.f.store, 'delete_version', return_value=None):
            with self.assertRaises(LabFailure): self.f.expire(NOW+timedelta(days=30))
        self.assertTrue(self.f.store.copies)

    def test_partial_delete_interruption_retry_removes_remaining_replicas(self):
        receipt = self.backup()
        original = next(iter(self.f.store.copies.values()))
        self.f.store.copies[(receipt.backup_id, 'v1', 'replica')] = replace(original, replica='replica')
        delete = self.f.store.delete_version
        def interrupted(copy):
            if copy.replica == 'replica': raise InterruptedError('synthetic')
            delete(copy)
        with patch.object(self.f.store, 'delete_version', side_effect=interrupted):
            with self.assertRaises(LabFailure): self.f.expire(NOW+timedelta(days=30))
        self.assertEqual(len(self.f.store.copies), 1)
        self.assertEqual(self.f.expire(NOW+timedelta(days=30)), 1)

    def test_cross_generation_receipt_and_changed_schema_rejected(self):
        receipt = self.backup()
        sealed = self.f.store.read_primary(receipt.backup_id)
        for invalid in (replace(receipt, generation='another'), replace(receipt, schema=('changed', (), None))):
            with self.assertRaises(LabFailure): self.f._decode(invalid, sealed)

    def test_missing_independent_ledger_blocks_even_matching_backup_hash(self):
        self.seed(); receipt = self.backup()
        ledger = self.ledger(); ledger.available = False
        with self.assertRaises(LabFailure): self.restore(receipt, ledger)
        ledger.available = True; ledger.complete = False
        with self.assertRaises(LabFailure): self.restore(receipt, ledger)

    def test_unpublished_latest_change_and_old_checkpoint_rejected(self):
        self.seed(); receipt = self.backup(); ledger = self.ledger()
        old = ledger.fetch(NOW)
        ledger.note_change(NOW+timedelta(seconds=1))
        with self.assertRaises(LabFailure): ledger.validate(old, NOW+timedelta(seconds=1))
        with self.assertRaises(LabFailure): self.restore(receipt, ledger, NOW+timedelta(seconds=1))

    def test_old_export_cannot_be_relabelled_as_new_checkpoint(self):
        self.seed(); ledger = self.ledger()
        export = self.ops.retention.restore_manifest(self.admin, NOW)
        with self.assertRaisesRegex(LabFailure, 'publication_invalid'):
            ledger.publish(export, NOW+timedelta(seconds=1), complete=True)
        export['manifest']['origin'] = 'tampered'
        with self.assertRaisesRegex(LabFailure, 'publication_invalid'):
            ledger.publish(export, NOW, complete=True)

    def test_restore_cannot_use_another_operations_database(self):
        self.seed(); receipt = self.backup(); ledger = self.ledger()
        with SyntheticBackupFoundation() as other:
            foreign_ops = OperationsRepository(other.lab.source)
            with self.assertRaises(LabFailure):
                self.f.restore_memory(receipt, ledger=ledger, operations=foreign_ops, actor=self.admin, now=NOW)

    def test_real_exclusive_lock_hits_bounded_snapshot_deadline(self):
        with closing(sqlite3.connect(self.f.lab.source)) as writer:
            writer.execute('BEGIN EXCLUSIVE')
            with self.assertRaises(TimeoutError): self.f.lab.snapshot(timeout_seconds=.05)
            writer.rollback()
        self.assertFalse(self.f.lab._snapshots)
        self.assertIsNotNone(self.backup())

    def test_latest_tombstone_replayed_auth_revoked_all_users_locked(self):
        self.seed(); deleted = self.reading(self.org)
        b2c = self.reading(None); other = self.reading(self.other)
        receipt = self.backup()
        with self.ops.auth.connection() as db:
            record_deletion(db, 'scope', self.owner, self.org, [deleted], NOW)
        ledger = self.ledger()
        with closing(self.restore(receipt, ledger)) as db:
            self.assertIsNone(db.execute('SELECT id FROM readings WHERE id=?', (deleted,)).fetchone())
            for rid in (b2c, other):
                self.assertIsNotNone(db.execute('SELECT id FROM readings WHERE id=?', (rid,)).fetchone())
            self.assertEqual(db.execute('SELECT count(*) FROM auth_sessions WHERE revoked_at IS NULL').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT count(*) FROM password_reset_tokens WHERE used_at IS NULL').fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM users WHERE status!='disabled'").fetchone()[0], 0)
            self.assertEqual(db.execute('PRAGMA database_list').fetchone()[2], '')

    def test_ledger_changes_during_replay_return_no_restored_connection(self):
        self.seed(); receipt = self.backup(); ledger = self.ledger()
        replay = self.ops.retention.apply_restore_memory_fixture
        def changed(*args):
            result = replay(*args); ledger.note_change(NOW)
            return result
        with patch.object(self.ops.retention, 'apply_restore_memory_fixture', side_effect=changed):
            with self.assertRaises(LabFailure): self.restore(receipt, ledger)
        self.assertEqual(self.f.audit[-1]['code'], 'denied')

    def test_snapshot_busy_deadline_or_invalid_timeout_does_not_register(self):
        for timeout in (0, -1, 61):
            with self.assertRaises(ValueError): self.f.lab.snapshot(timeout)
        # Advance the injected monotonic clock at the first backup progress callback.
        with patch('research.backup_restore_lab.time.monotonic', side_effect=[0, 6]):
            with self.assertRaises(TimeoutError): self.f.lab.snapshot()
        self.assertEqual(self.f.lab._snapshots, {})


if __name__ == '__main__': unittest.main(verbosity=2)
