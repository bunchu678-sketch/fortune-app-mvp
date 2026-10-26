"""Offline K01/K03 JSON migration for explicitly identified LOCAL test DBs."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse
from copy import deepcopy
from contextlib import closing
from datetime import datetime, timezone
import json
import sqlite3
from history_versions import DATA_SCHEMA_VERSION
from reading_snapshot import public_result_snapshot


def check_integrity(db):
    if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise ValueError("DB integrity_check failed")
    if db.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("DB foreign_key_check failed")


def state(db):
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return {table: db.execute('SELECT * FROM "' + table.replace('"', '""') + '" ORDER BY rowid').fetchall() for table in tables}


def plan(db):
    check_integrity(db)
    columns = [r[1] for r in db.execute("PRAGMA table_info(readings)")]
    if not {"id", "result_snapshot", "data_schema_version"} <= set(columns):
        raise ValueError("Unknown readings schema")
    updates = []
    for ident, raw, version in db.execute("SELECT id,result_snapshot,data_schema_version FROM readings"):
        old = json.loads(raw)
        if not isinstance(old, dict) or version not in (1, DATA_SCHEMA_VERSION):
            raise ValueError("Unknown snapshot schema; stop without changes")
        new = public_result_snapshot(old)
        year = old.get("yearly_overall", {})
        if year.get("year") == 2026 and any(year.get(k) != new.get("yearly_overall", {}).get(k) for k in ("theme", "comment")):
            raise ValueError("2026 text differs from registered original; human review required")
        if old != new or version != DATA_SCHEMA_VERSION:
            updates.append((json.dumps(new, ensure_ascii=False, allow_nan=False, separators=(",", ":")), DATA_SCHEMA_VERSION, ident))
    return updates


def verify_unchanged(before, after, columns, updates):
    expected = deepcopy(before)
    index = {name: columns.index(name) for name in ("id", "result_snapshot", "data_schema_version")}
    targets = {ident: (raw, version) for raw, version, ident in updates}
    rows = []
    for row in expected["readings"]:
        values = list(row)
        target = targets.get(values[index["id"]])
        if target:
            values[index["result_snapshot"]], values[index["data_schema_version"]] = target
        rows.append(tuple(values))
    expected["readings"] = rows
    if after != expected:
        raise ValueError("Unexpected change to rows, IDs, relationships or retained columns")


def migrate(db_path, backup_dir=None, apply=False, test_data_confirmed=False):
    path = Path(db_path).resolve(strict=True)
    if not test_data_confirmed:
        raise ValueError("Explicit test-data confirmation required")
    db = sqlite3.connect(path.as_uri() + ("?mode=rw" if apply else "?mode=ro"), uri=True)
    try:
        db.execute("PRAGMA foreign_keys=ON")
        if apply:
            if backup_dir is None:
                raise ValueError("Repository-external backup directory required")
            folder = Path(backup_dir).resolve()
            repo = Path(__file__).resolve().parents[1]
            if folder == repo or repo in folder.parents:
                raise ValueError("Backup must be outside repository")
            db.execute("BEGIN IMMEDIATE")
        before = state(db)
        columns = [r[1] for r in db.execute("PRAGMA table_info(readings)")]
        updates = plan(db)
        backup = None
        if apply and updates:
            folder.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = folder / (path.name + ".k01-k03-" + stamp + ".sqlite3")
            if backup.exists():
                raise ValueError("Backup collision; stop")
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as origin, closing(sqlite3.connect(str(backup))) as target:
                origin.backup(target)
                target.commit()
                check_integrity(target)
                if state(target) != before:
                    raise ValueError("Backup differs from migration input")
            db.executemany("UPDATE readings SET result_snapshot=?,data_schema_version=? WHERE id=?", updates)
            check_integrity(db)
            verify_unchanged(before, state(db), columns, updates)
            if plan(db):
                raise ValueError("Migration is not idempotent")
        if apply:
            db.commit()
        return {"mode": "apply" if apply else "dry-run", "readings": len(before["readings"]), "changed": len(updates),
                "integrity": "ok", "foreign_keys": "ok", "backup": str(backup) if backup else None}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--test-data-confirmed", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    path = args.db.resolve(strict=True)
    if (root / "data").resolve() not in path.parents:
        parser.error("Only explicitly identified local data/ DBs are allowed")
    print(json.dumps(migrate(path, args.backup_dir, args.apply, args.test_data_confirmed), ensure_ascii=False))

if __name__ == "__main__":
    main()
