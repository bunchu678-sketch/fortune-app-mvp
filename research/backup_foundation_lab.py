"""Synthetic-only orchestration; no production paths, timer, storage or restore CLI.

Acquisition reuses SyntheticBackupLab. Encryption is an isolated standard-library
probe using disposable keys. Object versions, replicas, audit, scheduler and the
independent latest ledger are memory-only mocks, not production integrations.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import base64
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, time as wall_time, timedelta, timezone
import hashlib
import json
import secrets
import sqlite3
import subprocess
from threading import RLock
from typing import Protocol
from uuid import uuid4
from research.backup_restore_lab import SyntheticBackupLab, inspect

JST = timezone(timedelta(hours=9))
RETENTION = timedelta(days=30)


class LabFailure(Exception):
    """Only fixed failure codes, never raw adapter/credential details."""


def instant(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise LabFailure('timezone_required')
    return value.astimezone(timezone.utc)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


class Sealer(Protocol):
    def seal(self, data: bytes, aad: bytes) -> bytes: ...
    def open(self, data: bytes, aad: bytes) -> bytes: ...


class SyntheticNodeAEAD:
    """Candidate evaluation only. Key is generated here, never accepted/persisted.

    Explicit executable selection avoids changing installed Node or app settings.
    Keys travel through a private subprocess pipe, never arguments or logs.
    """
    def __init__(self, executable):
        self._executable = str(executable)
        self._key = secrets.token_bytes(32)

    def _run(self, operation, data, aad):
        if len(data) > 64 * 1024 * 1024 or len(aad) > 16384:
            raise LabFailure('synthetic_probe_size_limit')
        request = {'syntheticOnly': True, 'operation': operation,
                   'key': base64.b64encode(self._key).decode(),
                   'data': base64.b64encode(data).decode(), 'aad': base64.b64encode(aad).decode()}
        try:
            result = subprocess.run([self._executable, str(Path(__file__).with_name('backup_crypto_probe.cjs'))],
                                    input=canonical(request), capture_output=True, timeout=15, check=False)
            if result.returncode:
                raise LabFailure('crypto_unavailable_or_authentication_failed')
            return base64.b64decode(result.stdout, validate=True)
        except Exception:
            raise LabFailure('crypto_unavailable_or_authentication_failed') from None

    def seal(self, data, aad):
        return self._run('seal', data, aad)

    def open(self, data, aad):
        return self._run('open', data, aad)


@dataclass(frozen=True)
class Copy:
    backup_id: str
    version: str
    replica: str
    created_at: datetime
    payload: bytes = field(repr=False)


class ObjectStore(Protocol):
    def put_once(self, backup_id: str, created_at: datetime, payload: bytes) -> None: ...
    def read_primary(self, backup_id: str) -> bytes: ...
    def inventory(self) -> tuple: ...
    def delete_version(self, copy: Copy) -> None: ...


class MemoryObjectStore:
    """No local/cloud file access. Models versions, replicas and incomplete listing."""
    def __init__(self):
        self.copies = {}
        self.complete = True
        self.revision = 0

    def put_once(self, backup_id, created_at, payload):
        key = (backup_id, 'v1', 'primary')
        expected = Copy(backup_id, 'v1', 'primary', created_at, payload)
        if key in self.copies:
            if self.copies[key] != expected:
                raise LabFailure('object_conflict')
            return
        self.copies[key] = expected
        self.revision += 1

    def read_primary(self, backup_id):
        return self.copies[(backup_id, 'v1', 'primary')].payload

    def inventory(self):
        if not self.complete:
            raise LabFailure('inventory_incomplete')
        return self.revision, tuple(self.copies.values())

    def delete_version(self, copy):
        key = (copy.backup_id, copy.version, copy.replica)
        current = self.copies.get(key)
        if current is not None and current != copy:
            raise LabFailure('version_changed')
        if current is not None:
            del self.copies[key]
            self.revision += 1


@dataclass(frozen=True)
class Receipt:
    backup_id: str
    generation: str
    created_at: datetime
    schema: tuple
    plaintext_sha256: str
    ciphertext_sha256: str
    aad: bytes = field(repr=False)


@dataclass(frozen=True)
class Checkpoint:
    revision: int
    fetched_at: datetime
    covered_through: datetime
    export: dict = field(repr=False, compare=False)


class LatestLedgerMock:
    """Independent synthetic authority, NOT an authenticated production provider.

    The authority tracks changes even when publication fails. A matching hash or
    caller-supplied timestamp cannot bypass the authority's latest high watermark.
    """
    def __init__(self):
        self.available = True
        self.complete = False
        self._revision = 0
        self._changed_at = None
        self._covered_through = None
        self._export = None

    def note_change(self, now):
        now = instant(now)
        if self._changed_at is not None and now < self._changed_at:
            raise LabFailure('ledger_clock_reversed')
        self._changed_at = now
        self._revision += 1

    def publish(self, export, covered_through, *, complete):
        covered_through = instant(covered_through)
        try:
            exported_at = instant(datetime.fromisoformat(export['manifest']['exported_at']))
            if (exported_at != covered_through or digest(canonical(export['manifest'])) != export['sha256']
                    or (self._covered_through is not None and covered_through < self._covered_through)):
                raise ValueError()
        except Exception:
            raise LabFailure('ledger_publication_invalid') from None
        self._export = json.loads(canonical(export))
        self._covered_through = covered_through
        self.complete = complete is True
        self._revision += 1

    def fetch(self, now):
        if not self.available or not self.complete or self._export is None:
            raise LabFailure('latest_ledger_unavailable')
        cp = Checkpoint(self._revision, instant(now), self._covered_through,
                        json.loads(canonical(self._export)))
        self.validate(cp, now)
        return cp

    def validate(self, cp, now):
        now = instant(now)
        if (not self.available or not self.complete or cp.revision != self._revision
                or self._changed_at is None or cp.covered_through < self._changed_at
                or cp.covered_through > cp.fetched_at or cp.fetched_at > now
                or cp.covered_through != self._covered_through
                or canonical(cp.export) != canonical(self._export)):
            raise LabFailure('latest_ledger_unproven')


class SyntheticBackupFoundation:
    """Explicitly called lab only. Restart loses scheduler/audit/mock storage/key.

    No automatic production fallback, environment DB lookup, file restore,
    account reopening, journal purge or application import exists.
    """
    def __init__(self, *, sealer=None, schedule=None):
        if schedule is not None and (not isinstance(schedule, wall_time) or schedule.tzinfo is not None):
            raise LabFailure('explicit_jst_schedule_required')
        self.lab = SyntheticBackupLab()
        self.generation = uuid4().hex
        self.sealer = sealer
        self.store = MemoryObjectStore()
        self.schedule = schedule
        self.audit = []
        self._verified = {}
        self._pending = {}
        self._completed_dates = set()
        self._last_now = None
        self._lock = RLock()

    def event(self, stage, code, backup_id=None):
        self.audit.append({'stage': stage, 'code': code, 'backup_id': backup_id,
                           'recorded_at': datetime.now(timezone.utc).isoformat()})

    def _capture(self, now):
        if self.sealer is None:
            raise LabFailure('encryption_not_configured')
        item = self.lab.snapshot()
        with closing(self.lab.restore_memory(item)) as db:
            # Serialize an in-memory SQLite backup; no decrypted file is written.
            db.execute('PRAGMA journal_mode=MEMORY')
            payload = db.serialize()
            schema = inspect(db)
        backup_id = uuid4().hex
        aad = canonical({'format': 1, 'generation': self.generation,
                         'backup_id': backup_id, 'created_at': now.isoformat(),
                         'schema': schema, 'sha256': digest(payload)})
        sealed = self.sealer.seal(payload, aad)
        return Receipt(backup_id, self.generation, now, schema, digest(payload), digest(sealed), aad), sealed

    def _decode(self, receipt, sealed):
        if receipt.generation != self.generation or digest(sealed) != receipt.ciphertext_sha256:
            raise LabFailure('backup_generation_or_hash_mismatch')
        plaintext = self.sealer.open(sealed, receipt.aad)
        if digest(plaintext) != receipt.plaintext_sha256:
            raise LabFailure('plaintext_hash_mismatch')
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        try:
            db.deserialize(plaintext)
            db.execute('PRAGMA foreign_keys=ON')
            if inspect(db) != receipt.schema:
                raise LabFailure('schema_mismatch')
            return db
        except Exception:
            db.close()
            raise

    def run_due(self, now, *, attempts=3):
        now = instant(now)
        if type(attempts) is not int or not 1 <= attempts <= 3:
            raise LabFailure('retry_limit')
        with self._lock:
            if self.schedule is None:
                raise LabFailure('schedule_not_decided')
            if self._last_now is not None and now < self._last_now:
                raise LabFailure('clock_reversed')
            self._last_now = now
            local = now.astimezone(JST)
            slot = local.date().isoformat()
            if local.time().replace(tzinfo=None) < self.schedule or slot in self._completed_dates:
                return None
            self.event('acquire', 'started')
            if slot not in self._pending:
                try:
                    self._pending[slot] = self._capture(now)
                except Exception:
                    self.event('acquire', 'failed')
                    raise LabFailure('acquisition_or_encryption_failed') from None
            receipt, sealed = self._pending[slot]
            for attempt in range(attempts):
                self.event('store', 'attempt', receipt.backup_id)
                try:
                    self.store.put_once(receipt.backup_id, receipt.created_at, sealed)
                    self.event('verify', 'started', receipt.backup_id)
                    with closing(self._decode(receipt, self.store.read_primary(receipt.backup_id))):
                        pass
                    self.event('verify', 'succeeded', receipt.backup_id)
                    self._verified[receipt.backup_id] = receipt
                    self._completed_dates.add(slot)
                    del self._pending[slot]
                    return receipt
                except Exception:
                    self.event('store_or_verify', 'failed', receipt.backup_id)
            raise LabFailure('backup_not_verified') from None

    def retention_plan(self, now):
        now = instant(now)
        revision, copies = self.store.inventory()
        # Creation time comes from the original receipt, not replication time.
        due = []
        for copy in copies:
            receipt = self._verified.get(copy.backup_id)
            if receipt is None or copy.created_at != receipt.created_at or copy.created_at > now:
                raise LabFailure('unreconciled_inventory')
            if now >= receipt.created_at + RETENTION:
                due.append(copy)
        return revision, tuple(due)

    def expire(self, now):
        with self._lock:
            try:
                self.event('retention', 'started')
                revision, due = self.retention_plan(now)
                if self.store.inventory()[0] != revision:
                    raise LabFailure('inventory_changed')
                for copy in due:
                    self.event('delete_version', 'started', copy.backup_id)
                    self.store.delete_version(copy)
                _, remaining = self.store.inventory()
                expired_ids = {copy.backup_id for copy in due}
                if any(copy.backup_id in expired_ids for copy in remaining):
                    raise LabFailure('copies_remain')
                self.event('retention', 'succeeded')
                return len(due)
            except Exception:
                self.event('retention', 'failed')
                raise LabFailure('retention_incomplete') from None

    def restore_memory(self, receipt, *, ledger, operations, actor, now):
        now = instant(now)
        db = None
        try:
            self.event('restore', 'started', receipt.backup_id)
            if operations.auth.path.resolve() != self.lab.source.resolve():
                raise LabFailure('only_owned_synthetic_operations_allowed')
            if self._verified.get(receipt.backup_id) != receipt or now < receipt.created_at:
                raise LabFailure('unverified_backup')
            checkpoint = ledger.fetch(now)
            db = self._decode(receipt, self.store.read_primary(receipt.backup_id))
            ledger.validate(checkpoint, now)
            export = checkpoint.export
            operations.retention.apply_restore_memory_fixture(actor, db, export['manifest'], export['sha256'], now)
            # Re-check latestness after replay, before exposing even this offline fixture.
            ledger.validate(checkpoint, now)
            inspect(db)
            self.event('restore', 'offline_locked', receipt.backup_id)
            return db
        except Exception:
            if db is not None:
                db.close()
            self.event('restore', 'denied', receipt.backup_id)
            raise LabFailure('restore_not_authorized') from None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.lab.__exit__(*args)
