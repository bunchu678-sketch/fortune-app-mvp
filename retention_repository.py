"""Independent purchase evidence, retention review and memory-only deletion verification.
No file database purge, scheduler, mail or billing execution is exposed.
"""
from contextlib import nullcontext
from datetime import date, timedelta
import hashlib
import json
from uuid import uuid4
from auth_schema import apply_migration
from auth_service import normalized_email, token_hash
from billing_policy import JST, MONTHLY_FEE, month_end, resume_commitment
from history_repository import HistoryError
from product_repository import text, day
from service_contract_repository import stamp, moment, terms
from account_lifecycle import utc

ARCHIVE_TABLES = ('service_contract_terms','service_suspensions','manual_dues',
                  'user_service_contracts','memberships','management_audit')
AUTH_TABLES = ('auth_sessions','password_reset_tokens','user_account_lifecycle',
               'user_activity','user_initial_setup','user_profiles','b2c_retention_status')
KNOWN_USER_REFERENCES = set(ARCHIVE_TABLES + AUTH_TABLES + ('operating_administrator',
    'reading_organization_scopes','successful_executions','purchase_links'))


def tables(db):
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def memory_only(db):
    if any(row[2] for row in db.execute('PRAGMA database_list')) or not db.execute('PRAGMA foreign_keys').fetchone()[0]:
        raise HistoryError('物理削除・復元適用はin-memory検証専用です。',403)


def record_deletion(db, kind, owner, org, reading_ids, now):
    if 'deletion_journal' not in tables(db):
        raise HistoryError('削除履歴の準備が必要です。',409)
    db.execute('INSERT INTO deletion_journal VALUES (?,?,?,?,?,?,?,?)',
        (str(uuid4()),kind,owner,org,json.dumps(sorted(reading_ids)),stamp(now),
         stamp(utc(now)+timedelta(days=30)),'review_pending'))


