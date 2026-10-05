"""Server-side authentication. Additive SQLite tables; no history rewrites."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from uuid import uuid4

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError, InvalidHashError
from history_repository import HistoryError, SQLiteHistoryRepository, timestamp

# Interim operational settings, not agreed product policy.
DEFAULT_SESSION_TTL_HOURS = 24
DEFAULT_LOGIN_WINDOW_SECONDS = 900
DEFAULT_LOGIN_ACCOUNT_LIMIT = 10
DEFAULT_LOGIN_IP_LIMIT = 30
COOKIE_NAME = "fortune_session"
PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4,
                                 hash_len=32, salt_len=16, type=Type.ID)
_DUMMY_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))


class AuthError(HistoryError):
    pass


def positive_setting(name, default, maximum):
    try:
        value = int(os.environ.get(name, str(default)))
        if not 1 <= value <= maximum:
            raise ValueError()
        return value
    except ValueError:
        raise AuthError("認証設定を確認してください。", 503) from None


@dataclass(frozen=True)
class AuthSettings:
    ttl_seconds: int
    login_window: int
    account_limit: int
    ip_limit: int
    production: bool
    public_origin: str

    @classmethod
    def load(cls):
        return cls(
            positive_setting("FORTUNE_SESSION_TTL_HOURS", DEFAULT_SESSION_TTL_HOURS, 8760) * 3600,
            positive_setting("FORTUNE_LOGIN_WINDOW_SECONDS", DEFAULT_LOGIN_WINDOW_SECONDS, 86400),
            positive_setting("FORTUNE_LOGIN_ACCOUNT_LIMIT", DEFAULT_LOGIN_ACCOUNT_LIMIT, 1000),
            positive_setting("FORTUNE_LOGIN_IP_LIMIT", DEFAULT_LOGIN_IP_LIMIT, 10000),
            os.environ.get("FORTUNE_ENV") == "production",
            os.environ.get("FORTUNE_PUBLIC_ORIGIN", "").strip().rstrip("/"),
        )


def database_path():
    value = os.environ.get("FORTUNE_HISTORY_DB_PATH")
    return Path(value) if value else Path(__file__).parent / "data" / "history.sqlite3"


def normalized_email(value):
    if not isinstance(value, str):
        raise AuthError("メールアドレスの形式を確認してください。", 422)
    value = value.strip()
    if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise AuthError("メールアドレスの形式を確認してください。", 422)
    return value.casefold()


def password_hash(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 1024:
        raise AuthError("パスワードは12〜1024文字で設定してください。", 422)
    return PASSWORD_HASHER.hash(password)


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def public_user(row):
    return {"id": row["id"], "email": row["email"]}


class AuthRepository:
    # Reuse only the connection/transaction helper, not the history initializer.
    connection = SQLiteHistoryRepository.connection

    def __init__(self, path=None):
        self.path = Path(path) if path is not None else database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, email TEXT NOT NULL,
                    normalized_email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active','disabled')),
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL, expires_at REAL NOT NULL, revoked_at TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id));
                CREATE INDEX IF NOT EXISTS auth_sessions_user ON auth_sessions(user_id);
                CREATE TABLE IF NOT EXISTS auth_login_attempts (
                    id INTEGER PRIMARY KEY, ip_key TEXT NOT NULL,
                    account_key TEXT NOT NULL, attempted_at REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS auth_login_ip ON auth_login_attempts(ip_key,attempted_at);
                CREATE INDEX IF NOT EXISTS auth_login_account ON auth_login_attempts(account_key,attempted_at);
            """)

    def create_user(self, email, password):
        normalized = normalized_email(email)
        encoded = password_hash(password)
        now, user_id = timestamp(), str(uuid4())
        try:
            with self.connection() as db:
                db.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)",
                           (user_id, email.strip(), normalized, encoded, "active", now, now))
        except sqlite3.IntegrityError:
            raise AuthError("同じメールアドレスは登録済みです。", 409) from None
        return {"id": user_id, "email": email.strip()}

    def change_user(self, email, action, password=None):
        normalized = normalized_email(email)
        encoded = password_hash(password) if action == "set-password" else None
        if action not in ("disable", "enable", "set-password"):
            raise AuthError("管理操作を確認してください。", 422)
        with self.connection() as db:
            row = db.execute("SELECT * FROM users WHERE normalized_email=?", (normalized,)).fetchone()
            if not row:
                raise AuthError("アカウントが見つかりません。", 404)
            if encoded:
                db.execute("UPDATE users SET password_hash=?,updated_at=? WHERE id=?",
                           (encoded, timestamp(), row["id"]))
            else:
                db.execute("UPDATE users SET status=?,updated_at=? WHERE id=?",
                           ("disabled" if action == "disable" else "active", timestamp(), row["id"]))
            if action != "enable":
                db.execute("UPDATE auth_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL",
                           (timestamp(), row["id"]))
            return public_user(row)

    def admit_login(self, email, ip, settings, now):
        # Do not trust request headers for IP identity. Persist budgets across workers/restarts.
        ip_key = token_hash(ip)
        account_key = token_hash(email)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM auth_login_attempts WHERE attempted_at<=?", (now-settings.login_window,))
            ip_count = db.execute("SELECT count(*) FROM auth_login_attempts WHERE ip_key=?", (ip_key,)).fetchone()[0]
            account_count = db.execute("SELECT count(*) FROM auth_login_attempts WHERE account_key=?", (account_key,)).fetchone()[0]
            if ip_count >= settings.ip_limit or account_count >= settings.account_limit:
                raise AuthError("ログイン試行が多いため、時間を置いて再度お試しください。", 429)
            db.execute("INSERT INTO auth_login_attempts(ip_key,account_key,attempted_at) VALUES (?,?,?)",
                       (ip_key, account_key, now))

    def login(self, email, password, settings=None, clock=time.time, previous_token=None, ip="local-cli"):
        settings = settings or AuthSettings.load()
        try:
            normalized = normalized_email(email)
        except AuthError:
            normalized = "invalid-email"
        if not isinstance(password, str) or not 1 <= len(password) <= 1024:
            raise AuthError("メールアドレスまたはパスワードが正しくありません。", 401)
        now = clock()
        self.admit_login(normalized, ip, settings, now)
        with self.connection() as db:
            row = db.execute("SELECT * FROM users WHERE normalized_email=?", (normalized,)).fetchone()
        try:
            valid = PASSWORD_HASHER.verify(row["password_hash"] if row else _DUMMY_HASH, password)
        except (VerificationError, InvalidHashError):
            valid = False
        if not valid or not row or row["status"] != "active":
            raise AuthError("メールアドレスまたはパスワードが正しくありません。", 401)
        raw_token = secrets.token_urlsafe(32)
        # Serialize with administrative disable/password changes and recheck hash/status.
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone()
            if current["status"] != "active" or current["password_hash"] != row["password_hash"]:
                raise AuthError("メールアドレスまたはパスワードが正しくありません。", 401)
            if previous_token:
                db.execute("UPDATE auth_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
                           (timestamp(), token_hash(previous_token)))
            db.execute("INSERT INTO auth_sessions VALUES (?,?,?,?,NULL)",
                       (token_hash(raw_token), row["id"], timestamp(), now+settings.ttl_seconds))
        return public_user(row), raw_token

    def authenticate(self, raw_token, clock=time.time):
        if not isinstance(raw_token, str) or not 20 <= len(raw_token) <= 200:
            raise AuthError("ログインしてください。", 401)
        with self.connection() as db:
            row = db.execute("""SELECT u.id,u.email FROM auth_sessions s JOIN users u ON u.id=s.user_id
                WHERE s.token_hash=? AND s.revoked_at IS NULL AND s.expires_at>?
                AND u.status='active'""", (token_hash(raw_token), clock())).fetchone()
        if not row:
            raise AuthError("ログインしてください。", 401)
        return public_user(row)

    def logout(self, raw_token):
        if raw_token and len(raw_token) <= 200:
            with self.connection() as db:
                db.execute("UPDATE auth_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
                           (timestamp(), token_hash(raw_token)))
