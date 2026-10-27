"""Durable encrypted ledger replication and fail-closed memory-only restore.

truth/ is an independent-authority TEST ORACLE, not a deployed trust service.
It models the information a real recovery operator must independently prove.
Application change hooks, authenticated transport and that production authority
are intentionally absent; loss of latestness proof always blocks restore.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime
import json
from research.backup_foundation_lab import LatestLedgerMock
from research.home_backup_storage import (JobState, ProcessLock, LabFailure, instant, timestamp, canonical, digest)
from research.home_backup_jobs import nothing


class DurableLedgerMock:
    def __init__(self, lab, *, point=nothing):
        self.lab = lab; self.point = point
        self.state = JobState(lab,'pc-state')
        for role in ('vps-state','pc-state'):
            path = lab.path(role,'ledger')
            if not path.exists(): path.mkdir()

    def truth(self):
        if not self.lab.truth_available: raise LabFailure('latest_authority_unavailable')
        path = self.lab.path('truth','latest.json')
        if not path.is_file(): raise LabFailure('latest_authority_missing')
        return json.loads(path.read_bytes())

    def note_change(self, now):
        with ProcessLock(self.lab,'vps-state'):
            return self._note_change(now)

    def _note_change(self, now):
        now = instant(now)
        old = self.truth() if self.lab.path('truth','latest.json').exists() else None
        if old and (not old['complete'] or datetime.fromisoformat(old['watermark'])>now):
            raise LabFailure('prior_ledger_change_unpublished')
        revision = old['revision']+1 if old else 1
        value = {'revision':revision,'watermark':timestamp(now),'complete':False,
                 'previous':old['chain'] if old else '0'*64}
        self.lab.write(self.lab.path('truth','latest.json'),canonical(value),replace=True)
        return revision

    def _file(self, role, revision):
        if type(revision) is not int or not 1<=revision<=100000:
            raise LabFailure('ledger_revision_refused')
        return self.lab.path(role,'ledger',f'ledger-{revision:08d}.enc')

    def publish(self, export, revision, now):
        with ProcessLock(self.lab,'vps-state'):
            return self._publish(export,revision,now)

    def _publish(self, export, revision, now):
        truth = self.truth()
        if truth['revision']!=revision or truth['watermark']!=timestamp(now) or truth['complete']:
            raise LabFailure('ledger_publication_order')
        # Reuse all existing timestamp/content checks; a hash is not a freshness proof.
        verifier = LatestLedgerMock()
        verifier.note_change(now); verifier.publish(export,now,complete=True)
        header = {'format':1,'kind':'ledger','generation':self.lab.generation,'revision':revision,
                  'watermark':timestamp(now),'export_sha256':export['sha256'],'previous':truth['previous']}
        chain = digest(canonical(header))
        header['chain'] = chain
        body = self.lab.envelope(header,canonical(export))
        self.lab.write(self._file('vps-state',revision),body,replace=True)
        self.point('ledger_published',None)
        self.lab.write(self.lab.path('truth','latest.json'),canonical({**truth,'complete':True,
                       'chain':chain,'export_sha256':export['sha256']}),replace=True)
        return revision

    def _head(self):
        rows = {r['name']:r['value'] for r in self.state.rows("SELECT * FROM metadata WHERE name IN ('ledger_revision','ledger_chain')")}
        return int(rows.get('ledger_revision',0)),rows.get('ledger_chain','0'*64)

    def sync(self, now):
        now = instant(now)
        with ProcessLock(self.lab,'pc-state'):
            truth = self.truth()
            if not truth['complete']: raise LabFailure('ledger_incomplete')
            last, previous = self._head()
            if last>truth['revision']: raise LabFailure('ledger_rollback')
            for revision in range(last+1,truth['revision']+1):
                if not self.lab.link_available: raise LabFailure('ledger_transport_unavailable')
                target = self._file('pc-state',revision)
                source = self._file('vps-state',revision)
                if not source.is_file(): raise LabFailure('ledger_revision_missing')
                body = source.read_bytes()
                header, clear = self.lab.open_envelope(body)
                export = json.loads(clear)
                unsigned = {key:value for key,value in header.items() if key!='chain'}
                if (header.get('kind')!='ledger' or header['revision']!=revision or header['previous']!=previous
                        or header['chain']!=digest(canonical(unsigned))
                        or export['sha256']!=header['export_sha256']
                        or datetime.fromisoformat(header['watermark'])>now):
                    raise LabFailure('ledger_chain_invalid')
                check = LatestLedgerMock()
                moment = datetime.fromisoformat(header['watermark'])
                check.note_change(moment); check.publish(export,moment,complete=True)
                self.lab.write(target,body)
                self.point('ledger_received',None)
                with self.state.db() as db:
                    for name,value in (('ledger_revision',str(revision)),('ledger_chain',header['chain'])):
                        db.execute('INSERT INTO metadata VALUES (?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value',(name,value))
                previous = header['chain']
            if previous!=truth['chain'] or self.truth()!=truth: raise LabFailure('ledger_changed_during_sync')
            self.state.event(now,'ledger_sync_verified')
            return truth['revision']

    def approved(self, now):
        truth = self.truth()
        last, chain = self._head()
        if not truth['complete'] or last!=truth['revision'] or chain!=truth['chain']:
            raise LabFailure('latest_ledger_unproven')
        path = self._file('pc-state',last)
        if not path.is_file(): raise LabFailure('independent_ledger_missing')
        header, clear = self.lab.open_envelope(path.read_bytes())
        export = json.loads(clear)
        if (header.get('kind')!='ledger' or header['revision']!=last or header['chain']!=chain
                or header['export_sha256']!=truth['export_sha256'] or header['watermark']!=truth['watermark']):
            raise LabFailure('independent_ledger_mismatch')
        verifier = LatestLedgerMock()
        moment = datetime.fromisoformat(header['watermark'])
        verifier.note_change(moment); verifier.publish(export,moment,complete=True)
        checkpoint = verifier.fetch(now)
        return truth,verifier,checkpoint

    def restore_memory(self, job, identifier, operations, actor, now):
        now = instant(now)
        db = None
        try:
            if operations.auth.path.resolve()!=self.lab.source_lab.source:
                raise LabFailure('foreign_operations_database')
            with ProcessLock(self.lab,'pc-state'):
                truth,verifier,checkpoint = self.approved(now)
                rows = job.state.rows("SELECT * FROM backups WHERE id=? AND state='verified'",(identifier,))
                if not rows: raise LabFailure('backup_not_verified')
                row = rows[0]
                body = job.verify_file(row)
                db = self.lab.decode_backup(body,json.loads(row['metadata']))
                if self.truth()!=truth: raise LabFailure('ledger_changed_during_restore')
                export = checkpoint.export
                operations.retention.apply_restore_memory_fixture(actor,db,export['manifest'],export['sha256'],now)
                self.point('restore_replayed',identifier)
                verifier.validate(checkpoint,now)
                if self.truth()!=truth: raise LabFailure('ledger_changed_during_restore')
                self.state.event(now,'restore_offline_locked',identifier)
                return db
        except Exception:
            if db is not None: db.close()
            self.state.event(now,'restore_denied',identifier,alert=True)
            raise LabFailure('restore_denied') from None
