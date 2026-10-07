"""Lifecycle contracts against disposable DBs; existing users and snapshots retained."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from auth_service import AuthRepository, AuthError, AuthSettings
from account_lifecycle import AccountLifecycleRepository, anniversary
from history_repository import SQLiteHistoryRepository

NOW = datetime(2024, 2, 29, 12, tzinfo=timezone.utc)
SETTINGS = AuthSettings(86400,900,100,1000,False,"")

class LifecycleCases(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.path = Path(self.temp.name)/"test.db"
        self.auth = AuthRepository(self.path)
        self.user = self.auth.create_user("one@example.test", "synthetic-password-1234")
        self.other = self.auth.create_user("two@example.test", "synthetic-password-1234")
        self.repo = AccountLifecycleRepository(self.path)
    def tearDown(self): self.temp.cleanup()
    def login(self):
        return self.auth.login(self.user["email"],"synthetic-password-1234",SETTINGS,clock=lambda:NOW.timestamp())[1]
    def test_one_year_boundary_and_thirty_day_wait(self):
        self.repo.suspend(self.user["id"],NOW)
        due=anniversary(NOW)
        self.assertEqual(self.repo.advance_due(due-timedelta(microseconds=1)),[])
        self.assertEqual(self.repo.advance_due(due),[self.user["id"]])
        self.assertEqual(self.repo.purge_candidates(due+timedelta(days=30)-timedelta(microseconds=1)),[])
        self.assertEqual(self.repo.purge_candidates(due+timedelta(days=30)),[self.user["id"]])
        with self.auth.connection() as db: self.assertEqual(db.execute("SELECT count(*) FROM users").fetchone()[0],2)
    def test_thirty_days_suspended_is_not_deletable(self):
        self.repo.suspend(self.user["id"],NOW)
        self.assertEqual(self.repo.advance_due(NOW+timedelta(days=30)),[])
        self.assertEqual(self.repo.purge_candidates(NOW+timedelta(days=30)),[])
    def test_late_transition_still_gets_full_thirty_days(self):
        self.repo.suspend(self.user["id"],NOW); late=NOW+timedelta(days=800)
        self.repo.advance_due(late)
        self.assertEqual(self.repo.purge_candidates(late),[])
        self.assertEqual(self.repo.purge_candidates(late+timedelta(days=30)),[self.user["id"]])
    def test_suspension_revokes_and_denies_login(self):
        token=self.login(); self.repo.suspend(self.user["id"],NOW)
        with self.assertRaises(AuthError): self.auth.authenticate(token,clock=lambda:NOW.timestamp())
        with self.assertRaises(AuthError): self.login()
    def test_side_table_checked_even_if_legacy_status_active(self):
        token=self.login(); self.repo.suspend(self.user["id"],NOW)
        with self.auth.connection() as db:
            db.execute("UPDATE users SET status='active' WHERE id=?",(self.user["id"],))
            db.execute("UPDATE auth_sessions SET revoked_at=NULL")
        with self.assertRaises(AuthError): self.auth.authenticate(token,clock=lambda:NOW.timestamp())
        with self.assertRaises(AuthError): self.login()
    def test_resume_never_revives_old_session_and_clears_deadlines(self):
        token=self.login(); self.repo.suspend(self.user["id"],NOW); self.repo.advance_due(anniversary(NOW))
        self.repo.resume(self.user["id"],anniversary(NOW))
        self.assertEqual(self.repo.state(self.user["id"])["state"],"active")
        self.assertIsNone(self.repo.state(self.user["id"])["suspended_at"])
        with self.assertRaises(AuthError): self.auth.authenticate(token,clock=lambda:NOW.timestamp())
        self.login()
    def test_repeated_suspend_does_not_restart_clock(self):
        self.repo.suspend(self.user["id"],NOW); self.repo.suspend(self.user["id"],NOW+timedelta(days=30))
        self.assertEqual(self.repo.state(self.user["id"])["suspended_at"],NOW.isoformat(timespec="microseconds"))
    def test_cli_disable_enable_matches_lifecycle(self):
        self.auth.change_user(self.user["email"],"disable")
        self.assertEqual(self.repo.state(self.user["id"])["state"],"suspended")
        self.auth.change_user(self.user["email"],"enable")
        self.assertEqual(self.repo.state(self.user["id"])["state"],"active")
    def test_additive_idempotence_does_not_guess_legacy_suspend_date(self):
        with self.auth.connection() as db: db.execute("UPDATE users SET status='disabled' WHERE id=?",(self.other["id"],))
        before=self.repo.state(self.other["id"])
        AuthRepository(self.path); AccountLifecycleRepository(self.path)
        self.assertEqual(self.repo.state(self.other["id"]),before)
        self.assertIsNone(before["suspended_at"])
        with self.auth.connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM schema_migrations").fetchone()[0],1)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(),[])
    def test_missing_user_is_rejected(self):
        with self.assertRaises(AuthError): self.repo.suspend("missing",NOW)
    def test_last_login_is_single_derived_activity_value(self):
        self.login()
        with self.auth.connection() as db:
            self.assertEqual(db.execute("SELECT last_login_at FROM user_activity WHERE user_id=?",(self.user["id"],)).fetchone()[0],NOW.isoformat(timespec="microseconds"))
    def test_timezone_required(self):
        with self.assertRaises(ValueError): self.repo.advance_due(datetime(2026,1,1))

if __name__ == "__main__": unittest.main(verbosity=2)
