"""Owned synthetic legacy DB only; copy migration, crash recovery and sampling.

No production DB input, connection, deployment or rollback writer is provided.
Rollback verification returns a memory connection from the pre-migration snapshot.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contextlib import closing
import hashlib
import json
import sqlite3
import subprocess
from threading import Event, Thread
import time
from research.backup_restore_lab import SyntheticBackupLab, inspect
from history_repository import SQLiteHistoryRepository
from operations_repository import OperationsRepository
from execution_repository import ExecutionRepository


def state(db):
    names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {n: sorted([tuple(r) for r in db.execute('SELECT * FROM "' + n.replace('"', '""') + '"')], key=repr) for n in names}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class SyntheticMigrationLab:
    def __init__(self, rows=25000):
        if type(rows) is not int or not 1 <= rows <= 100000:
            raise ValueError('Synthetic row count must be 1..100000')
        self.legacy = SyntheticBackupLab()
        self.working = SyntheticBackupLab()
        try:
            SQLiteHistoryRepository(self.legacy.source)
            with closing(sqlite3.connect(self.legacy.source)) as db:
                # Historical B2C six-table fixture; password is deliberately not usable.
                db.executescript('''
                CREATE TABLE users (id TEXT PRIMARY KEY,email TEXT NOT NULL,
                    normalized_email TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active','disabled')),created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
                CREATE TABLE auth_sessions (token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,expires_at REAL NOT NULL,revoked_at TEXT,FOREIGN KEY(user_id) REFERENCES users(id));
                CREATE INDEX auth_sessions_user ON auth_sessions(user_id);
                CREATE TABLE auth_login_attempts (id INTEGER PRIMARY KEY,ip_key TEXT NOT NULL,account_key TEXT NOT NULL,attempted_at REAL NOT NULL);
                CREATE INDEX auth_login_ip ON auth_login_attempts(ip_key,attempted_at);
                CREATE INDEX auth_login_account ON auth_login_attempts(account_key,attempted_at);
                ''')
                self.expected_schema = inspect(db)[0]
                for owner in ('synthetic-owner-one', 'synthetic-owner-two'):
                    email = owner+'@example.test'
                    db.execute('INSERT INTO users VALUES (?,?,?,?,?,?,?)', (owner,email,email,'not-a-password-hash','active','2026-10-27','2026-10-27'))
                    db.execute('INSERT INTO persons VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                        (owner,owner,'合成','旧利用者','','','合成','旧利用者','1988-08-12','{}','2026-10-27','2026-10-27'))
                    db.execute('INSERT INTO reading_groups VALUES (?,?,?,?)', (owner,owner,owner,'2026-10-27'))
                for offset in range(0, rows, 1000):
                    values = []
                    for index in range(offset, min(offset+1000, rows)):
                        owner = 'synthetic-owner-one' if index % 2 == 0 else 'synthetic-owner-two'
                        values.append((f'synthetic-reading-{index}',owner,owner,owner,None,'2026-10-27',
                            '2026-10-27','2026-10-27',None,'synthetic '*64,'{}','{"ok":true}','legacy','legacy',1))
                    db.executemany('INSERT INTO readings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', values)
                db.commit()
                inspect(db)
            self.before = self.legacy.snapshot()
            self._prepared = False
        except Exception:
            self.__exit__(None, None, None)
            raise

    def prepare(self):
        if not self._prepared:
            if self.working.source.exists():
                raise ValueError('Synthetic working path unexpectedly exists')
            with closing(self.legacy.restore_memory(self.before)) as src, closing(sqlite3.connect(self.working.source)) as dst:
                src.backup(dst)
            self._prepared = True
        return self.working.source

    def migrate(self, *, expected_schema=None):
        path = self.prepare()
        with closing(sqlite3.connect(path)) as db:
            if inspect(db)[0] != (expected_schema or self.expected_schema):
                raise ValueError('Synthetic preflight schema mismatch; no migration attempted')
        done = Event()
        samples = []
        def sample():
            while not done.is_set():
                samples.append(sum(p.stat().st_size for root in (self.legacy.root,self.working.root)
                                   for p in root.iterdir() if p.is_file()))
                done.wait(.005)
        watcher = Thread(target=sample, daemon=True)
        watcher.start()
        start = time.perf_counter()
        try:
            ops = OperationsRepository(path)
            ExecutionRepository(ops)
        finally:
            elapsed = time.perf_counter()-start
            done.set(); watcher.join()
        with closing(sqlite3.connect(path)) as db:
            inspect(db)
            metrics = {'synthetic_only': True, 'migration_seconds': elapsed,
                       'sampled_total_bytes': max(samples, default=0),
                       'sampling_interval_seconds': .005,
                       'working_db_bytes': path.stat().st_size,
                       'readings': db.execute('SELECT count(*) FROM readings').fetchone()[0],
                       'migration_keys': [r[0] for r in db.execute('SELECT migration_key FROM schema_migrations ORDER BY migration_key')]}
        return ops, metrics

    def crash_uncommitted_migration(self):
        """Actual child abnormal exit in one open SQLite DDL/data transaction."""
        path = self.prepare()
        self.working._guard(path)
        child = '''import os,sqlite3,sys
from auth_schema import apply_migration
db=sqlite3.connect(sys.argv[1]);db.execute('BEGIN IMMEDIATE')
apply_migration(db,'synthetic-crash',['CREATE TABLE synthetic_uncommitted(id TEXT)'])
db.execute("UPDATE readings SET memo='synthetic uncommitted update'")
os._exit(73)
'''
        result = subprocess.run([sys.executable, '-B', '-c', child, str(path)],
                                cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=30)
        if result.returncode != 73:
            raise ValueError('Synthetic child did not reach intended crash')
        return result.returncode

    def rollback_memory(self):
        return self.legacy.restore_memory(self.before)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.working.__exit__(*args)
        self.legacy.__exit__(*args)
