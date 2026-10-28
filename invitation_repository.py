"""Operator-only initial invitations. Reuses reset tokens; no sale/payment records."""
from datetime import datetime,timezone
import logging
import secrets
import sqlite3
import time
from uuid import uuid4
from auth_schema import apply_migration
from auth_service import AuthError,normalized_email,password_hash,token_hash
from history_repository import HistoryError,timestamp
from password_reset_service import RESET_TTL_SECONDS,stamp
from product_repository import text


def trial_access(db,org,owner):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='initial_invitations'").fetchone():return False
    return bool(db.execute("""SELECT 1 FROM initial_invitations v JOIN user_initial_setup s ON s.user_id=v.user_id
        JOIN users u ON u.id=v.user_id WHERE v.organization_id=? AND v.user_id=? AND v.role='student'
        AND v.cancelled_at IS NULL AND s.completed_at IS NOT NULL AND u.status='active'""",(org,owner)).fetchone())


class InvitationRepository:
    def __init__(self,operations):
        self.operations=operations;self.auth=operations.auth
        with self.auth.connection() as db:
            apply_migration(db,'product-invitations-004',[
                """CREATE TABLE initial_invitations (
                    id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, user_id TEXT NOT NULL UNIQUE,
                    alias TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('teacher','student')),
                    purpose TEXT NOT NULL CHECK(purpose='free_trial'),
                    delivery_state TEXT NOT NULL CHECK(delivery_state IN ('unsent','queued','sending','provider_accepted','failed')),
                    attempt INTEGER NOT NULL DEFAULT 0, token_digest TEXT, expires_at REAL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, cancelled_at TEXT,
                    FOREIGN KEY(organization_id,user_id) REFERENCES memberships(organization_id,user_id))""",
                "CREATE UNIQUE INDEX invitation_active_alias ON initial_invitations(organization_id,alias) WHERE cancelled_at IS NULL",
            ])

    def list(self,actor,now=None):
        now=time.time() if now is None else now
        with self.auth.connection() as db:
            self.operations.require_admin(db,actor)
            rows=db.execute("""SELECT v.*,u.email,s.completed_at,t.used_at FROM initial_invitations v
                JOIN users u ON u.id=v.user_id JOIN user_initial_setup s ON s.user_id=v.user_id
                LEFT JOIN password_reset_tokens t ON t.token_hash=v.token_digest ORDER BY v.created_at DESC""").fetchall()
        result=[]
        for row in rows:
            setup=('cancelled' if row['cancelled_at'] else 'completed' if row['completed_at']
                else 'expired' if row['expires_at'] is not None and (row['expires_at']<=now or row['used_at']) else 'pending')
            result.append({key:row[key] for key in ('id','organization_id','user_id','alias','role','email','purpose','delivery_state','attempt','created_at','updated_at')} |
                          {'setup_state':setup,'expires_at':row['expires_at'],'mailbox_delivery_confirmed':False})
        return result

    def create(self,actor,org,alias,role,email,*,free_trial_confirmed=False):
        alias=text(alias,64)
        if role not in ('teacher','student') or free_trial_confirmed is not True:
            raise HistoryError('役割と無料試用の確認が必要です。',422)
        normalized=normalized_email(email)
        encoded=password_hash(secrets.token_urlsafe(48));now=timestamp()
        with self.operations.change(actor) as db:
            self.operations.product.organization(db,org)
            user=db.execute('SELECT id FROM users WHERE normalized_email=?',(normalized,)).fetchone()
            if user:
                previous=db.execute('SELECT * FROM initial_invitations WHERE user_id=?',(user['id'],)).fetchone()
                if (not previous or previous['organization_id']!=org or previous['alias']!=alias
                    or previous['role']!=role or previous['cancelled_at']):
                    raise HistoryError('登録済みUserの権限・所属を確認してください。自動で変更しません。',409)
                memberships=[tuple(r) for r in db.execute('SELECT organization_id,role FROM memberships WHERE user_id=?',(user['id'],))]
                if memberships!=[(org,role)]:raise HistoryError('既存Userの所属・役割が一致しません。',409)
                if db.execute('SELECT 1 FROM user_initial_setup WHERE user_id=? AND completed_at IS NOT NULL',(user['id'],)).fetchone():
                    raise HistoryError('初回設定は完了済みです。',409)
                return previous['id']
            if db.execute('SELECT 1 FROM initial_invitations WHERE organization_id=? AND alias=? AND cancelled_at IS NULL',(org,alias)).fetchone():
                raise HistoryError('同じ識別名の招待があります。再送または取消しを選んでください。',409)
            owner=str(uuid4());invitation=str(uuid4())
            db.execute('INSERT INTO users VALUES (?,?,?,?,?,?,?)',(owner,email.strip(),normalized,encoded,'active',now,now))
            db.execute('INSERT INTO user_profiles VALUES (?,?)',(owner,alias))
            db.execute('INSERT INTO user_initial_setup VALUES (?,NULL)',(owner,))
            self.operations.product.add_membership(org,owner,role,connection=db)
            db.execute("""INSERT INTO initial_invitations(id,organization_id,user_id,alias,role,purpose,delivery_state,created_at,updated_at)
                VALUES (?,?,?,?,?,'free_trial','unsent',?,?)""",(invitation,org,owner,alias,role,now,now))
            self.operations.audit(db,actor,'invitation-create-free-trial',owner,org)
            return invitation

    def queue(self,actor,invitation,service,ip):
        if service is None:raise AuthError('初回設定メールは未設定です。',503)
        with self.auth.connection() as db:
            self.operations.require_admin(db,actor)
            row=db.execute('SELECT v.*,u.email FROM initial_invitations v JOIN users u ON u.id=v.user_id WHERE v.id=?',(invitation,)).fetchone()
            if not row:raise HistoryError('招待が見つかりません。',404)
            email=row['email']
        service.admit_request(email,ip)
        with self.operations.change(actor) as db:
            row=db.execute('SELECT * FROM initial_invitations WHERE id=?',(invitation,)).fetchone()
            user=db.execute('SELECT status FROM users WHERE id=?',(row['user_id'],)).fetchone()
            memberships=[tuple(r) for r in db.execute('SELECT organization_id,role FROM memberships WHERE user_id=?',(row['user_id'],))]
            if memberships!=[(row['organization_id'],row['role'])]:raise HistoryError('所属・役割の変更を確認してください。',409)
            if row['cancelled_at'] or user['status']!='active':raise HistoryError('招待は取り消し済みか停止中です。',409)
            if db.execute('SELECT 1 FROM user_initial_setup WHERE user_id=? AND completed_at IS NOT NULL',(row['user_id'],)).fetchone():
                raise HistoryError('初回設定は完了済みです。',409)
            now=stamp(service.clock())
            db.execute('UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL',(now,row['user_id']))
            attempt=row['attempt']+1
            db.execute("UPDATE initial_invitations SET delivery_state='queued',attempt=?,token_digest=NULL,expires_at=NULL,updated_at=? WHERE id=?",(attempt,now,invitation))
            self.operations.audit(db,actor,'invitation-mail-queued',row['user_id'],row['organization_id'])
            return attempt

    def deliver(self,invitation,attempt,service):
        issued=None
        try:
            now=service.clock()
            with self.auth.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT v.*,u.email FROM initial_invitations v JOIN users u ON u.id=v.user_id WHERE v.id=?',(invitation,)).fetchone()
                if not row or row['cancelled_at'] or row['attempt']!=attempt or row['delivery_state']!='queued':return
                issued=service.repository.issue(normalized_email(row['email']),now,connection=db)
                if not issued:raise ValueError()
                db.execute("UPDATE initial_invitations SET delivery_state='sending',token_digest=?,expires_at=?,updated_at=? WHERE id=?",(token_hash(issued[1]),now+RESET_TTL_SECONDS,stamp(now),invitation))
            service.mailer.send(service.message(*issued,initial=True))
            state='provider_accepted'
        except Exception:
            if issued:
                try:service.repository.revoke(issued[1],service.clock())
                except Exception:pass
            state='failed'
            logging.getLogger(__name__).error('Invitation mail delivery unavailable')
        with self.auth.connection() as db:
            db.execute("UPDATE initial_invitations SET delivery_state=?,updated_at=? WHERE id=? AND attempt=? AND cancelled_at IS NULL",(state,stamp(service.clock()),invitation,attempt))

    def cancel(self,actor,invitation):
        with self.operations.change(actor) as db:
            row=db.execute('SELECT * FROM initial_invitations WHERE id=?',(invitation,)).fetchone()
            if not row:raise HistoryError('招待が見つかりません。',404)
            if row['cancelled_at']:return
            if db.execute('SELECT 1 FROM user_initial_setup WHERE user_id=? AND completed_at IS NOT NULL',(row['user_id'],)).fetchone():
                raise HistoryError('設定済みUserは利用停止の操作を使ってください。',409)
            now=timestamp()
            db.execute('UPDATE initial_invitations SET cancelled_at=?,updated_at=? WHERE id=?',(now,now,invitation))
            db.execute("UPDATE users SET status='disabled',updated_at=? WHERE id=?",(now,row['user_id']))
            db.execute('UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL',(now,row['user_id']))
            db.execute('UPDATE auth_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL',(now,row['user_id']))
            self.operations.audit(db,actor,'invitation-cancel',row['user_id'],row['organization_id'])
