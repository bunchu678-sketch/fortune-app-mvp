"""Org-scoped billing/retention. No invoices, mail, scheduler or persistent purge."""
from datetime import date, datetime, timedelta, timezone
from auth_schema import apply_migration
from account_lifecycle import utc
from billing_policy import (JST, MONTHLY_FEE, first_billing_date, month_end, paid_access_end,
                            suspension_retention, resume_commitment, billing_preview, arrears_preview)
from history_repository import HistoryError
from product_repository import day


def moment(value):
    return datetime.fromisoformat(value) if value else None


def stamp(value):
    return utc(value).isoformat(timespec='microseconds')


def terms(db, org, owner):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='service_contract_terms'").fetchone():
        return None
    row = db.execute("SELECT * FROM service_contract_terms WHERE organization_id=? AND user_id=?", (org, owner)).fetchone()
    return dict(row) if row else None


def effective_state(contract_state, value, now):
    if not value:
        return contract_state
    if value['purged_at']:
        return 'deleted'
    if value['access_ends_at'] and utc(now) >= moment(value['access_ends_at']):
        return 'terminated'
    if value['suspended_at'] and utc(now) >= suspension_retention(moment(value['suspended_at']))[0]:
        return 'deletion_pending'
    return contract_state


def content_visible(db, owner, reading_id, now=None):
    """Legacy/unscoped B2C rows remain unchanged. Recovery does not resume access."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='service_contract_terms'").fetchone():
        return True
    row = db.execute("SELECT organization_id FROM reading_organization_scopes WHERE owner_user_id=? AND reading_id=?", (owner, reading_id)).fetchone()
    if not row:
        return True
    value = terms(db, row[0], owner)
    if not value:
        return True
    now = utc(now)
    if value['purged_at']:
        return False
    if value['access_ends_at'] and now >= moment(value['access_ends_at']):
        return bool(value['recovered_at'])
    if value['suspended_at'] and now >= suspension_retention(moment(value['suspended_at']))[0]:
        return False
    return True


class ServiceContractRepository:
    def __init__(self, operations):
        self.operations = operations
        self.auth = operations.auth
        with self.auth.connection() as db:
            apply_migration(db, 'product-billing-retention-004', [
                """CREATE TABLE service_contract_terms (
                    organization_id TEXT NOT NULL, user_id TEXT NOT NULL,
                    activated_at TEXT, paid_through TEXT, suspended_at TEXT,
                    awaiting_initial_setup INTEGER NOT NULL DEFAULT 0 CHECK(awaiting_initial_setup IN (0,1)),
                    cancellation_requested_at TEXT, access_ends_at TEXT,
                    recovered_at TEXT, purged_at TEXT, last_reminded_at TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(organization_id,user_id),
                    FOREIGN KEY(organization_id,user_id) REFERENCES user_service_contracts(organization_id,user_id))""",
                """CREATE TABLE service_suspensions (id TEXT PRIMARY KEY, organization_id TEXT NOT NULL,
                    user_id TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT,
                    FOREIGN KEY(organization_id,user_id) REFERENCES user_service_contracts(organization_id,user_id))""",
                "CREATE UNIQUE INDEX one_open_service_suspension ON service_suspensions(organization_id,user_id) WHERE ended_at IS NULL",
            ])

    @staticmethod
    def contract(db, org, owner):
        row = db.execute("SELECT * FROM user_service_contracts WHERE organization_id=? AND user_id=?", (org, owner)).fetchone()
        if not row:
            raise HistoryError('利用契約が見つかりません。', 404)
        member = db.execute("SELECT role FROM memberships WHERE organization_id=? AND user_id=?", (org, owner)).fetchone()
        if not member or member[0] != 'student':
            raise HistoryError('生徒利用契約を確認してください。', 409)
        return dict(row)

    @staticmethod
    def ensure(db, org, owner, now):
        db.execute("""INSERT INTO service_contract_terms(organization_id,user_id,updated_at) VALUES (?,?,?)
            ON CONFLICT(organization_id,user_id) DO NOTHING""", (org, owner, stamp(now)))

    def summary(self, org, owner, now=None, *, connection=None):
        if connection is None:
            with self.auth.connection() as db:
                return self.summary(org, owner, now, connection=db)
        db = connection; now = utc(now)
        contract = self.contract(db, org, owner)
        value = terms(db, org, owner) or dict.fromkeys(['activated_at','paid_through','suspended_at',
            'cancellation_requested_at','access_ends_at','recovered_at','purged_at','last_reminded_at'])
        state = effective_state(contract['state'], value, now)
        deadline = moment(value['access_ends_at']) + timedelta(days=30) if value['access_ends_at'] else None
        pending = None
        if not deadline and value['suspended_at']:
            pending, deadline = suspension_retention(moment(value['suspended_at']))
        next_date = billing_preview(moment(value['activated_at']), state, now,
            resumed_at=moment(contract['resumed_at']), access_ends_at=moment(value['access_ends_at']),
            paid_through=date.fromisoformat(value['paid_through']) if value['paid_through'] else None)
        return {**value, 'organization_id':org, 'state':state,
                'first_billing_date':first_billing_date(moment(value['activated_at'])).isoformat() if value['activated_at'] else None,
                'next_billing_date':next_date.isoformat() if next_date else None,
                'monthly_fee':contract['monthly_fee'], 'minimum_term_until':contract['minimum_term_until'],
                'deletion_pending_at':stamp(pending) if pending else None,
                'deletion_due_at':stamp(deadline) if deadline else None,
                'deletion_hold':bool(value['recovered_at']),
                'cancellation_needs_review':bool(value['cancellation_requested_at'] and not value['access_ends_at']),
                'automatic_actions_enabled':False}

    def activate(self, actor, org, owner, now=None):
        """Explicit confirmation of actual eligibility NOW; no historical date input/backfill."""
        now = utc(now)
        with self.operations.change(actor) as db:
            contract = self.contract(db, org, owner)
            self.operations.member_access(db, org, owner)
            if db.execute('SELECT 1 FROM user_initial_setup WHERE user_id=? AND completed_at IS NULL',(owner,)).fetchone():
                raise HistoryError('本人の初回設定が未完了です。',409)
            self.ensure(db, org, owner, now)
            value = terms(db, org, owner)
            if value['activated_at']:
                return self.summary(org, owner, now, connection=db)
            if value['suspended_at'] or value['cancellation_requested_at']:
                raise HistoryError('契約状態を確認してください。', 409)
            db.execute("""UPDATE service_contract_terms SET activated_at=?,paid_through=?,updated_at=?
                WHERE organization_id=? AND user_id=?""", (stamp(now),month_end(now.astimezone(JST).date()).isoformat(),stamp(now),org,owner))
            if contract['monthly_fee'] is None:
                db.execute('UPDATE user_service_contracts SET monthly_fee=? WHERE organization_id=? AND user_id=?', (MONTHLY_FEE,org,owner))
            self.operations.audit(db,actor,'service-activate',owner,org)
            return self.summary(org,owner,now,connection=db)

    def paid_period(self, actor, org, owner, paid_through, now=None):
        now = utc(now); paid = date.fromisoformat(day(paid_through))
        if paid != month_end(paid):
            raise HistoryError('支払済み期間の末日を指定してください。',422)
        with self.operations.change(actor) as db:
            self.contract(db, org, owner); self.ensure(db, org, owner, now)
            value = terms(db,org,owner)
            if value['access_ends_at'] or (value['paid_through'] and paid_through < value['paid_through']):
                raise HistoryError('確定済み期間を変更できません。',409)
            db.execute('UPDATE service_contract_terms SET paid_through=?,updated_at=? WHERE organization_id=? AND user_id=?', (paid_through,stamp(now),org,owner))
            self.operations.audit(db,actor,'paid-period-confirm',owner,org)
            return self.summary(org,owner,now,connection=db)

    def suspend(self, actor, org, owner, now=None):
        now = utc(now)
        with self.operations.change(actor) as db:
            contract = self.contract(db,org,owner); self.ensure(db,org,owner,now)
            value = terms(db,org,owner)
            if value['cancellation_requested_at'] or contract['state']=='terminated':
                raise HistoryError('正式解約を休止に変更できません。',409)
            if not value['suspended_at']:
                from uuid import uuid4
                db.execute('INSERT INTO service_suspensions VALUES (?,?,?,?,NULL)',(str(uuid4()),org,owner,stamp(now)))
            db.execute("UPDATE user_service_contracts SET state='suspended',updated_at=? WHERE organization_id=? AND user_id=?", (stamp(now),org,owner))
            db.execute('UPDATE service_contract_terms SET suspended_at=COALESCE(suspended_at,?),updated_at=? WHERE organization_id=? AND user_id=?',(stamp(now),stamp(now),org,owner))
            self.operations.audit(db,actor,'service-suspend',owner,org)
            return self.summary(org,owner,now,connection=db)

    def resume(self, actor, org, owner, now=None):
        now = utc(now)
        with self.operations.change(actor) as db:
            contract = self.contract(db,org,owner); value = terms(db,org,owner)
            if not value or not value['suspended_at'] or value['cancellation_requested_at'] or contract['state']!='suspended':
                raise HistoryError('再開可能な休止契約がありません。',409)
            if now >= suspension_retention(moment(value['suspended_at']))[0]:
                raise HistoryError('休止後1年を経過しています。確認が必要です。',409)
            if db.execute('SELECT 1 FROM manual_dues WHERE organization_id=? AND user_id=? AND settled_at IS NULL',(org,owner)).fetchone():
                raise HistoryError('未納分の全額精算を確認してから再開してください。',409)
            db.execute("UPDATE user_service_contracts SET state='active',resumed_at=?,minimum_term_until=?,updated_at=? WHERE organization_id=? AND user_id=?",(stamp(now),stamp(resume_commitment(now)),stamp(now),org,owner))
            db.execute('UPDATE service_suspensions SET ended_at=? WHERE organization_id=? AND user_id=? AND ended_at IS NULL',(stamp(now),org,owner))
            db.execute('UPDATE service_contract_terms SET suspended_at=NULL,updated_at=? WHERE organization_id=? AND user_id=?',(stamp(now),org,owner))
            self.operations.audit(db,actor,'service-resume',owner,org)
            return self.summary(org,owner,now,connection=db)

    def cancel(self, owner, org, now=None, *, actor=None):
        """Owner request. Unknown paid-through records request only, never guesses an end."""
        now = utc(now)
        manager = self.operations.change(actor) if actor else self.auth.connection()
        with manager as db:
            if not actor: db.execute('BEGIN IMMEDIATE')
            contract = self.contract(db,org,owner); self.ensure(db,org,owner,now)
            value = terms(db,org,owner)
            if value['access_ends_at']:
                return self.summary(org,owner,now,connection=db)
            end = max(now,paid_access_end(date.fromisoformat(value['paid_through']))) if value['paid_through'] else None
            if end and contract['minimum_term_until'] and end < moment(contract['minimum_term_until']):
                raise HistoryError('再開後の最低契約期間について運営への確認が必要です。',409)
            db.execute("""UPDATE service_contract_terms SET cancellation_requested_at=COALESCE(cancellation_requested_at,?),
                access_ends_at=?,updated_at=? WHERE organization_id=? AND user_id=?""",(stamp(now),stamp(end) if end else None,stamp(now),org,owner))
            self.operations.audit(db,actor or owner,'service-cancellation-request',owner,org)
            return self.summary(org,owner,now,connection=db)

    def recover(self, owner, org, now=None, *, actor=None):
        now = utc(now)
        manager = self.operations.change(actor) if actor else self.auth.connection()
        with manager as db:
            if not actor: db.execute('BEGIN IMMEDIATE')
            self.contract(db,org,owner); value=terms(db,org,owner)
            end=moment(value['access_ends_at']) if value else None
            if not end or not (end <= now < end+timedelta(days=30)) or value['purged_at']:
                raise HistoryError('復旧可能な解約データがありません。',404)
            db.execute('UPDATE service_contract_terms SET recovered_at=?,updated_at=? WHERE organization_id=? AND user_id=?',(stamp(now),stamp(now),org,owner))
            self.operations.audit(db,actor or owner,'service-data-recover',owner,org)
            # Do not modify state, end, resumed_at, paid period, dues or global User.
            return self.summary(org,owner,now,connection=db)

    def arrears(self, actor, org, owner, now=None):
        now = utc(now)
        with self.auth.connection() as db:
            self.operations.require_admin(db,actor); self.contract(db,org,owner)
            row=db.execute('SELECT due_date,confirmed_at FROM manual_dues WHERE organization_id=? AND user_id=? AND settled_at IS NULL ORDER BY due_date LIMIT 1',(org,owner)).fetchone()
            if not row: return {'suspension_due':False,'reminder_due':False,'automatic_actions_enabled':False}
            value=terms(db,org,owner)
            result=arrears_preview(datetime.combine(date.fromisoformat(row['due_date']),datetime.min.time(),JST),moment(row['confirmed_at']),now,
                moment(value['last_reminded_at']) if value else None)
            current=self.summary(org,owner,now,connection=db)
            if current['state']!='active' or current['cancellation_requested_at']:
                result['suspension_due']=False
            return {k:stamp(v) if isinstance(v,datetime) else v for k,v in result.items()}

    def deletion_plan(self, actor, org, owner, now=None, *, connection=None):
        """Content-free dry run. Shared source dependencies fail closed; preserve accounting/User."""
        if connection is None:
            with self.auth.connection() as db:
                return self.deletion_plan(actor,org,owner,now,connection=db)
        db=connection; now=utc(now); self.operations.require_admin(db,actor)
        value=self.summary(org,owner,now,connection=db)
        deadline=moment(value['deletion_due_at'])
        eligible=bool(deadline and now>=deadline and not value['deletion_hold'] and not value['purged_at'])
        ids=[r[0] for r in db.execute('SELECT reading_id FROM reading_organization_scopes WHERE organization_id=? AND owner_user_id=?',(org,owner))]
        blockers=[]
        for rid in ids:
            for row in db.execute('SELECT id FROM readings WHERE source_reading_id=?',(rid,)):
                if row[0] not in ids: blockers.append({'reading_id':rid,'dependent_id':row[0]})
        return {'organization_id':org,'user_id':owner,'eligible':eligible,'reading_ids':ids,
                'blocked_dependencies':blockers,'can_delete':eligible and not blockers,
                'delete_user':False,'preserve_accounting':True,'automatic_actions_enabled':False}

    def purge_memory_fixture(self, actor, org, owner, db, now=None):
        """Only an isolated in-memory database can execute this verified plan. No file DB path."""
        if any(row[2] for row in db.execute('PRAGMA database_list')) or not db.execute('PRAGMA foreign_keys').fetchone()[0]:
            raise HistoryError('物理削除はin-memory検証専用です。',403)
        now=utc(now)
        with db:
            db.execute('BEGIN IMMEDIATE')
            plan=self.deletion_plan(actor,org,owner,now,connection=db)
            if not plan['can_delete']:raise HistoryError('削除対象の確認が必要です。',409)
            ids=plan['reading_ids']
            groups=set(); persons=set()
            for rid in ids:
                row=db.execute('SELECT group_id,person_id FROM readings WHERE id=? AND owner_user_id=?',(rid,owner)).fetchone()
                groups.add(row[0]); persons.add(row[1])
            # Only selected internal references are detached; references outside selection block above.
            for rid in ids:
                db.execute('UPDATE readings SET source_reading_id=NULL WHERE id=? AND owner_user_id=?',(rid,owner))
            for rid in ids:
                db.execute('DELETE FROM reading_organization_scopes WHERE reading_id=? AND owner_user_id=?',(rid,owner))
                db.execute('DELETE FROM readings WHERE id=? AND owner_user_id=?',(rid,owner))
            for gid in groups:
                db.execute('DELETE FROM reading_groups WHERE owner_user_id=? AND id=? AND NOT EXISTS(SELECT 1 FROM readings r WHERE r.group_id=reading_groups.id)',(owner,gid))
            for pid in persons:
                db.execute('DELETE FROM persons WHERE owner_user_id=? AND id=? AND NOT EXISTS(SELECT 1 FROM readings r WHERE r.person_id=persons.id) AND NOT EXISTS(SELECT 1 FROM reading_groups g WHERE g.person_id=persons.id)',(owner,pid))
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='successful_executions'").fetchone():
                db.execute('DELETE FROM successful_executions WHERE owner_user_id=? AND organization_id=?',(owner,org))
            db.execute('UPDATE service_contract_terms SET purged_at=?,updated_at=? WHERE organization_id=? AND user_id=?',(stamp(now),stamp(now),org,owner))
            self.operations.audit(db,actor,'service-data-purge-test',owner,org)
            if db.execute('PRAGMA foreign_key_check').fetchall():raise HistoryError('関連データの整合性を確認してください。',409)
            return plan


def activate_initial_contracts(db, owner, now):
    """Only newly issued marked contracts; reset of any legacy User cannot backfill dates."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='service_contract_terms'").fetchone():return
    for row in db.execute("""SELECT t.organization_id,c.monthly_fee FROM service_contract_terms t
        JOIN user_service_contracts c ON c.organization_id=t.organization_id AND c.user_id=t.user_id
        JOIN memberships m ON m.organization_id=t.organization_id AND m.user_id=t.user_id
        WHERE t.user_id=? AND t.awaiting_initial_setup=1 AND t.activated_at IS NULL
        AND t.suspended_at IS NULL AND t.cancellation_requested_at IS NULL AND c.state='active'
        AND c.initial_payment_confirmed=1 AND m.role='student'""",(owner,)).fetchall():
        db.execute("""UPDATE service_contract_terms SET activated_at=?,paid_through=?,awaiting_initial_setup=0,updated_at=?
            WHERE organization_id=? AND user_id=?""",(stamp(now),month_end(utc(now).astimezone(JST).date()).isoformat(),stamp(now),row['organization_id'],owner))
        if row['monthly_fee'] is None:
            db.execute('UPDATE user_service_contracts SET monthly_fee=? WHERE organization_id=? AND user_id=?',(MONTHLY_FEE,row['organization_id'],owner))
        # Same transaction as password completion; audit contains identifiers, no token/password.
        from operations_repository import OperationsRepository
        OperationsRepository.audit(db,owner,'service-initial-activate',owner,row['organization_id'])


def mark_activation(db, org, owner, now):
    """Atomic actual grant for a new contract, not an implicit migration/backfill."""
    ServiceContractRepository.ensure(db,org,owner,now)
    value=terms(db,org,owner)
    if value['activated_at'] or value['cancellation_requested_at'] or value['suspended_at']:return
    contract=db.execute('SELECT state,monthly_fee FROM user_service_contracts WHERE organization_id=? AND user_id=?',(org,owner)).fetchone()
    if contract['state']!='active':return
    db.execute('UPDATE service_contract_terms SET activated_at=?,paid_through=?,updated_at=? WHERE organization_id=? AND user_id=?',(stamp(now),month_end(utc(now).astimezone(JST).date()).isoformat(),stamp(now),org,owner))
    if contract['monthly_fee'] is None:
        db.execute('UPDATE user_service_contracts SET monthly_fee=? WHERE organization_id=? AND user_id=?',(MONTHLY_FEE,org,owner))
