"""New migration risks: scale, crash/restart, mismatch and B2C/Org isolation."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contextlib import closing
import json
import secrets
import sqlite3
from threading import Event, Thread
import unittest
from research.migration_scale_lab import SyntheticMigrationLab, state, fingerprint
from operations_repository import OperationsRepository
from execution_repository import ExecutionRepository
from history_repository import HistoryError


class MigrationScaleCases(unittest.TestCase):
    def test_scale_preserves_all_legacy_rows_and_measures_elapsed_and_disk(self):
        with SyntheticMigrationLab(25000) as lab:
            with closing(lab.rollback_memory()) as db: before = state(db)
            ops, metrics = lab.migrate()
            with ops.auth.connection() as db:
                after = state(db)
                for table, rows in before.items(): self.assertEqual(after[table], rows, table)
                self.assertEqual(db.execute('SELECT count(*) FROM memberships').fetchone()[0], 0)
                self.assertEqual(db.execute('SELECT count(*) FROM reading_organization_scopes').fetchone()[0], 0)
            self.assertEqual(metrics['readings'], 25000)
            self.assertEqual(len(metrics['migration_keys']), 8)
            self.assertGreater(metrics['working_db_bytes'], 10*1024*1024)
            self.assertGreater(metrics['sampled_total_bytes'], metrics['working_db_bytes'])
            print('SYNTHETIC_MIGRATION_METRICS '+json.dumps(metrics, sort_keys=True))

    def test_actual_process_crash_rolls_back_before_safe_retry(self):
        with SyntheticMigrationLab(100) as lab:
            with closing(lab.rollback_memory()) as db: before = state(db)
            self.assertEqual(lab.crash_uncommitted_migration(), 73)
            with closing(sqlite3.connect(lab.working.source)) as db:
                self.assertEqual(state(db), before)
                self.assertFalse(db.execute("SELECT 1 FROM sqlite_master WHERE name='synthetic_uncommitted'").fetchone())
            ops, _ = lab.migrate()
            with ops.auth.connection() as db:
                for table, rows in before.items(): self.assertEqual(state(db)[table], rows)

    def test_schema_mismatch_aborts_before_ddl_or_row_change(self):
        with SyntheticMigrationLab(10) as lab:
            path = lab.prepare()
            with closing(sqlite3.connect(path)) as db:
                db.execute('ALTER TABLE users ADD COLUMN unexpected TEXT'); db.commit()
                before = (fingerprint(state(db)), db.execute('PRAGMA schema_version').fetchone()[0])
            with self.assertRaisesRegex(ValueError, 'schema mismatch'): lab.migrate()
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual((fingerprint(state(db)),db.execute('PRAGMA schema_version').fetchone()[0]),before)
                self.assertFalse(db.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone())

    def test_partial_committed_initialization_resumes_and_second_run_is_identical(self):
        from auth_service import AuthRepository
        with SyntheticMigrationLab(100) as lab:
            # A process may stop after AuthRepository committed but before B2B initialization.
            AuthRepository(lab.prepare())
            ops = OperationsRepository(lab.working.source); ExecutionRepository(ops)
            with ops.auth.connection() as db: before = fingerprint(state(db))
            again = OperationsRepository(lab.working.source); ExecutionRepository(again)
            with again.auth.connection() as db: self.assertEqual(fingerprint(state(db)), before)
            with closing(lab.rollback_memory()) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM readings').fetchone()[0],100)
                self.assertFalse(db.execute("SELECT 1 FROM sqlite_master WHERE name='organizations'").fetchone())

    def test_migrated_b2c_rows_remain_unscoped_and_cross_org_ownership_rejected(self):
        with SyntheticMigrationLab(10) as lab:
            ops, _ = lab.migrate()
            admin = ops.auth.create_user('admin@example.test', secrets.token_urlsafe(32))['id']
            ops.bootstrap(admin)
            one = ops.create_organization(admin,'合成一','one')['id']
            two = ops.create_organization(admin,'合成二','two')['id']
            ops.assign(admin,one,'synthetic-owner-one','student',True,2000)
            ops.assign(admin,two,'synthetic-owner-two','student',True,2000)
            with ops.auth.connection() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM reading_organization_scopes').fetchone()[0],0)
            with self.assertRaises(HistoryError): ops.product.resolve_context(one,'synthetic-owner-two')
            with self.assertRaises(HistoryError): ops.product.resolve_context(two,'synthetic-owner-one')
            with self.assertRaises(HistoryError): ops.product.history.detail('synthetic-owner-two','synthetic-reading-0')
            self.assertEqual(ops.product.history.detail('synthetic-owner-one','synthetic-reading-0')['id'],'synthetic-reading-0')

    def test_wal_legacy_writer_continues_and_acknowledged_commits_survive_migration(self):
        with SyntheticMigrationLab(1000) as lab:
            path = lab.prepare()
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute('PRAGMA journal_mode=WAL').fetchone()[0], 'wal')
            started = Event(); finished = Event(); errors = []; acknowledged = []
            def legacy_writer():
                try:
                    with closing(sqlite3.connect(path, timeout=5)) as db:
                        for index in range(30):
                            db.execute('INSERT INTO auth_login_attempts(ip_key,account_key,attempted_at) VALUES (?,?,?)',
                                       ('synthetic-ip', 'synthetic-account', index))
                            db.commit(); acknowledged.append(index)
                            self.assertEqual(db.execute('SELECT count(*) FROM readings').fetchone()[0], 1000)
                            started.set()
                            finished.wait(.002)
                except Exception as error:
                    errors.append(type(error).__name__); started.set()
            thread = Thread(target=legacy_writer)
            thread.start()
            try:
                self.assertTrue(started.wait(5))
                ops, _ = lab.migrate()
            finally:
                finished.set(); thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(len(acknowledged), 30)
            with ops.auth.connection() as db:
                self.assertEqual([r[0] for r in db.execute('SELECT attempted_at FROM auth_login_attempts ORDER BY attempted_at')], acknowledged)
                self.assertEqual(db.execute('SELECT count(*) FROM readings').fetchone()[0], 1000)


if __name__ == '__main__': unittest.main(verbosity=2)
