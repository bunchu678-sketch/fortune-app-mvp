"""Owned synthetic disk fixtures, durable private job state and existing AEAD.

There is deliberately no production path/SSH/HDD/key configuration interface.
All roles live in a fresh SyntheticBackupLab; separate directories model roles,
not independent physical devices or a production trust provider.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import base64
from contextlib import closing, contextmanager
from datetime import datetime, time as wall_time, timedelta
import gzip
from io import BytesIO
import json
import os
import re
import secrets
import shutil
import sqlite3
from uuid import uuid4
from research.backup_foundation_lab import (SyntheticNodeAEAD, LabFailure, instant, canonical, digest, JST)
from research.backup_restore_lab import SyntheticBackupLab, inspect

MAX_RAW = 64*1024*1024
MAX_WIRE = 96*1024*1024


def timestamp(now):
    return instant(now).isoformat()


class BackupSchedule:
    """Explicit JST generation slots; delayed pulls share the generation key.

    A missed generation window is never backfilled. Its eventual copy would
    contain current data, so representing it as a past recovery point is false.
    """
    def __init__(self, times, *, pull_delay=timedelta(0), generation_window=timedelta(minutes=30),
                 alert_grace=timedelta(minutes=15)):
        times=tuple(times)
        if (not 1<=len(times)<=4 or any(not isinstance(t,wall_time) or t.tzinfo is not None
                or t.second or t.microsecond for t in times)
                or times!=tuple(sorted(set(times)))):
            raise LabFailure('explicit_synthetic_schedule_required')
        intervals=[(datetime.combine(datetime.min.date(),right)-datetime.combine(datetime.min.date(),left)).total_seconds()%86400
                   for left,right in zip(times,times[1:]+times[:1])]
        shortest=min(value or 86400 for value in intervals)
        if any(not isinstance(value,timedelta) or value.total_seconds()<0
               for value in (pull_delay,generation_window,alert_grace)):
            raise LabFailure('schedule_interval_invalid')
        if not 0<generation_window.total_seconds()<shortest or (pull_delay+alert_grace).total_seconds()>=shortest:
            raise LabFailure('schedule_interval_invalid')
        self.times=times; self.pull_delay=pull_delay
        self.generation_window=generation_window; self.alert_grace=alert_grace

    @classmethod
    def coerce(cls, value):
        if isinstance(value,cls): return value
        if isinstance(value,wall_time): return cls((value,))  # Existing daily fixtures.
        raise LabFailure('explicit_synthetic_schedule_required')

    @classmethod
    def parse(cls, text, delay_minutes):
        if not re.fullmatch(r'\d{2}:\d{2}(,\d{2}:\d{2}){0,3}',text) or type(delay_minutes) is not int:
            raise LabFailure('explicit_synthetic_schedule_required')
        try: times=tuple(wall_time.fromisoformat(value) for value in text.split(','))
        except ValueError: raise LabFailure('explicit_synthetic_schedule_required') from None
        return cls(times,pull_delay=timedelta(minutes=delay_minutes))

    def anchor(self, now):
        local=instant(now).astimezone(JST)
        candidates=[datetime.combine(local.date(),t,JST) for t in self.times]
        return max((t for t in candidates if t<=local),default=datetime.combine(local.date()-timedelta(days=1),self.times[-1],JST))

    def key(self, anchor):
        local=instant(anchor).astimezone(JST)
        if local.time().replace(tzinfo=None) not in self.times:
            raise LabFailure('slot_not_in_schedule')
        return local.isoformat(timespec='minutes')

    def previous(self, anchor): return self.anchor(anchor-timedelta(microseconds=1))

    def next(self, anchor):
        index=self.times.index(anchor.astimezone(JST).time().replace(tzinfo=None))
        day=anchor.astimezone(JST).date()
        return datetime.combine(day if index+1<len(self.times) else day+timedelta(days=1),
                                self.times[(index+1)%len(self.times)],JST)

    def expected(self, now):
        anchor=self.anchor(now)
        return anchor if instant(now)>=anchor+self.pull_delay else self.previous(anchor)

    def missing_between(self, keys):
        anchors=sorted(datetime.fromisoformat(key) for key in set(keys))
        return any(self.next(left)<right for left,right in zip(anchors,anchors[1:]))

    def overdue(self, key, now):
        anchor=datetime.fromisoformat(key)
        return instant(now)>=self.next(anchor)+self.pull_delay+self.alert_grace


def slot(now, schedule):
    return BackupSchedule.coerce(schedule).key(BackupSchedule.coerce(schedule).anchor(now))


class OwnedHomeLab:
    def __init__(self, node_executable):
        self.source_lab = SyntheticBackupLab()
        self.root = self.source_lab.root
        self.generation = uuid4().hex
        self.node = str(node_executable)
        self._owner = True
        self.disk_available = True
        self.disk_free_bytes = None  # An explicit synthetic capacity fault, never a real HDD.
        self.link_available = True
        self.truth_available = True
        for role in ('vps-stage','vps-state','pc-state','mock-hdd','vps-key','pc-key','offline-key','truth'):
            self.path(role).mkdir()
        self.write(self.path('lab.json'), canonical({'synthetic_only':True,'generation':self.generation,'node':self.node}))
        self.write(self.path('mock-hdd','volume.json'),canonical({'synthetic_volume':self.generation}))
        key = secrets.token_bytes(32)
        for role in ('vps-key','pc-key','offline-key'):
            self.write(self.path(role,'synthetic.key'),key)

    @classmethod
    def attach_for_test(cls, root, generation):
        root = Path(root)
        if not root.name.startswith('fortune-synthetic-backup-') or root.is_symlink() or root.is_junction():
            raise LabFailure('not_owned_synthetic_lab')
        marker = json.loads((root/'lab.json').read_bytes())
        if marker.get('synthetic_only') is not True or marker.get('generation') != generation:
            raise LabFailure('not_owned_synthetic_lab')
        obj = object.__new__(cls)
        obj.root = root.resolve(); obj.generation = generation; obj.node = marker['node']; obj._owner = False
        obj.disk_available = obj.link_available = obj.truth_available = True
        obj.disk_free_bytes = None
        obj.source_lab = object.__new__(SyntheticBackupLab)
        obj.source_lab.root = obj.root
        obj.source_lab._source = obj.root/'new-synthetic-source.sqlite3'
        obj.source_lab._generation = generation
        obj.source_lab._snapshots = {}
        return obj

    def check(self, path):
        path = Path(path)
        if path != self.root and self.root not in path.parents:
            raise LabFailure('outside_synthetic_lab')
        cursor = path
        while True:
            if cursor.is_symlink() or cursor.is_junction():
                raise LabFailure('reparse_path_refused')
            if cursor == self.root: break
            cursor = cursor.parent
        if path.resolve() != path:
            raise LabFailure('outside_synthetic_lab')
        return path

    def path(self, *parts):
        return self.check(self.root.joinpath(*parts))

    def artifact(self, role, identifier, suffix='.enc'):
        if not re.fullmatch('[0-9a-f]{32}',identifier) or suffix not in ('.enc','.part'):
            raise LabFailure('artifact_name_refused')
        return self.path(role,identifier+suffix)

    def write(self, path, data, *, replace=False):
        path = self.check(path)
        if path.exists() and not replace:
            if path.read_bytes() == data: return
            raise LabFailure('immutable_file_conflict')
        temporary = self.check(path.with_name(path.name+'.writing'))
        if temporary.exists(): temporary.unlink()  # Only this owned atomic-write name.
        try:
            with temporary.open('xb') as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            self.check(path)
            os.replace(temporary,path)
        finally:
            if temporary.exists(): temporary.unlink()

    def disk(self, required=0):
        if not self.disk_available:
            raise LabFailure('hdd_unavailable')
        marker = self.path('mock-hdd','volume.json')
        if not marker.is_file() or json.loads(marker.read_bytes()) != {'synthetic_volume':self.generation}:
            raise LabFailure('hdd_identity_mismatch')
        available=self.disk_free_bytes if self.disk_free_bytes is not None else shutil.disk_usage(marker.parent).free
        if available < required:
            raise LabFailure('hdd_capacity_insufficient')
        return self.path('mock-hdd')

    def usage(self):
        """Only this newly allocated mock volume; never enumerates real HDDs."""
        volume=self.disk()
        return {'ciphertext_bytes':sum(self.check(p).stat().st_size for p in volume.glob('*.enc')),
                'partial_bytes':sum(self.check(p).stat().st_size for p in volume.glob('*.part')),
                'stage_bytes':sum(self.check(p).stat().st_size for p in self.path('vps-stage').glob('*.enc')),
                'mock_host_free_bytes':shutil.disk_usage(volume).free,
                'injected_free_bytes':self.disk_free_bytes}

    def cipher(self, role):
        if role not in ('vps-key','pc-key'): raise LabFailure('key_role_refused')
        try:
            key = self.path(role,'synthetic.key').read_bytes()
            if len(key) != 32: raise ValueError()
        except Exception:
            raise LabFailure('synthetic_key_unavailable') from None
        # Reuse the existing standard Node AES-GCM implementation unchanged.
        cipher = SyntheticNodeAEAD(self.node)
        cipher._key = key
        return cipher

    def recover_synthetic_pc_key(self):
        key = self.path('offline-key','synthetic.key').read_bytes()
        if len(key) != 32: raise LabFailure('recovery_key_unavailable')
        self.write(self.path('pc-key','synthetic.key'),key,replace=True)

    def envelope(self, header, payload, role='vps-key'):
        encrypted = self.cipher(role).seal(payload,canonical(header))
        return canonical({'header':header,'ciphertext':base64.b64encode(encrypted).decode()})

    def open_envelope(self, body, role='pc-key'):
        try:
            if len(body)>MAX_WIRE: raise ValueError()
            value = json.loads(body)
            header = value['header']
            if header['generation'] != self.generation or header['format'] != 1:
                raise ValueError()
            clear = self.cipher(role).open(base64.b64decode(value['ciphertext'],validate=True),canonical(header))
            return header,clear
        except Exception:
            raise LabFailure('envelope_authentication_failed') from None

    def decode_backup(self, body, expected=None, role='pc-key'):
        header, packed = self.open_envelope(body,role)
        if header.get('kind') != 'backup' or (expected is not None and canonical(header) != canonical(expected)):
            raise LabFailure('backup_metadata_mismatch')
        if type(header.get('raw_size')) is not int or not 0 < header['raw_size'] <= MAX_RAW:
            raise LabFailure('backup_size_refused')
        with gzip.GzipFile(fileobj=BytesIO(packed)) as stream:
            raw = stream.read(header['raw_size']+1)
        if len(raw) != header['raw_size'] or digest(raw) != header['raw_sha256']:
            raise LabFailure('backup_content_mismatch')
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        try:
            db.deserialize(raw); db.execute('PRAGMA foreign_keys=ON')
            if canonical(inspect(db)) != canonical(header['schema']):
                raise LabFailure('backup_schema_mismatch')
            return db
        except Exception:
            db.close(); raise

    def clean_plain_snapshots(self):
        for path in self.root.glob('snapshot-*.sqlite3'):
            if not re.fullmatch('snapshot-[0-9a-f]{32}\\.sqlite3',path.name):
                raise LabFailure('unexpected_plain_snapshot')
            self.check(path).unlink()

    def __enter__(self): return self

    def __exit__(self,*args):
        if self._owner: self.source_lab.__exit__(*args)


class JobState:
    """New private control schema, completely separate from application schema."""
    def __init__(self, lab, role):
        if role not in ('vps-state','pc-state'): raise LabFailure('state_role_refused')
        self.lab = lab
        self.path = lab.path(role,'synthetic-jobs.sqlite3')
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS backups (
                    id TEXT PRIMARY KEY, slot TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
                    metadata TEXT, sha256 TEXT, size INTEGER, state TEXT NOT NULL, offset INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS runs (slot TEXT PRIMARY KEY, state TEXT NOT NULL, last_code TEXT, attempts INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, at TEXT NOT NULL, code TEXT NOT NULL, backup_id TEXT);
                CREATE TABLE IF NOT EXISTS outbox (code TEXT PRIMARY KEY, last_seen TEXT NOT NULL, occurrences INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')

    @contextmanager
    def db(self):
        self.lab.check(self.path)
        with closing(sqlite3.connect(self.path,timeout=2)) as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA synchronous=FULL')
            with db: yield db

    def rows(self, sql, args=()):
        with self.db() as db: return [dict(r) for r in db.execute(sql,args)]

    def event(self, now, code, identifier=None, *, alert=False):
        if not re.fullmatch('[a-z_]+',code): raise LabFailure('audit_code_refused')
        with self.db() as db:
            db.execute('INSERT INTO events(at,code,backup_id) VALUES (?,?,?)',(timestamp(now),code,identifier))
            if alert:
                db.execute('INSERT INTO outbox VALUES (?,?,1) ON CONFLICT(code) DO UPDATE SET last_seen=excluded.last_seen,occurrences=occurrences+1',(code,timestamp(now)))

    def clock(self, now):
        now = instant(now)
        with self.db() as db:
            old = db.execute("SELECT value FROM metadata WHERE name='last_clock'").fetchone()
            if old and now < datetime.fromisoformat(old[0]): raise LabFailure('clock_reversed')
            db.execute("INSERT INTO metadata VALUES ('last_clock',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",(timestamp(now),))


class ProcessLock:
    """OS releases this lock on actual process exit; no stale PID/lease bypass."""
    def __init__(self, lab, role):
        self.lab = lab; self.path = lab.path(role,'job.lock'); self.stream = None

    def __enter__(self):
        self.lab.check(self.path)
        stream = self.path.open('a+b')
        try:
            if self.path.stat().st_size == 0:
                stream.write(b'0'); stream.flush()
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.stream = stream
            return self
        except OSError:
            stream.close()
            raise LabFailure('job_already_running') from None

    def __exit__(self,*args):
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(self.stream,fcntl.LOCK_UN)
        finally:
            self.stream.close()
