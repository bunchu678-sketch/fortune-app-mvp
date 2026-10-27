"""Shared durable backup jobs, with strict synthetic wrappers and transport IO."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contextlib import closing
from datetime import datetime, timedelta, time as wall_time
import gzip
import json
import os
import re
from uuid import uuid4
from research.home_backup_storage import (OwnedHomeLab, JobState, ProcessLock, LabFailure,
    MAX_RAW, MAX_WIRE, instant, timestamp, slot, canonical, digest, JST, BackupSchedule)


def nothing(stage, identifier): pass


def audit_failure(state,now,error,identifier=None):
    # Adapter failure codes are fixed ASCII identifiers, never raw OS/SSH text.
    code=str(error)
    if isinstance(error,LabFailure) and re.fullmatch('[a-z_]{1,64}',code):
        state.event(now,code,identifier,alert=True)


class VPSBackupJob:
    def __init__(self, lab, *, schedule, staging_days, staging_limit_bytes, point=nothing):
        schedule=BackupSchedule.coerce(schedule)
        if type(staging_days) is not int or not 1 <= staging_days <= 7 or staging_limit_bytes<=0:
            raise LabFailure('explicit_staging_policy_required')
        self.lab = lab; self.schedule = schedule; self.staging_days = staging_days
        self.limit = staging_limit_bytes; self.point = point
        self.state = JobState(lab,'vps-state')

    def catalog(self):
        if not self.lab.link_available: raise LabFailure('transport_unavailable')
        return self.state.rows('SELECT * FROM backups ORDER BY created_at,id')

    def prefix_digest(self, row, length):
        if type(length) is not int or not 0<=length<=row['size']:
            raise LabFailure('resume_offset_refused')
        with self.lab.artifact('vps-stage',row['id']).open('rb') as stream:
            return digest(stream.read(length))

    def payload_chunks(self, row, offset):
        if type(offset) is not int or not 0<=offset<=row['size']:
            raise LabFailure('resume_offset_refused')
        path=self.lab.artifact('vps-stage',row['id'])
        if path.stat().st_size!=row['size']: raise LabFailure('staged_file_corrupt')
        with path.open('rb') as stream:
            stream.seek(offset)
            while block:=stream.read(1024):
                if not self.lab.link_available: raise LabFailure('transport_unavailable')
                yield block

    def generate(self, now):
        now = instant(now)
        with ProcessLock(self.lab,'vps-state'):
            self.state.clock(now)
            anchor=self.schedule.anchor(now)
            current_slot=slot(now,self.schedule)
            self.state.event(now,'generation_started')
            self.lab.clean_plain_snapshots()
            previous=self.state.rows('SELECT slot FROM backups ORDER BY slot DESC LIMIT 1')
            if previous and self.schedule.missing_between([previous[0]['slot'],current_slot]):
                self.state.event(now,'generation_gap',alert=True)
            rows = self.state.rows('SELECT * FROM backups WHERE slot=?',(current_slot,))
            row = rows[0] if rows else None
            if row and row['state'] in ('ready','acked'):
                path = self.lab.artifact('vps-stage',row['id'])
                if not path.is_file() or digest(path.read_bytes()) != row['sha256']:
                    self.state.event(now,'staged_backup_corrupt',row['id'],alert=True)
                    raise LabFailure('staged_backup_corrupt')
                return row
            if now-anchor>self.schedule.generation_window and not (row and self.lab.artifact('vps-stage',row['id']).exists()):
                self.state.event(now,'generation_window_missed',alert=True)
                return None
            identifier = row['id'] if row else uuid4().hex
            if row and row['state']=='deleted': raise LabFailure('generation_already_expired')
            with self.state.db() as db:
                db.execute("INSERT INTO backups(id,slot,created_at,state) VALUES (?,?,?,'pending') ON CONFLICT(id) DO NOTHING",
                           (identifier,current_slot,timestamp(now)))
            path = self.lab.artifact('vps-stage',identifier)
            try:
                if path.exists():
                    body = path.read_bytes()
                    header,_ = self.lab.open_envelope(body,'vps-key')
                    if header['id'] != identifier or header['slot'] != current_slot: raise LabFailure('staged_identity_mismatch')
                    with closing(self.lab.decode_backup(body,header,'vps-key')): pass
                else:
                    item = self.lab.source_lab.snapshot()
                    try:
                        raw = item.path.read_bytes()
                        if len(raw)>MAX_RAW: raise LabFailure('synthetic_size_limit')
                        header = {'format':1,'kind':'backup','generation':self.lab.generation,'id':identifier,
                                  'slot':current_slot,'created_at':timestamp(now),'raw_size':len(raw),
                                  'raw_sha256':digest(raw),'schema':[item.schema_sha256,item.migrations,item.origin]}
                        body = self.lab.envelope(header,gzip.compress(raw,compresslevel=6,mtime=0))
                    finally:
                        self.lab.check(item.path).unlink(missing_ok=True)
                    used = sum(p.stat().st_size for p in self.lab.path('vps-stage').iterdir() if p.is_file())
                    if used+len(body)>self.limit: raise LabFailure('staging_capacity_insufficient')
                    self.lab.write(path,body)
                    self.point('server_published',identifier)
                    with closing(self.lab.decode_backup(body,header,'vps-key')): pass
                with self.state.db() as db:
                    db.execute("UPDATE backups SET created_at=?,metadata=?,sha256=?,size=?,state='ready' WHERE id=?",
                               (header['created_at'],canonical(header).decode(),digest(body),len(body),identifier))
                self.state.event(now,'generation_verified',identifier)
                return self.state.rows('SELECT * FROM backups WHERE id=?',(identifier,))[0]
            except Exception as error:
                audit_failure(self.state,now,error,identifier)
                self.state.event(now,'generation_failed',identifier,alert=True)
                raise LabFailure('generation_failed') from None
            finally:
                self.lab.clean_plain_snapshots()

    def acknowledge(self, identifier, sha256, now):
        with self.state.db() as db:
            row = db.execute('SELECT sha256,state FROM backups WHERE id=?',(identifier,)).fetchone()
            if not row or row['sha256']!=sha256 or row['state'] not in ('ready','acked'):
                raise LabFailure('acknowledgement_mismatch')
            db.execute("UPDATE backups SET state='acked' WHERE id=?",(identifier,))
        self.state.event(now,'offsite_receipt_recorded',identifier)

    def sweep(self, now):
        """Candidate staging policy only; never erase the final staged generation."""
        now = instant(now)
        with ProcessLock(self.lab,'vps-state'):
            rows = self.state.rows("SELECT * FROM backups WHERE state IN ('ready','acked') ORDER BY created_at DESC")
            newest = None
            for candidate in rows:
                try:
                    body=self.lab.artifact('vps-stage',candidate['id']).read_bytes()
                    if digest(body)!=candidate['sha256']: raise LabFailure('staged_file_corrupt')
                    with closing(self.lab.decode_backup(body,json.loads(candidate['metadata']),'vps-key')): pass
                    newest=candidate['id']; break
                except Exception:
                    self.state.event(now,'staged_backup_corrupt',candidate['id'],alert=True)
            if rows and newest is None:
                self.state.event(now,'staging_unverified',alert=True)
                return
            for row in rows:
                age = now-datetime.fromisoformat(row['created_at'])
                if row['state']=='ready' and self.schedule.overdue(row['slot'],now):
                    self.state.event(now,'delivery_overdue',row['id'],alert=True)
                if age<timedelta(days=self.staging_days): continue
                if row['id']==newest:
                    self.state.event(now,'staging_retention_overdue',row['id'],alert=True)
                    continue
                # Metadata is retained, so a later receiver can report a missed point.
                with self.state.db() as db: db.execute("UPDATE backups SET state='delete_pending' WHERE id=?",(row['id'],))
                self.lab.artifact('vps-stage',row['id']).unlink(missing_ok=True)
                with self.state.db() as db: db.execute("UPDATE backups SET state='deleted' WHERE id=?",(row['id'],))
                self.state.event(now,'staging_deleted',row['id'])
            # Recover an interrupted staging deletion on the next sweep.
            for row in self.state.rows("SELECT * FROM backups WHERE state='delete_pending'"):
                self.lab.artifact('vps-stage',row['id']).unlink(missing_ok=True)
                with self.state.db() as db: db.execute("UPDATE backups SET state='deleted' WHERE id=?",(row['id'],))


class HomeBackupJob:
    def __init__(self, lab, server, *, schedule, point=nothing):
        schedule=BackupSchedule.coerce(schedule)
        if schedule.times!=server.schedule.times or schedule.pull_delay!=server.schedule.pull_delay:
            raise LabFailure('source_receiver_schedule_mismatch')
        self.lab = lab; self.server = server; self.schedule = schedule; self.point = point
        self.state = JobState(lab,'pc-state')

    def verify_file(self, row):
        self.lab.disk()
        body = self.lab.artifact('mock-hdd',row['id']).read_bytes()
        if len(body)!=row['size'] or digest(body)!=row['sha256']:
            raise LabFailure('received_file_corrupt')
        with closing(self.lab.decode_backup(body,json.loads(row['metadata']))): pass
        return body

    def _pull_one(self, row, now):
        self.lab.disk()
        if row['size'] is None or not 0<row['size']<=MAX_WIRE:
            raise LabFailure('wire_size_refused')
        header = json.loads(row['metadata'])
        if header['id']!=row['id'] or header['created_at']!=row['created_at'] or header['slot']!=row['slot']:
            raise LabFailure('catalog_metadata_mismatch')
        if datetime.fromisoformat(row['created_at'])>now: raise LabFailure('source_clock_future')
        target = self.lab.artifact('mock-hdd',row['id'])
        part = self.lab.artifact('mock-hdd',row['id'],'.part')
        old = self.state.rows('SELECT * FROM backups WHERE id=?',(row['id'],))
        if old and old[0]['state'] in ('deleted','delete_pending'): return False
        if old and old[0]['state']=='verified':
            # The durable receipt binds the previously AEAD-verified exact bytes.
            # Avoid re-decrypting every unchanged historical generation every day;
            # the latest usable generation is decrypted again before cleanup.
            if any(old[0][key]!=row[key] for key in ('metadata','sha256','size','created_at','slot')):
                raise LabFailure('receipt_metadata_conflict')
            body=target.read_bytes()
            if len(body)!=row['size'] or digest(body)!=row['sha256']:
                raise LabFailure('received_file_corrupt')
            if row['state']=='ready': self.server.acknowledge(row['id'],row['sha256'],now)
            return False
        with self.state.db() as db:
            db.execute("INSERT INTO backups(id,slot,created_at,metadata,sha256,size,state) VALUES (?,?,?,?,?,?,'receiving') ON CONFLICT(id) DO NOTHING",
                       tuple(row[k] for k in ('id','slot','created_at','metadata','sha256','size')))
        if not target.exists():
            if not self.lab.link_available: raise LabFailure('transport_unavailable')
            previous = part.read_bytes() if part.exists() else b''
            if len(previous)>row['size'] or (previous and self.server.prefix_digest(row,len(previous))!=digest(previous)):
                self.lab.check(part).unlink(); previous = b''
                self.state.event(now,'partial_restarted',row['id'])
            self.lab.disk(row['size']-len(previous))
            with part.open('ab') as stream, closing(self.server.payload_chunks(row,len(previous))) as blocks:
                for block in blocks:
                    if not self.lab.link_available: raise LabFailure('transport_unavailable')
                    if not block or stream.tell()+len(block)>row['size']: raise LabFailure('wire_size_refused')
                    stream.write(block); stream.flush(); os.fsync(stream.fileno())
                    with self.state.db() as db: db.execute('UPDATE backups SET offset=? WHERE id=?',(stream.tell(),row['id']))
                    self.point('transfer_chunk',row['id'])
            body = part.read_bytes()
            if len(body)!=row['size'] or digest(body)!=row['sha256']: raise LabFailure('staged_file_corrupt')
            with closing(self.lab.decode_backup(body,header)): pass
            self.lab.disk(); self.lab.check(target); os.replace(part,target)
            self.point('received_renamed',row['id'])
        self.verify_file(row)
        self.state.event(now,'receive_verified',row['id'])
        with self.state.db() as db:
            db.execute("UPDATE backups SET state='verified',offset=size WHERE id=?",(row['id'],))
        self.point('receipt_committed',row['id'])
        self.server.acknowledge(row['id'],row['sha256'],now)
        return True

    def _last_good(self, now):
        for row in self.state.rows("SELECT * FROM backups WHERE state IN ('verified','delete_pending') ORDER BY created_at DESC"):
            if row['state']=='delete_pending' and not self.lab.artifact('mock-hdd',row['id']).exists():
                continue  # Expected after a crash between unlink and journal commit.
            try:
                self.verify_file(row)
                return row
            except Exception:
                self.state.event(now,'local_backup_corrupt',row['id'],alert=True)
        return None

    def prune(self, now):
        now = instant(now); self.lab.disk()
        rows = self.state.rows('SELECT * FROM backups')
        known = {r['id']+extension for r in rows for extension in ('.enc','.part')}
        markers=getattr(self.lab,'inventory_marker_names',{'volume.json'})
        unknown = [p.name for p in self.lab.path('mock-hdd').iterdir() if p.name not in markers and p.name not in known]
        if unknown:
            self.state.event(now,'unknown_inventory',alert=True)
            return ['unknown_inventory']
        last = self._last_good(now)
        if last is None and any(r['state']!='deleted' for r in rows):
            self.state.event(now,'retention_unverified',alert=True)
            return ['retention_unverified']
        warnings = []
        for row in rows:
            if row['state']=='deleted': continue
            due = now>=datetime.fromisoformat(row['created_at'])+timedelta(days=30)
            if not due and row['state']!='delete_pending': continue
            if last and row['id']==last['id']:
                with self.state.db() as db: db.execute("UPDATE backups SET state='verified' WHERE id=?",(row['id'],))
                self.state.event(now,'retention_overdue',row['id'],alert=True)
                warnings.append('retention_overdue')
                continue
            self.state.event(now,'delete_started',row['id'])
            with self.state.db() as db: db.execute("UPDATE backups SET state='delete_pending' WHERE id=?",(row['id'],))
            self.point('delete_pending',row['id'])
            for suffix in ('.enc','.part'):
                self.lab.disk(); self.lab.artifact('mock-hdd',row['id'],suffix).unlink(missing_ok=True)
            self.point('deleted_before_record',row['id'])
            with self.state.db() as db: db.execute("UPDATE backups SET state='deleted',offset=0 WHERE id=?",(row['id'],))
            self.state.event(now,'delete_completed',row['id'])
        return warnings

    def run_daily(self, now, *, catch_up=False, attempts=3):
        """Compatibility name; persistent completion is per generation time slot."""
        return self.run_slot(now,catch_up=catch_up,attempts=attempts)

    def run_slot(self, now, *, catch_up=False, attempts=3):
        now = instant(now)
        if type(attempts) is not int or not 1<=attempts<=3: raise LabFailure('retry_limit')
        with ProcessLock(self.lab,'pc-state'):
            self.state.clock(now)
            anchor=self.schedule.anchor(now)
            before_pull=now<anchor+self.schedule.pull_delay
            before_daily=(len(self.schedule.times)==1 and anchor.date()!=now.astimezone(JST).date())
            if not catch_up and (before_pull or before_daily):
                return {'status':'not_due','received':0}
            current_slot=self.schedule.key(self.schedule.expected(now))
            current = self.state.rows('SELECT * FROM runs WHERE slot=?',(current_slot,))
            if current and current[0]['state']=='completed': return {'status':'already_completed','received':0}
            self.state.event(now,'job_started')
            with self.state.db() as db:
                db.execute("INSERT INTO runs VALUES (?,'running',NULL,1) ON CONFLICT(slot) DO UPDATE SET state='running',attempts=attempts+1",(current_slot,))
            try:
                self.lab.disk()
                catalog = self.server.catalog()
                received = 0; warnings = []
                dates=sorted({row['slot'] for row in catalog})
                if self.schedule.missing_between(dates):
                    warnings.append('generation_gap')
                existing = {r['id']:r for r in self.state.rows('SELECT * FROM backups')}
                for row in catalog:
                    if row['state']=='pending': warnings.append('generation_incomplete')
                    if row['state']=='deleted' and row['id'] not in existing and now-datetime.fromisoformat(row['created_at'])<timedelta(days=30):
                        warnings.append('staging_gap')
                    if row['state'] not in ('ready','acked'): continue
                    for attempt in range(attempts):
                        try:
                            done = self._pull_one(row,now)
                            if done and (row['id'] not in existing or existing[row['id']]['state']!='verified'): received+=1
                            break
                        except Exception as error:
                            self.state.event(now,'receive_attempt_failed',row['id'])
                            if attempt+1==attempts:
                                audit_failure(self.state,now,error,row['id'])
                                raise LabFailure('receive_failed') from None
                candidates = [r for r in catalog if r['metadata'] and r['state']!='pending']
                expected=self.schedule.expected(now)
                if not candidates or max(r['slot'] for r in candidates)<self.schedule.key(expected):
                    stale=(now>=expected+self.schedule.pull_delay+self.schedule.alert_grace
                           or bool(candidates and self.schedule.overdue(max(r['slot'] for r in candidates),now)))
                    warnings.append('generation_stale' if stale else 'generation_pending')
                last = self._last_good(now)
                if last is None or self.schedule.overdue(last['slot'],now):
                    warnings.append('offsite_backup_stale')
                warnings.extend(self.prune(now))
                for code in set(warnings): self.state.event(now,code,alert=True)
                status = 'attention' if warnings else 'completed'
                storage=self.lab.usage()
                with self.state.db() as db:
                    old=db.execute("SELECT value FROM metadata WHERE name='retained_bytes'").fetchone()
                    storage['retained_delta_bytes']=storage['ciphertext_bytes']-(int(old[0]) if old else 0)
                    db.execute("INSERT INTO metadata VALUES ('retained_bytes',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",
                               (str(storage['ciphertext_bytes']),))
                self.state.event(now,'job_attention' if warnings else 'job_completed')
                with self.state.db() as db:
                    db.execute('UPDATE runs SET state=?,last_code=? WHERE slot=?',(status,','.join(sorted(set(warnings))),current_slot))
                return {'status':status,'received':received,'warnings':sorted(set(warnings)),'storage':storage}
            except Exception as error:
                audit_failure(self.state,now,error)
                self.state.event(now,'job_failed',alert=True)
                with self.state.db() as db: db.execute("UPDATE runs SET state='failed',last_code='job_failed' WHERE slot=?",(current_slot,))
                raise LabFailure('job_failed') from None


class SyntheticVPS(VPSBackupJob):
    """Original synthetic boundary remains strict; real adapters use another class."""
    def __init__(self, lab, **kwargs):
        if not isinstance(lab,OwnedHomeLab): raise LabFailure('explicit_synthetic_schedule_required')
        super().__init__(lab,**kwargs)


class SyntheticHomeJob(HomeBackupJob):
    def __init__(self, lab, server, **kwargs):
        if not isinstance(lab,OwnedHomeLab) or not isinstance(server,SyntheticVPS) or server.lab.root!=lab.root:
            raise LabFailure('only_owned_mock_transport_allowed')
        super().__init__(lab,server,**kwargs)
