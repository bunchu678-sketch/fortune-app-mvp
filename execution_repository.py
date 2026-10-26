"""Successful calculation ledger. No birth data, person names or fortune output persisted."""
import hashlib
import hmac
import json
import secrets
from uuid import uuid4, UUID
from history_repository import HistoryError, timestamp
from auth_schema import apply_migration
from auth_service import AuthError
from product_repository import ProductRepository
from operations_repository import OperationsRepository
from usage_repository import month_window
from account_lifecycle import utc


def execution_key(value):
    try:
        if not isinstance(value,str) or str(UUID(value))!=value.lower(): raise ValueError()
    except (ValueError,AttributeError): raise HistoryError("鑑定実行IDを確認してください。",422) from None
    return value.lower()


def fingerprint(payload, salt):
    # Only a random-key HMAC remains in DB. No inputs/results are recorded for metrics.
    raw=json.dumps(payload,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(",",":")).encode()
    return hmac.new(bytes.fromhex(salt),raw,hashlib.sha256).hexdigest()


class ExecutionRepository:
    def __init__(self, operations):
        self.operations=operations;self.auth=operations.auth
        with self.auth.connection() as db:
            apply_migration(db,"product-executions-003",[
                """CREATE TABLE successful_executions (id TEXT PRIMARY KEY, owner_user_id TEXT NOT NULL REFERENCES users(id),
                    organization_id TEXT REFERENCES organizations(id), scope_key TEXT NOT NULL,
                    execution_key_hash TEXT NOT NULL, payload_mac TEXT NOT NULL, comparison_key TEXT NOT NULL,
                    completed_at TEXT NOT NULL, UNIQUE(owner_user_id,scope_key,execution_key_hash),
                    CHECK(scope_key=COALESCE(organization_id,'b2c')))""",
                "CREATE INDEX executions_owner_time ON successful_executions(owner_user_id,completed_at)",
                "CREATE INDEX executions_org_time ON successful_executions(organization_id,completed_at)",
            ])

    def record_success(self, owner, organization_id, key, payload, now=None):
        key=execution_key(key);key_hash=hashlib.sha256(key.encode()).hexdigest();scope=organization_id or "b2c"
        stamp=utc(now).isoformat(timespec="microseconds")
        with self.auth.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("""SELECT 1 FROM users u LEFT JOIN user_account_lifecycle l ON l.user_id=u.id
                WHERE u.id=? AND u.status='active' AND COALESCE(l.state,'active')='active'
                AND NOT EXISTS(SELECT 1 FROM user_initial_setup i WHERE i.user_id=u.id AND i.completed_at IS NULL)""",(owner,)).fetchone():
                raise AuthError("ログインしてください。",401)
            if organization_id:self.operations.member_access(db,organization_id,owner)
            old=db.execute("SELECT payload_mac,comparison_key FROM successful_executions WHERE owner_user_id=? AND scope_key=? AND execution_key_hash=?",(owner,scope,key_hash)).fetchone()
            if old:
                if not hmac.compare_digest(old["payload_mac"],fingerprint(payload,old["comparison_key"])):
                    raise HistoryError("別条件の鑑定には新しい実行IDを使用してください。",409)
                return False
            salt=secrets.token_hex(32)
            db.execute("INSERT INTO successful_executions VALUES (?,?,?,?,?,?,?,?)",(str(uuid4()),owner,organization_id,scope,key_hash,fingerprint(payload,salt),salt,stamp))
            return True

    @staticmethod
    def counts(db, owner=None, org=None, now=None):
        start,end=month_window(now)
        row=db.execute("""SELECT COUNT(*) AS executions_total,
            COALESCE(SUM(CASE WHEN completed_at>=? AND completed_at<? THEN 1 ELSE 0 END),0) AS executions_this_month,
            MAX(completed_at) AS last_execution_at FROM successful_executions
            WHERE (? IS NULL OR owner_user_id=?) AND (? IS NULL OR organization_id=?)""",(start,end,owner,owner,org,org)).fetchone()
        return dict(row)

    def personal(self, owner, org=None, now=None):
        with self.auth.connection() as db:
            if org:self.operations.member_access(db,org,owner)
            row=db.execute("""SELECT COUNT(*) AS saved_histories_total,
                COALESCE(SUM(CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END),0) AS saved_histories_current,
                COALESCE(SUM(CASE WHEN deleted_at IS NOT NULL THEN 1 ELSE 0 END),0) AS deleted_histories
                FROM readings WHERE owner_user_id=?""",(owner,)).fetchone()
            if org:
                row=db.execute("""SELECT COUNT(*) AS saved_histories_total,
                    COALESCE(SUM(CASE WHEN r.deleted_at IS NULL THEN 1 ELSE 0 END),0) AS saved_histories_current,
                    COALESCE(SUM(CASE WHEN r.deleted_at IS NOT NULL THEN 1 ELSE 0 END),0) AS deleted_histories
                    FROM readings r JOIN reading_organization_scopes s ON s.reading_id=r.id AND s.owner_user_id=r.owner_user_id
                    WHERE r.owner_user_id=? AND s.organization_id=?""",(owner,org)).fetchone()
            return {**self.counts(db,owner,org,now),**dict(row),"month_timezone":"Asia/Tokyo",
                    "execution_count_basis":"successful_new_calculations","saved_count_basis":"persisted_histories"}

    def organization_totals(self, org, now=None):
        with self.auth.connection() as db:
            self.operations.product.organization(db,org)
            data=self.counts(db,org=org,now=now)
            # Teachers receive no last-time field and no per-student quantities.
            return {"executions_this_month":data["executions_this_month"],"executions_total":data["executions_total"],"month_timezone":"Asia/Tokyo"}
