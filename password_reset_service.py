"""Password reset tokens and application service; no automatic live mail wiring."""
from datetime import datetime, timezone
import hmac
import logging
import secrets
import time
from urllib.parse import urlsplit
from uuid import uuid4
from auth_service import AuthRepository, AuthSettings, AuthError, normalized_email, password_hash, token_hash
from mail_delivery import TextMail

RESET_TTL_SECONDS=30*60
ACCEPTED_MESSAGE="登録されている場合は、パスワード再設定の案内を送信します。"
INVALID_LINK_MESSAGE="再設定リンクが無効または期限切れです。再度申請してください。"


def stamp(now): return datetime.fromtimestamp(now,timezone.utc).isoformat(timespec="microseconds")


def trusted_origin(value, development=False):
    try:
        parsed=urlsplit(value)
        if parsed.username or parsed.password or parsed.path not in ("","/") or parsed.query or parsed.fragment or not parsed.hostname:
            raise ValueError()
        parsed.port
        if parsed.scheme!="https" and not (development and parsed.scheme=="http" and parsed.hostname in ("localhost","127.0.0.1","::1")):
            raise ValueError()
        if any(c.isspace() for c in value): raise ValueError()
    except (ValueError,TypeError,AttributeError): raise AuthError("再設定メールはまだ利用できません。",503) from None
    return value.rstrip("/")


class PasswordResetRepository:
    def __init__(self, auth): self.auth=auth

    def admit(self, operation, account, ip, settings, now):
        # Separate persisted budgets, identical for present/absent accounts; no mail address stored here.
        account_key=token_hash(account); ip_key=token_hash(ip)
        with self.auth.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM password_reset_attempts WHERE attempted_at<=?",(now-settings.login_window,))
            ip_count=db.execute("SELECT count(*) FROM password_reset_attempts WHERE operation=? AND ip_key=?",(operation,ip_key)).fetchone()[0]
            account_count=db.execute("SELECT count(*) FROM password_reset_attempts WHERE operation=? AND account_key=?",(operation,account_key)).fetchone()[0]
            if ip_count>=settings.ip_limit or account_count>=settings.account_limit:
                raise AuthError("しばらく時間をおいて再度お試しください。",429)
            db.execute("INSERT INTO password_reset_attempts VALUES (?,?,?,?,?)",(str(uuid4()),operation,ip_key,account_key,now))

    def issue(self, email, now):
        raw_token=secrets.token_urlsafe(32)
        with self.auth.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            user=db.execute("""SELECT u.* FROM users u LEFT JOIN user_account_lifecycle l ON l.user_id=u.id
                WHERE normalized_email=? AND u.status='active' AND COALESCE(l.state,'active')='active'""",(email,)).fetchone()
            if not user: return None
            db.execute("UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL",(stamp(now),user["id"]))
            db.execute("INSERT INTO password_reset_tokens VALUES (?,?,?,?,?,NULL)",
                       (token_hash(raw_token),user["id"],token_hash(user["password_hash"]),stamp(now),now+RESET_TTL_SECONDS))
            return user["email"],raw_token

    def revoke(self, raw_token, now):
        with self.auth.connection() as db:
            db.execute("UPDATE password_reset_tokens SET used_at=? WHERE token_hash=? AND used_at IS NULL",(stamp(now),token_hash(raw_token)))

    def complete(self, raw_token, new_password, now):
        if not isinstance(raw_token,str) or not 40<=len(raw_token)<=200:
            raise AuthError(INVALID_LINK_MESSAGE,400)
        encoded=password_hash(new_password)
        with self.auth.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("""SELECT t.*,u.password_hash FROM password_reset_tokens t JOIN users u ON u.id=t.user_id
                LEFT JOIN user_account_lifecycle l ON l.user_id=u.id WHERE t.token_hash=? AND t.used_at IS NULL
                AND t.expires_at>? AND u.status='active' AND COALESCE(l.state,'active')='active'""",(token_hash(raw_token),now)).fetchone()
            if not row or not hmac.compare_digest(row["password_version"],token_hash(row["password_hash"])):
                raise AuthError(INVALID_LINK_MESSAGE,400)
            db.execute("UPDATE users SET password_hash=?,updated_at=? WHERE id=?",(encoded,stamp(now),row["user_id"]))
            db.execute("UPDATE user_initial_setup SET completed_at=? WHERE user_id=?",(stamp(now),row["user_id"]))
            db.execute("UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL",(stamp(now),row["user_id"]))
            db.execute("UPDATE auth_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL",(stamp(now),row["user_id"]))
        return {"ok":True}


class PasswordResetService:
    def __init__(self, auth, mailer=None, public_origin=None, settings=None, clock=time.time):
        self.repository=PasswordResetRepository(auth); self.mailer=mailer; self.public_origin=public_origin
        self.settings=settings or AuthSettings.load(); self.clock=clock

    def admit_request(self, email, ip):
        if self.mailer is None or self.public_origin is None: raise AuthError("再設定メールはまだ利用できません。",503)
        trusted_origin(self.public_origin,development=not self.settings.production)
        email=normalized_email(email)
        self.repository.admit("request",email,ip,self.settings,self.clock())
        return email

    def deliver(self, normalized):
        # Called after the HTTP response. Live SMTP latency/failure must not reveal account existence.
        issued=None
        try:
            issued=self.repository.issue(normalized,self.clock())
            if issued:
                email,token=issued
                link=trusted_origin(self.public_origin,development=not self.settings.production)+"/reset-password#token="+token
                self.mailer.send(TextMail(email,"パスワード再設定",f"30分以内に次のリンクからパスワードを再設定してください。\n{link}\n心当たりがない場合は、このメールを無視してください。"))
        except Exception:
            if issued:
                try: self.repository.revoke(issued[1],self.clock())
                except Exception: pass
            logging.getLogger(__name__).error("Password reset delivery unavailable")

    def request(self,email,ip="local-test"):
        normalized=self.admit_request(email,ip); self.deliver(normalized)
        return {"ok":True,"message":ACCEPTED_MESSAGE}

    def complete(self,token,password,ip="local-test"):
        # Bound all unauthenticated Argon2 operations by IP and token budgets.
        budget=token if isinstance(token,str) and len(token)<=200 else "invalid-token"
        now=self.clock(); self.repository.admit("complete",budget,ip,self.settings,now)
        return self.repository.complete(token,password,now)