class RetentionRepository:
    def __init__(self, operations):
        self.operations=operations; self.auth=operations.auth
        with self.auth.connection() as db:
            apply_migration(db,'product-final-retention-005',[
                """CREATE TABLE purchase_proofs (purchase_number TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL REFERENCES organizations(id), purchased_on TEXT NOT NULL,
                    payment_confirmed INTEGER NOT NULL CHECK(payment_confirmed=1),
                    purchaser_digest TEXT NOT NULL, review_on TEXT NOT NULL, created_at TEXT NOT NULL,
                    retention_basis TEXT NOT NULL)""",
                """CREATE TABLE purchase_links (purchase_number TEXT PRIMARY KEY REFERENCES purchase_proofs(purchase_number),
                    user_id TEXT REFERENCES users(id) ON DELETE SET NULL, linked_at TEXT NOT NULL)""",
                """CREATE TABLE b2c_retention_status (user_id TEXT PRIMARY KEY REFERENCES users(id),
                    state TEXT NOT NULL CHECK(state IN ('active','inactive')), confirmed_at TEXT NOT NULL)""",
                """CREATE TABLE retained_records (id TEXT PRIMARY KEY, record_kind TEXT NOT NULL,
                    record_key TEXT NOT NULL, organization_id TEXT, former_user_id TEXT NOT NULL,
                    record_json TEXT NOT NULL, archived_at TEXT NOT NULL,
                    review_on TEXT NOT NULL, retention_basis TEXT NOT NULL)""",
                """CREATE TABLE deletion_journal (id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('scope','user')),
                    former_user_id TEXT NOT NULL, organization_id TEXT, reading_ids_json TEXT NOT NULL,
                    deleted_at TEXT NOT NULL, review_after TEXT NOT NULL, review_state TEXT NOT NULL)""",
                "CREATE TABLE retention_origin (singleton INTEGER PRIMARY KEY CHECK(singleton=1), id TEXT NOT NULL)",
                "INSERT INTO retention_origin VALUES (1,'"+str(uuid4())+"')",
                "ALTER TABLE service_contract_terms ADD COLUMN cycle_id TEXT",
            ])

    def confirm_b2c(self, actor, owner, state):
        if state not in ('active','inactive'):raise HistoryError('B2C利用状況を確認してください。',422)
        with self.operations.change(actor) as db:
            if not db.execute('SELECT 1 FROM users WHERE id=?',(owner,)).fetchone():raise HistoryError('利用者が見つかりません。',404)
            db.execute('INSERT INTO b2c_retention_status VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET state=excluded.state,confirmed_at=excluded.confirmed_at',(owner,state,stamp(None)))
            self.operations.audit(db,actor,'b2c-retention-confirm',owner)

    def register_purchase(self, actor, number, org, purchased_on, email, payment_confirmed, review_on, owner=None):
        number=text(number,100)
        if '/' in number or '\\' in number:raise HistoryError('購入番号にパス区切りは使用できません。',422)
        purchased_on=day(purchased_on); review_on=day(review_on)
        if payment_confirmed is not True or not purchased_on or not review_on or review_on<=utc(None).astimezone(JST).date().isoformat():
            raise HistoryError('入金・購入日・将来の保持見直し日を確認してください。',422)
        if purchased_on>utc(None).astimezone(JST).date().isoformat():raise HistoryError('将来の購入日は指定できません。',422)
        digest=token_hash(normalized_email(email))
        with self.operations.change(actor) as db:
            self.operations.product.organization(db,org)
            if db.execute('SELECT 1 FROM purchase_proofs WHERE purchase_number=?',(number,)).fetchone():raise HistoryError('購入番号は登録済みです。',409)
            if owner:
                row=db.execute('SELECT normalized_email FROM users WHERE id=?',(owner,)).fetchone()
                contract=db.execute('SELECT initial_payment_confirmed FROM user_service_contracts WHERE organization_id=? AND user_id=?',(org,owner)).fetchone()
                if not row or token_hash(row[0])!=digest or not contract or not contract[0]:raise HistoryError('購入者と確認済み契約を確認してください。',409)
            db.execute('INSERT INTO purchase_proofs VALUES (?,?,?,1,?,?,?,?)',(number,org,purchased_on,digest,review_on,stamp(None),'same_product_recontract_proof'))
            if owner:db.execute('INSERT INTO purchase_links VALUES (?,?,?)',(number,owner,stamp(None)))
            self.operations.audit(db,actor,'purchase-proof-register',number,org)
        return {'purchase_number':number,'organization_id':org,'review_on':review_on}

    def purchases(self, actor):
        with self.auth.connection() as db:
            self.operations.require_admin(db,actor)
            return [dict(r) for r in db.execute('SELECT p.purchase_number,p.organization_id,p.purchased_on,p.payment_confirmed,p.review_on,p.retention_basis,l.user_id FROM purchase_proofs p LEFT JOIN purchase_links l USING(purchase_number) ORDER BY p.purchased_on DESC')]

    def recontract(self, actor, number, org, email, display_name, identity_verified, monthly_payment_confirmed, paid_through, now=None):
        """Manual proof + identity check. Never reconstruct deleted fortunes or waive another product."""
        now=utc(now); normalized=normalized_email(email); paid=day(paid_through)
        if identity_verified is not True or monthly_payment_confirmed is not True:
            raise HistoryError('購入証明・本人確認・月額入金の手動確認が必要です。',422)
        if not paid or date.fromisoformat(paid)!=month_end(date.fromisoformat(paid)) or date.fromisoformat(paid)<now.astimezone(JST).date():
            raise HistoryError('確認済みの支払期間末日を指定してください。',422)
        with self.operations.change(actor) as db:
            proof=db.execute('SELECT * FROM purchase_proofs WHERE purchase_number=?',(number,)).fetchone()
            if not proof or proof['organization_id']!=org or proof['purchaser_digest']!=token_hash(normalized):
                raise HistoryError('この商品の購入証明と本人確認情報を確認してください。',409)
            row=db.execute('SELECT id,status FROM users WHERE normalized_email=?',(normalized,)).fetchone()
            link=db.execute('SELECT user_id FROM purchase_links WHERE purchase_number=?',(number,)).fetchone()
            if link and link[0] and (not row or row['id']!=link[0]):raise HistoryError('購入証明は別の利用者に紐付いています。',409)
            if row:
                owner=row['id']
                lifecycle=db.execute('SELECT state FROM user_account_lifecycle WHERE user_id=?',(owner,)).fetchone()
                if row['status']!='active' or (lifecycle and lifecycle[0]!='active'):raise HistoryError('User本体の状態を先に確認してください。',409)
                pending=db.execute('SELECT 1 FROM user_initial_setup WHERE user_id=? AND completed_at IS NULL',(owner,)).fetchone()
                if pending:raise HistoryError('初回設定を完了してください。',409)
                old=terms(db,org,owner)
                contract=db.execute('SELECT state,monthly_fee FROM user_service_contracts WHERE organization_id=? AND user_id=?',(org,owner)).fetchone()
                if old and old['access_ends_at'] and now<moment(old['access_ends_at']):raise HistoryError('支払済み利用期間が終了していません。',409)
                if contract and not (old and (old['access_ends_at'] or old['suspended_at'] or old['purged_at'])):raise HistoryError('継続中の利用契約です。',409)
                if db.execute('SELECT 1 FROM manual_dues WHERE organization_id=? AND user_id=? AND settled_at IS NULL',(org,owner)).fetchone():raise HistoryError('未納分の全額精算が必要です。',409)
                for table in ('service_contract_terms','user_service_contracts'):
                    self.archive(db,table,owner,now,org)
                if not db.execute('SELECT 1 FROM memberships WHERE organization_id=? AND user_id=?',(org,owner)).fetchone():self.operations.product.add_membership(org,owner,'student',connection=db)
                if db.execute('SELECT role FROM memberships WHERE organization_id=? AND user_id=?',(org,owner)).fetchone()[0]!='student':raise HistoryError('所属区分を確認してください。',409)
                self.operations.membership(db,org,owner,'student',True,contract['monthly_fee'] if contract and contract['monthly_fee'] is not None else MONTHLY_FEE)
                self.operations.services.ensure(db,org,owner,now)
                db.execute('UPDATE service_contract_terms SET activated_at=?,awaiting_initial_setup=0 WHERE organization_id=? AND user_id=?',(stamp(now),org,owner))
                result={'id':owner,'setup_pending':False}
            else:
                result=self.operations.issue_account(actor,org,email,display_name,True,MONTHLY_FEE,connection=db);owner=result['id']
            db.execute("UPDATE user_service_contracts SET state='active',resumed_at=?,minimum_term_until=?,updated_at=? WHERE organization_id=? AND user_id=?",(stamp(now),stamp(resume_commitment(now)),stamp(now),org,owner))
            db.execute('UPDATE service_suspensions SET ended_at=COALESCE(ended_at,?) WHERE organization_id=? AND user_id=?',(stamp(now),org,owner))
            db.execute('UPDATE service_contract_terms SET paid_through=?,suspended_at=NULL,cancellation_requested_at=NULL,access_ends_at=NULL,recovered_at=NULL,purged_at=NULL,last_reminded_at=NULL,cycle_id=?,updated_at=? WHERE organization_id=? AND user_id=?',(paid,str(uuid4()),stamp(now),org,owner))
            db.execute('INSERT INTO purchase_links VALUES (?,?,?) ON CONFLICT(purchase_number) DO UPDATE SET user_id=excluded.user_id,linked_at=excluded.linked_at',(number,owner,stamp(now)))
            self.operations.audit(db,actor,'purchase-recontract',number,org)
            return {**result,'initial_fee_required':False,'deleted_history_restorable':False,'mail_delivery':'disabled'}

    @staticmethod
    def archive(db, table, owner, now, org=None):
        if table not in ARCHIVE_TABLES:raise ValueError('Unsupported archive table')
        column='actor_user_id' if table=='management_audit' else 'user_id'
        sql='SELECT * FROM '+table+' WHERE '+column+'=?';args=[owner]
        if org:sql+=' AND organization_id=?';args.append(org)
        for row in db.execute(sql,args).fetchall():
            value=dict(row)
            # C/D identifiers and already recorded amounts/dates only; no auth/profile/reading content.
            if db.execute('SELECT 1 FROM retained_records WHERE record_kind=? AND former_user_id=? AND record_json=?',(table,owner,json.dumps(value,sort_keys=True))).fetchone():continue
            db.execute('INSERT INTO retained_records VALUES (?,?,?,?,?,?,?,?,?)',
                (str(uuid4()),table,value.get('id') or value.get('organization_id'),value.get('organization_id'),owner,
                 json.dumps(value,sort_keys=True),stamp(now),utc(now).astimezone(JST).date().isoformat(),'review_pending'))

    def user_plan(self, actor, owner, now=None, *, connection=None):
        if connection is None:
            with self.auth.connection() as db:return self.user_plan(actor,owner,now,connection=db)
        db=connection;now=utc(now);self.operations.require_admin(db,actor)
        if not db.execute('SELECT 1 FROM users WHERE id=?',(owner,)).fetchone():raise HistoryError('利用者が見つかりません。',404)
        blockers=[]
        if db.execute('SELECT 1 FROM operating_administrator WHERE user_id=?',(owner,)).fetchone():blockers.append('operating_administrator')
        b2c=db.execute('SELECT state FROM b2c_retention_status WHERE user_id=?',(owner,)).fetchone()
        if not b2c or b2c[0]!='inactive':blockers.append('b2c_active_or_unknown')
        if db.execute('SELECT 1 FROM readings r WHERE owner_user_id=? AND NOT EXISTS(SELECT 1 FROM reading_organization_scopes s WHERE s.reading_id=r.id)',(owner,)).fetchone():blockers.append('b2c_readings')
        if 'successful_executions' in tables(db) and db.execute('SELECT 1 FROM successful_executions WHERE owner_user_id=? AND organization_id IS NULL',(owner,)).fetchone():blockers.append('b2c_execution_records')
        plans=[]
        members=db.execute('SELECT organization_id,role FROM memberships WHERE user_id=?',(owner,)).fetchall()
        if not members:blockers.append('no_verified_contract_history')
        for member in members:
            if member['role']!='student':blockers.append('non_student_membership');continue
            try:
                plan=self.operations.services.deletion_plan(actor,member['organization_id'],owner,now,connection=db)
                value=terms(db,member['organization_id'],owner)
                if not plan['can_delete'] and not (value and value['purged_at'] and not plan['reading_ids']):blockers.append('contract_not_expired_or_dependency')
                plans.append(plan)
            except HistoryError:blockers.append('unknown_contract')
        for table in tables(db):
            for fk in db.execute('PRAGMA foreign_key_list("'+table.replace('"','""')+'")'):
                if fk[2]=='users' and table not in KNOWN_USER_REFERENCES:blockers.append('unknown_user_reference:'+table)
        return {'user_id':owner,'can_delete':not blockers,'blockers':sorted(set(blockers)),
                'organization_plans':plans,'preserve_contract_and_accounting':True,'automatic_actions_enabled':False}

    def purge_user_memory_fixture(self, actor, owner, db, now=None):
        memory_only(db);now=utc(now);nested=db.in_transaction
        with nullcontext() if nested else db:
            if not nested:db.execute('BEGIN IMMEDIATE')
            plan=self.user_plan(actor,owner,now,connection=db)
            if not plan['can_delete']:raise HistoryError('User削除対象の確認が必要です。',409)
            for scope in plan['organization_plans']:
                if scope['can_delete']:self.operations.services.purge_memory_fixture(actor,scope['organization_id'],owner,db,now)
            record_deletion(db,'user',owner,None,[],now)
            self.remove_user_records(db,owner,now)
            self.operations.audit(db,actor,'user-purge-test',owner)
            if db.execute('PRAGMA foreign_key_check').fetchall():raise HistoryError('関連データの整合性を確認してください。',409)
            return plan

    def remove_user_records(self, db, owner, now):
        memory_only(db)
        # Used only after an authorized plan or an authoritative restore tombstone. Preserve C/D before unlinking.
        if db.execute('SELECT 1 FROM readings WHERE owner_user_id=?',(owner,)).fetchone():raise HistoryError('未処理の鑑定データがあります。',409)
        email=db.execute('SELECT normalized_email FROM users WHERE id=?',(owner,)).fetchone()
        for table in ARCHIVE_TABLES:
            self.archive(db,table,owner,now)
            column='actor_user_id' if table=='management_audit' else 'user_id'
            db.execute('DELETE FROM '+table+' WHERE '+column+'=?',(owner,))
        for table in AUTH_TABLES:
            if table in tables(db):db.execute('DELETE FROM '+table+' WHERE user_id=?',(owner,))
        if email:
            for table in ('auth_login_attempts','password_reset_attempts'):
                if table in tables(db):db.execute('DELETE FROM '+table+' WHERE account_key=?',(token_hash(email[0]),))
        if 'successful_executions' in tables(db):db.execute('DELETE FROM successful_executions WHERE owner_user_id=?',(owner,))
        db.execute('DELETE FROM reading_groups WHERE owner_user_id=?',(owner,));db.execute('DELETE FROM persons WHERE owner_user_id=?',(owner,))
        db.execute('DELETE FROM users WHERE id=?',(owner,))

    def restore_manifest(self, actor, now=None):
        """Export under one snapshot. Store fresh digest separately in authenticated off-VPS custody."""
        with self.auth.connection() as db:
            db.execute('BEGIN');self.operations.require_admin(db,actor)
            scopes=[]
            for row in db.execute('SELECT * FROM service_contract_terms ORDER BY organization_id,user_id'):
                value=self.operations.services.summary(row['organization_id'],row['user_id'],now,connection=db)
                contract_state=db.execute('SELECT state FROM user_service_contracts WHERE organization_id=? AND user_id=?',(row['organization_id'],row['user_id'])).fetchone()[0]
                scopes.append({'contract_state':contract_state,**{k:value.get(k) for k in ('organization_id','user_id','suspended_at','cancellation_requested_at','access_ends_at','recovered_at','purged_at','cycle_id','deletion_due_at')}})
            value={'format':1,'origin':db.execute('SELECT id FROM retention_origin').fetchone()[0],
                   'exported_at':stamp(now),'scopes':scopes,
                   'deletions':[dict(r) for r in db.execute('SELECT * FROM deletion_journal ORDER BY deleted_at,id')],
                   'purchase_proofs':[dict(r) for r in db.execute('SELECT * FROM purchase_proofs ORDER BY purchase_number')],
                   'retained_records':[dict(r) for r in db.execute('SELECT * FROM retained_records ORDER BY id')]}
            encoded=json.dumps(value,sort_keys=True,separators=(',',':'))
            return {'manifest':value,'sha256':hashlib.sha256(encoded.encode()).hexdigest()}

    def restore_preview(self, actor, db, manifest, trusted_sha256, now=None):
        self.operations.require_admin(db,actor);now=utc(now)
        encoded=json.dumps(manifest,sort_keys=True,separators=(',',':'))
        if manifest.get('format')!=1 or not trusted_sha256 or hashlib.sha256(encoded.encode()).hexdigest()!=trusted_sha256:
            raise HistoryError('最新の外部保管済み削除情報を検証できません。',409)
        if manifest.get('origin')!=db.execute('SELECT id FROM retention_origin').fetchone()[0] or moment(manifest['exported_at'])>now:
            raise HistoryError('復元元・取得日時を確認してください。',409)
        # A fresh external checkpoint is mandatory. A digest from the same old backup is insufficient.
        for scope in manifest['scopes']:
            old=terms(db,scope['organization_id'],scope['user_id'])
            if not old or old.get('cycle_id')!=scope['cycle_id']:
                raise HistoryError('再契約・新規契約を最新の契約記録と照合してください。',409)
        due=[s for s in manifest['scopes'] if s['deletion_due_at'] and now>=moment(s['deletion_due_at'])]
        return {'expired_scopes':due,'deletions':manifest['deletions'],'automatic_actions_enabled':False}

    def apply_restore_memory_fixture(self, actor, db, manifest, trusted_sha256, now=None):
        memory_only(db);now=utc(now)
        with db:
            db.execute('BEGIN IMMEDIATE')
            preview=self.restore_preview(actor,db,manifest,trusted_sha256,now)
            # Restore access stays locked until current contract/identity records have been reconciled.
            db.execute('UPDATE auth_sessions SET revoked_at=COALESCE(revoked_at,?)',(stamp(now),))
            db.execute('UPDATE password_reset_tokens SET used_at=COALESCE(used_at,?)',(stamp(now),))
            for scope in manifest['scopes']:
                db.execute('UPDATE user_service_contracts SET state=? WHERE organization_id=? AND user_id=?',(scope['contract_state'],scope['organization_id'],scope['user_id']))
                fields=('suspended_at','cancellation_requested_at','access_ends_at','recovered_at','purged_at')
                db.execute('UPDATE service_contract_terms SET '+','.join(k+'=?' for k in fields)+' WHERE organization_id=? AND user_id=?',tuple(scope[k] for k in fields)+(scope['organization_id'],scope['user_id']))
            for scope in preview['expired_scopes']:
                # A tombstone may already mark purged; recompute deletion against the restored rows.
                db.execute('UPDATE service_contract_terms SET purged_at=NULL WHERE organization_id=? AND user_id=?',(scope['organization_id'],scope['user_id']))
                self.operations.services.purge_memory_fixture(actor,scope['organization_id'],scope['user_id'],db,now)
            for proof in manifest['purchase_proofs']:
                old=db.execute('SELECT * FROM purchase_proofs WHERE purchase_number=?',(proof['purchase_number'],)).fetchone()
                if old and any(old[k]!=proof[k] for k in ('organization_id','purchased_on','payment_confirmed','purchaser_digest')):raise HistoryError('購入証明の不一致を確認してください。',409)
                db.execute('INSERT INTO purchase_proofs VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(purchase_number) DO UPDATE SET review_on=excluded.review_on,retention_basis=excluded.retention_basis',tuple(proof[k] for k in ('purchase_number','organization_id','purchased_on','payment_confirmed','purchaser_digest','review_on','created_at','retention_basis')))
            for record in manifest['retained_records']:
                db.execute('INSERT OR IGNORE INTO retained_records VALUES (?,?,?,?,?,?,?,?,?)',tuple(record[k] for k in ('id','record_kind','record_key','organization_id','former_user_id','record_json','archived_at','review_on','retention_basis')))
            for event in sorted(preview['deletions'],key=lambda e:(e['kind']=='user',e['deleted_at'],e['id'])):
                ids=json.loads(event['reading_ids_json']);owner=event['former_user_id']
                groups=set();persons=set()
                for rid in ids:
                    row=db.execute('SELECT group_id,person_id FROM readings WHERE id=? AND owner_user_id=?',(rid,owner)).fetchone()
                    if row:groups.add(row[0]);persons.add(row[1])
                    db.execute('UPDATE readings SET source_reading_id=NULL WHERE id=? AND owner_user_id=?',(rid,owner))
                for rid in ids:
                    if db.execute('SELECT 1 FROM readings WHERE source_reading_id=? AND id!=?',(rid,rid)).fetchone():raise HistoryError('削除済み履歴の依存関係を確認してください。',409)
                    db.execute('DELETE FROM reading_organization_scopes WHERE reading_id=? AND owner_user_id=?',(rid,owner))
                    db.execute('DELETE FROM readings WHERE id=? AND owner_user_id=?',(rid,owner))
                for gid in groups:
                    db.execute('DELETE FROM reading_groups WHERE id=? AND owner_user_id=? AND NOT EXISTS(SELECT 1 FROM readings r WHERE r.group_id=reading_groups.id)',(gid,owner))
                for pid in persons:
                    db.execute('DELETE FROM persons WHERE id=? AND owner_user_id=? AND NOT EXISTS(SELECT 1 FROM readings r WHERE r.person_id=persons.id) AND NOT EXISTS(SELECT 1 FROM reading_groups g WHERE g.person_id=persons.id)',(pid,owner))
                if event['kind']=='user' and db.execute('SELECT 1 FROM users WHERE id=?',(owner,)).fetchone():
                    if db.execute('SELECT 1 FROM operating_administrator WHERE user_id=?',(owner,)).fetchone():raise HistoryError('運営者の復元情報を確認してください。',409)
                    self.remove_user_records(db,owner,now)
                db.execute('INSERT OR IGNORE INTO deletion_journal VALUES (?,?,?,?,?,?,?,?)',tuple(event[k] for k in ('id','kind','former_user_id','organization_id','reading_ids_json','deleted_at','review_after','review_state')))
            # Offline fixture remains closed: passwords/account state must be reconciled externally.
            db.execute("UPDATE users SET status='disabled'")
            if db.execute('PRAGMA foreign_key_check').fetchall():raise HistoryError('復元後の参照整合性を確認してください。',409)
            return preview


    def retention_reviews(self, actor):
        with self.auth.connection() as db:
            self.operations.require_admin(db,actor)
            return [dict(r) for r in db.execute('SELECT id,record_kind,organization_id,review_on,retention_basis FROM retained_records ORDER BY review_on,id')]

    def review(self, actor, kind, identifier, review_on, basis):
        review_on=day(review_on);basis=text(basis,200)
        if not review_on or review_on<=utc(None).astimezone(JST).date().isoformat():raise HistoryError('将来の保持見直し日を指定してください。',422)
        with self.operations.change(actor) as db:
            if kind=='purchase':
                changed=db.execute('UPDATE purchase_proofs SET review_on=?,retention_basis=? WHERE purchase_number=?',(review_on,basis,identifier)).rowcount
            elif kind=='record':
                changed=db.execute('UPDATE retained_records SET review_on=?,retention_basis=? WHERE id=?',(review_on,basis,identifier)).rowcount
            else:raise HistoryError('保持記録の種類を確認してください。',422)
            if not changed:raise HistoryError('保持記録が見つかりません。',404)
            self.operations.audit(db,actor,'retention-review-'+kind,identifier)
