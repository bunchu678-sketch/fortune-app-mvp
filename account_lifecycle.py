"""Account retention policy; no physical deletion or scheduler is provided."""
from datetime import datetime, timedelta, timezone
from auth_service import AuthRepository, AuthError
from auth_schema import set_account_state


def utc(value=None):
    value = value or datetime.now(timezone.utc)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("An aware datetime is required")
    return value.astimezone(timezone.utc)


def anniversary(value):
    """One calendar year; a leap-day anniversary is February 28."""
    try:
        return value.replace(year=value.year + 1)
    except ValueError:
        return value.replace(year=value.year + 1, day=28)


class AccountLifecycleRepository:
    def __init__(self, path):
        self.auth = AuthRepository(path)

    def state(self, user_id):
        with self.auth.connection() as db:
            row = db.execute("""SELECT u.id,u.status,l.state,l.suspended_at,l.deletion_pending_at
                FROM users u LEFT JOIN user_account_lifecycle l ON l.user_id=u.id WHERE u.id=?""",
                (user_id,)).fetchone()
            if not row:
                raise AuthError("Account not found", 404)
            state = row["state"] or ("active" if row["status"] == "active" else "suspended")
            return {"user_id": user_id, "state": state, "suspended_at": row["suspended_at"],
                    "deletion_pending_at": row["deletion_pending_at"]}

    def suspend(self, user_id, now=None):
        stamp = utc(now).isoformat(timespec="microseconds")
        with self.auth.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone():
                raise AuthError("Account not found", 404)
            set_account_state(db, user_id, "suspended", stamp)
            db.execute("UPDATE users SET status='disabled',updated_at=? WHERE id=?", (stamp, user_id))
            db.execute("UPDATE auth_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (stamp,user_id))
        return self.state(user_id)

    def resume(self, user_id, now=None):
        stamp = utc(now).isoformat(timespec="microseconds")
        with self.auth.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone():
                raise AuthError("Account not found", 404)
            set_account_state(db, user_id, "active", stamp)
            db.execute("UPDATE users SET status='active',updated_at=? WHERE id=?", (stamp,user_id))
            db.execute("UPDATE auth_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (stamp,user_id))
        return self.state(user_id)

    def advance_due(self, now=None):
        instant = utc(now); stamp = instant.isoformat(timespec="microseconds")
        changed = []
        with self.auth.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT user_id,suspended_at FROM user_account_lifecycle WHERE state='suspended'").fetchall()
            for row in rows:
                if anniversary(utc(datetime.fromisoformat(row["suspended_at"]))) <= instant:
                    db.execute("""UPDATE user_account_lifecycle SET state='deletion_pending',
                        deletion_pending_at=?,updated_at=? WHERE user_id=?""", (stamp,stamp,row["user_id"]))
                    db.execute("UPDATE users SET status='disabled',updated_at=? WHERE id=?", (stamp,row["user_id"]))
                    db.execute("UPDATE auth_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (stamp,row["user_id"]))
                    changed.append(row["user_id"])
        return changed

    def purge_candidates(self, now=None):
        instant = utc(now)
        with self.auth.connection() as db:
            rows = db.execute("SELECT user_id,deletion_pending_at FROM user_account_lifecycle WHERE state='deletion_pending'").fetchall()
            return [row["user_id"] for row in rows
                    if utc(datetime.fromisoformat(row["deletion_pending_at"])) + timedelta(days=30) <= instant]
