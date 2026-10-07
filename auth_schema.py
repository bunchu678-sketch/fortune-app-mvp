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


def set_account_state(db, user_id, state, now):
    current = db.execute("SELECT * FROM user_account_lifecycle WHERE user_id=?", (user_id,)).fetchone()
    if state == "suspended" and current and current["state"] in ("suspended", "deletion_pending"):
        return
    suspended_at = None if state == "active" else now
    db.execute("""INSERT INTO user_account_lifecycle VALUES (?,?,?,NULL,?)
        ON CONFLICT(user_id) DO UPDATE SET state=excluded.state,
        suspended_at=excluded.suspended_at,deletion_pending_at=NULL,updated_at=excluded.updated_at""",
        (user_id, state, suspended_at, now))
