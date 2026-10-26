"""Synthetic-only SQLite backup laboratory; no external DB input or file restore.

Every source and snapshot is newly allocated by this instance. Restore returns
an in-memory connection only. This is neither an encrypted backup service nor
a trusted latest-checkpoint provider, and is not a production restore command.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contextlib import closing
from dataclasses import dataclass
import hashlib
import json
import sqlite3
import tempfile
from uuid import uuid4


@dataclass(frozen=True)
class Snapshot:
    path: Path
    generation: str
    sha256: str
    schema_sha256: str
    migrations: tuple
    origin: str | None


def inspect(db):
    if [tuple(r) for r in db.execute('PRAGMA integrity_check')] != [('ok',)]:
        raise ValueError('Synthetic snapshot integrity failed')
    if db.execute('PRAGMA foreign_key_check').fetchall():
        raise ValueError('Synthetic snapshot references failed')
    schema = [tuple(r) for r in db.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    migrations = tuple(r[0] for r in db.execute('SELECT migration_key FROM schema_migrations ORDER BY migration_key')) if 'schema_migrations' in tables else ()
    origin = db.execute('SELECT id FROM retention_origin').fetchone()[0] if 'retention_origin' in tables else None
    schema_hash = hashlib.sha256(json.dumps([schema, db.execute('PRAGMA user_version').fetchone()[0]], ensure_ascii=False).encode()).hexdigest()
    return schema_hash, migrations, origin


class SyntheticBackupLab:
    def __init__(self):
        # No path argument and no FORTUNE_HISTORY_DB_PATH: a real DB cannot be selected.
        self._temp = tempfile.TemporaryDirectory(prefix='fortune-synthetic-backup-')
        self.root = Path(self._temp.name).resolve()
        self._source = self.root / 'new-synthetic-source.sqlite3'
        self._generation = uuid4().hex
        self._snapshots = {}

    @property
    def source(self):
        return self._source

    def _guard(self, path):
        if path.is_symlink() or path.resolve().parent != self.root or self.root.is_symlink():
            raise ValueError('Only this newly allocated synthetic laboratory is allowed')

    def snapshot(self):
        self._guard(self.source)
        if not self.source.is_file():
            raise ValueError('Create the synthetic source first')
        target = self.root / ('snapshot-' + uuid4().hex + '.sqlite3')
        # Reserve a new name; never overwrite a prior snapshot or source.
        with target.open('xb'):
            pass
        with closing(sqlite3.connect(self.source.as_uri() + '?mode=ro', uri=True)) as src, closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
            dst.commit()
            schema, migrations, origin = inspect(dst)
        item = Snapshot(target, self._generation, hashlib.sha256(target.read_bytes()).hexdigest(), schema, migrations, origin)
        self._snapshots[target.name] = item
        return item

    def restore_memory(self, item):
        if not isinstance(item, Snapshot) or self._snapshots.get(item.path.name) != item or item.generation != self._generation:
            raise ValueError('Unknown synthetic snapshot or generation')
        self._guard(item.path)
        if hashlib.sha256(item.path.read_bytes()).hexdigest() != item.sha256:
            raise ValueError('Snapshot checksum differs')
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with closing(sqlite3.connect(item.path.as_uri() + '?mode=ro', uri=True)) as src:
                if inspect(src) != (item.schema_sha256, item.migrations, item.origin):
                    raise ValueError('Snapshot schema, migrations or origin differs')
                src.backup(db)
            inspect(db)
            return db
        except Exception:
            db.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        # Only disposable paths allocated by TemporaryDirectory are cleaned up.
        self._temp.cleanup()


def main():
    if sys.argv[1:]:
        raise SystemExit('This synthetic laboratory accepts no DB path or other arguments')
    from operations_repository import OperationsRepository
    with SyntheticBackupLab() as lab:
        OperationsRepository(lab.source)
        item = lab.snapshot()
        with closing(lab.restore_memory(item)) as db:
            inspect(db)
        print(json.dumps({'synthetic_only': True, 'integrity': 'ok', 'foreign_keys': 'ok',
                          'restore_target': ':memory:', 'file_restore_enabled': False}))


if __name__ == '__main__':
    main()
