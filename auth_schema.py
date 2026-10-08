"""Additive SQLite migrations for authentication extensions (no user rewrites)."""
from history_repository import timestamp


def apply_migration(db, key, statements):
    if not db.in_transaction:
        db.execute("BEGIN IMMEDIATE")
    db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (migration_key TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
    if db.execute("SELECT 1 FROM schema_migrations WHERE migration_key=?", (key,)).fetchone():
        return
    for statement in statements:
        db.execute(statement)
    db.execute("INSERT INTO schema_migrations VALUES (?,?)", (key, timestamp()))


def migrate_auth_extensions(db):
    apply_migration(db, "auth-lifecycle-001", [
        """CREATE TABLE user_account_lifecycle (
            user_id TEXT PRIMARY KEY REFERENCES users(id),
            state TEXT NOT NULL CHECK(state IN ('active','suspended','deletion_pending')),
            suspended_at TEXT, deletion_pending_at TEXT, updated_at TEXT NOT NULL,
            CHECK((state='active' AND suspended_at IS NULL AND deletion_pending_at IS NULL)
                OR (state='suspended' AND suspended_at IS NOT NULL AND deletion_pending_at IS NULL)
                OR (state='deletion_pending' AND suspended_at IS NOT NULL AND deletion_pending_at IS NOT NULL)))""",
        "CREATE INDEX account_lifecycle_due ON user_account_lifecycle(state,suspended_at,deletion_pending_at)",
        """CREATE TABLE user_activity (
            user_id TEXT PRIMARY KEY REFERENCES users(id), last_login_at TEXT NOT NULL)""",
    ])

    apply_migration(db, "auth-password-reset-002", [
        """CREATE TABLE password_reset_tokens (token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id), password_version TEXT NOT NULL,
            created_at TEXT NOT NULL, expires_at REAL NOT NULL, used_at TEXT)""",
        "CREATE INDEX password_reset_user ON password_reset_tokens(user_id,used_at)",
        """CREATE TABLE password_reset_attempts (id TEXT PRIMARY KEY, operation TEXT NOT NULL,
            ip_key TEXT NOT NULL, account_key TEXT NOT NULL, attempted_at REAL NOT NULL)""",
        "CREATE INDEX password_reset_rate_ip ON password_reset_attempts(operation,ip_key,attempted_at)",
        "CREATE INDEX password_reset_rate_account ON password_reset_attempts(operation,account_key,attempted_at)",
    ])

    apply_migration(db, "auth-initial-setup-003", [
        """CREATE TABLE user_initial_setup (user_id TEXT PRIMARY KEY REFERENCES users(id),
            completed_at TEXT)""",
    ])


def set_account_state(db, user_id, state, now):
    db.execute("UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL", (now,user_id))
    current = db.execute("SELECT * FROM user_account_lifecycle WHERE user_id=?", (user_id,)).fetchone()
    if state == "suspended" and current and current["state"] in ("suspended", "deletion_pending"):
        return
    suspended_at = None if state == "active" else now
    db.execute("""INSERT INTO user_account_lifecycle VALUES (?,?,?,NULL,?)
        ON CONFLICT(user_id) DO UPDATE SET state=excluded.state,
        suspended_at=excluded.suspended_at,deletion_pending_at=NULL,updated_at=excluded.updated_at""",
        (user_id, state, suspended_at, now))
