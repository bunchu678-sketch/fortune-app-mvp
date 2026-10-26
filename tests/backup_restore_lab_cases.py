"""WAL snapshots, guarded memory restore, migration and deletion consistency."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from contextlib import closing, contextmanager
from dataclasses import replace
from datetime import timedelta
import hashlib
import json
import secrets
import sqlite3
import unittest
from unittest.mock import patch

from research.backup_restore_lab import SyntheticBackupLab, inspect
from operations_repository import OperationsRepository
from auth_service import AuthError
from auth_schema import apply_migration
from history_repository import HistoryError, SQLiteHistoryRepository
from password_reset_service import PasswordResetRepository
from retention_repository import record_deletion
from billing_retention_cases import NOW


def state(db):
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {table: sorted([tuple(r) for r in db.execute('SELECT * FROM "' + table.replace('"', '""') + '"')], key=repr) for table in tables}


class BackupRestoreLabCases(unittest.TestCase):
    def setUp(self):
        self.lab = SyntheticBackupLab()
        self.addCleanup(self.lab.__exit__, None, None, None)
        self.ops = OperationsRepository(self.lab.source)

    def seed(self):
        password = secrets.token_urlsafe(32)
        self.admin = self.ops.auth.create_user('admin@example.test', password)['id']
        self.owner = self.ops.auth.create_user('owner@example.test', password)['id']
        self.ops.bootstrap(self.admin)
        self.org = self.ops.create_organization(self.admin, '合成教室', 'backup-lab')['id']
        self.ops.assign(self.admin, self.org, self.owner, 'student', True, 2000)
        self.ops.auth.login('owner@example.test', password)
        PasswordResetRepository(self.ops.auth).issue('owner@example.test', NOW.timestamp())
        self.ops.services.activate(self.admin, self.org, self.owner, NOW)

    def test_no_external_db_argument_and_environment_cannot_select_source(self):
        with self.assertRaises(TypeError):
            SyntheticBackupLab(Path('/var/lib/fortune-app/history.sqlite3'))
        with patch.dict('os.environ', {'FORTUNE_HISTORY_DB_PATH': '/var/lib/fortune-app/history.sqlite3'}):
            with SyntheticBackupLab() as other:
                self.assertNotEqual(str(other.source), '/var/lib/fortune-app/history.sqlite3')
                self.assertFalse(other.source.exists())

    def test_wal_committed_rows_captured_with_writer_connection_open(self):
        with closing(sqlite3.connect(self.lab.source)) as writer:
            self.assertEqual(writer.execute('PRAGMA journal_mode=WAL').fetchone()[0], 'wal')
            writer.execute('PRAGMA wal_autocheckpoint=0')
            writer.execute('CREATE TABLE synthetic_wal (id INTEGER PRIMARY KEY, value TEXT)')
            writer.execute("INSERT INTO synthetic_wal VALUES (1,'committed in WAL')")
            writer.commit()
            self.assertTrue(Path(str(self.lab.source) + '-wal').stat().st_size > 0)
            item = self.lab.snapshot()
            with closing(self.lab.restore_memory(item)) as restored:
                self.assertEqual(tuple(restored.execute('SELECT * FROM synthetic_wal').fetchone()), (1, 'committed in WAL'))

    def test_uncommitted_writer_rows_excluded_then_retry_captures_commit(self):
        with closing(sqlite3.connect(self.lab.source)) as writer:
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute('CREATE TABLE synthetic_pending (id INTEGER PRIMARY KEY)'); writer.commit()
            writer.execute('INSERT INTO synthetic_pending VALUES (1)')
            before = self.lab.snapshot()
            with closing(self.lab.restore_memory(before)) as restored:
                self.assertEqual(restored.execute('SELECT count(*) FROM synthetic_pending').fetchone()[0], 0)
            writer.commit()
            after = self.lab.snapshot()
            with closing(self.lab.restore_memory(after)) as restored:
                self.assertEqual(restored.execute('SELECT count(*) FROM synthetic_pending').fetchone()[0], 1)

    def test_checksum_tampering_rejected_before_restore(self):
        item = self.lab.snapshot()
        with item.path.open('ab') as stream: stream.write(b'tamper')
        with self.assertRaisesRegex(ValueError, 'checksum'): self.lab.restore_memory(item)

    def test_cross_lab_and_changed_generation_rejected(self):
        item = self.lab.snapshot()
        with SyntheticBackupLab() as other:
            with self.assertRaises(ValueError): other.restore_memory(item)
        with self.assertRaises(ValueError): self.lab.restore_memory(replace(item, generation='untrusted'))

    def test_snapshot_schema_manifest_cannot_be_substituted(self):
        item = self.lab.snapshot()
        with self.assertRaises(ValueError): self.lab.restore_memory(replace(item, schema_sha256='0' * 64))
        with self.assertRaises(ValueError): self.lab.restore_memory(replace(item, migrations=()))

    def test_failed_snapshot_is_not_registered_and_retry_is_safe(self):
        with patch('research.backup_restore_lab.inspect', side_effect=ValueError('synthetic interruption')):
            with self.assertRaises(ValueError): self.lab.snapshot()
        self.assertEqual(self.lab._snapshots, {})
        item = self.lab.snapshot()
        with closing(self.lab.restore_memory(item)) as restored: inspect(restored)

    def test_integrity_valid_database_with_invalid_foreign_keys_rejected(self):
        with closing(sqlite3.connect(self.lab.source)) as db:
            db.execute('PRAGMA foreign_keys=OFF')
            db.execute('CREATE TABLE synthetic_parent (id INTEGER PRIMARY KEY)')
            db.execute('CREATE TABLE synthetic_child (parent_id REFERENCES synthetic_parent(id))')
            db.execute('INSERT INTO synthetic_child VALUES (9)'); db.commit()
        with self.assertRaisesRegex(ValueError, 'references'): self.lab.snapshot()

    def test_legacy_additive_migration_and_memory_rollback(self):
        with SyntheticBackupLab() as legacy:
            SQLiteHistoryRepository(legacy.source)
            item = legacy.snapshot()
            with closing(legacy.restore_memory(item)) as restored: before = state(restored)
            OperationsRepository(legacy.source)
            after = legacy.snapshot()
            with closing(legacy.restore_memory(after)) as migrated:
                for table, rows in before.items(): self.assertEqual(state(migrated)[table], rows)
                self.assertTrue(after.migrations)
            OperationsRepository(legacy.source)
            self.assertEqual(legacy.snapshot().schema_sha256, after.schema_sha256)
            with closing(legacy.restore_memory(item)) as restored: self.assertEqual(state(restored), before)

    def test_migration_failure_rolls_back_ddl_marker_and_data(self):
        with self.ops.auth.connection() as db: before = state(db)
        with self.ops.auth.connection() as db:
            with self.assertRaises(sqlite3.DatabaseError):
                with db:
                    db.execute('BEGIN IMMEDIATE')
                    apply_migration(db, 'lab-deliberate-failure', ['CREATE TABLE lab_transient (id TEXT)', 'INVALID SQL'])
        with self.ops.auth.connection() as db:
            self.assertEqual(state(db), before)
            self.assertFalse(db.execute("SELECT 1 FROM sqlite_master WHERE name='lab_transient'").fetchone())

    def test_source_and_snapshot_bytes_unchanged_by_memory_restore(self):
        item = self.lab.snapshot()
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.lab.source, item.path)}
        with closing(self.lab.restore_memory(item)) as db:
            db.execute('CREATE TABLE memory_only_change (id TEXT)'); db.commit()
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before})

    def test_actual_replay_revokes_auth_locks_users_and_repeat_fails_closed(self):
        self.seed(); item = self.lab.snapshot()
        export = self.ops.retention.restore_manifest(self.admin, NOW + timedelta(days=1))
        with closing(self.lab.restore_memory(item)) as db:
            self.ops.retention.apply_restore_memory_fixture(self.admin, db, export['manifest'], export['sha256'], NOW + timedelta(days=1))
            self.assertEqual(db.execute('SELECT count(*) FROM auth_sessions WHERE revoked_at IS NULL').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT count(*) FROM password_reset_tokens WHERE used_at IS NULL').fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM users WHERE status!='disabled'").fetchone()[0], 0)
            before = state(db)
            with self.assertRaises(AuthError):
                self.ops.retention.apply_restore_memory_fixture(self.admin, db, export['manifest'], export['sha256'], NOW + timedelta(days=1))
            self.assertEqual(state(db), before)

    def reading(self, org):
        return self.ops.product.history.create(self.owner, {
            'input_snapshot': {'form': {'surname': '合成', 'givenName': '復元確認', 'birthDate': '1988-08-12', 'readingDate': '2026-10-20'}},
            'result_snapshot': {'ok': True}, 'memo': 'synthetic-only'}, ('test', 'test', 1), org)

    def test_pre_cancel_backup_replay_deletes_expired_scope_keeps_b2c(self):
        self.seed(); deleted = self.reading(self.org); kept = self.reading(None)
        item = self.lab.snapshot(); self.ops.services.cancel(self.owner, self.org, NOW)
        due = NOW + timedelta(days=60); export = self.ops.retention.restore_manifest(self.admin, due)
        with closing(self.lab.restore_memory(item)) as db:
            self.ops.retention.apply_restore_memory_fixture(self.admin, db, export['manifest'], export['sha256'], due)
            self.assertIsNone(db.execute('SELECT id FROM readings WHERE id=?', (deleted['id'],)).fetchone())
            self.assertIsNotNone(db.execute('SELECT id FROM readings WHERE id=?', (kept['id'],)).fetchone())
            inspect(db)

    def test_latest_independent_tombstone_prevents_old_reading_reappearing(self):
        self.seed(); row = self.reading(self.org); item = self.lab.snapshot()
        with closing(self.lab.restore_memory(item)) as latest:
            record_deletion(latest, 'scope', self.owner, self.org, [row['id']], NOW); latest.commit()
            @contextmanager
            def connection(): yield latest
            with patch.object(self.ops.auth, 'connection', connection):
                export = self.ops.retention.restore_manifest(self.admin, NOW + timedelta(days=1))
        with closing(self.lab.restore_memory(item)) as db:
            self.ops.retention.apply_restore_memory_fixture(self.admin, db, export['manifest'], export['sha256'], NOW + timedelta(days=1))
            self.assertIsNone(db.execute('SELECT id FROM readings WHERE id=?', (row['id'],)).fetchone())
            self.assertEqual(db.execute('SELECT count(*) FROM deletion_journal').fetchone()[0], 1)
            inspect(db)

    def test_stale_checkpoint_and_changed_contract_generation_stop_without_changes(self):
        self.seed(); item = self.lab.snapshot(); old = self.ops.retention.restore_manifest(self.admin, NOW)
        with self.ops.auth.connection() as db:
            db.execute("UPDATE service_contract_terms SET cycle_id='synthetic-new-contract-generation'")
        current = self.ops.retention.restore_manifest(self.admin, NOW + timedelta(days=1))
        with closing(self.lab.restore_memory(item)) as db:
            before = state(db)
            with self.assertRaises(HistoryError): self.ops.retention.restore_preview(self.admin, db, old['manifest'], current['sha256'], NOW + timedelta(days=1))
            with self.assertRaises(HistoryError): self.ops.retention.apply_restore_memory_fixture(self.admin, db, current['manifest'], current['sha256'], NOW + timedelta(days=1))
            self.assertEqual(state(db), before)

    def test_interrupted_retention_replay_rolls_back_auth_and_data(self):
        self.seed(); row = self.reading(self.org); item = self.lab.snapshot()
        self.ops.services.cancel(self.owner, self.org, NOW)
        due = NOW + timedelta(days=60); export = self.ops.retention.restore_manifest(self.admin, due)
        with closing(self.lab.restore_memory(item)) as db:
            before = state(db)
            with patch.object(self.ops.services, 'purge_memory_fixture', side_effect=HistoryError('synthetic interruption', 409)):
                with self.assertRaises(HistoryError): self.ops.retention.apply_restore_memory_fixture(self.admin, db, export['manifest'], export['sha256'], due)
            self.assertEqual(state(db), before)
            self.assertIsNotNone(db.execute('SELECT id FROM readings WHERE id=?', (row['id'],)).fetchone())

    def test_file_restore_and_purge_remain_rejected(self):
        self.seed(); export = self.ops.retention.restore_manifest(self.admin, NOW)
        with self.ops.auth.connection() as db:
            before = state(db)
            with self.assertRaises(HistoryError): self.ops.retention.apply_restore_memory_fixture(self.admin, db, export['manifest'], export['sha256'], NOW)
            with self.assertRaises(HistoryError): self.ops.retention.purge_user_memory_fixture(self.admin, self.owner, db, NOW)
            self.assertEqual(state(db), before)


if __name__ == '__main__': unittest.main()
