"""Phase 9 confirmed permissions/contracts/billing. Temporary DB only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from auth_service import AuthRepository,AuthError,AuthSettings
from operations_repository import OperationsRepository
from history_repository import HistoryError
from password_reset_service import PasswordResetService
from mail_delivery import MemoryMailTransport
from billing_policy import arrears_preview,add_months

PASSWORD="synthetic-password-1234"
NOW=datetime(2026,10,8,tzinfo=timezone.utc)

class OperationsCases(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.path=Path(self.temp.name)/"test.db"
        self.repo=OperationsRepository(self.path); self.auth=self.repo.auth
        self.admin=self.auth.create_user("operator@example.test",PASSWORD)["id"]
        self.teacher=self.auth.create_user("teacher@example.test",PASSWORD)["id"]
        self.student=self.auth.create_user("student@example.test",PASSWORD)["id"]
        self.repo.bootstrap(self.admin)
        self.org=self.repo.create_organization(self.admin,"教室一","class-one")["id"]
        self.other=self.repo.create_organization(self.admin,"教室二","class-two")["id"]
        self.repo.assign(self.admin,self.org,self.teacher,"teacher")
        self.repo.assign(self.admin,self.org,self.student,"student",True,2000)
    def tearDown(self): self.temp.cleanup()
    def test_single_operator_explicit_and_idempotent(self):
        self.repo.bootstrap(self.admin)
        with self.assertRaises(AuthError): self.repo.bootstrap(self.teacher)
    def test_membership_role_admin_does_not_grant_operator(self):
        self.repo.product.add_membership(self.other,self.teacher,"admin")
        with self.assertRaises(AuthError): self.repo.users(self.teacher)
    def test_teacher_and_student_cannot_write(self):
        for actor in (self.teacher,self.student):
            with self.assertRaises(AuthError): self.repo.create_organization(actor,"Forbidden","forbidden")
            with self.assertRaises(AuthError): self.repo.transition(actor,self.student,"suspend")
            with self.assertRaises(AuthError): self.repo.issue_account(actor,self.org,"new@example.test","新規",True)
    def test_teacher_payload_allowlist_no_student_metrics_or_identifiers(self):
        data=self.repo.teacher(self.org,self.teacher)
        self.assertEqual(set(data),{"organization_id","display_name","students"})
        self.assertEqual(set(data["students"][0]),{"display_name","account_state"})
        self.assertNotIn(self.student,str(data)); self.assertNotIn("student@example.test",str(data))
    def test_teacher_wrong_org_and_student_role_denied(self):
        with self.assertRaises(HistoryError): self.repo.teacher(self.other,self.teacher)
        with self.assertRaises(AuthError): self.repo.teacher(self.org,self.student)
    def test_teacher_termination_preserves_student_access_and_history_structure(self):
        c=self.repo.teacher_contract(self.admin,self.org,"active")["id"]
        for state in ("suspended","terminated"):
            self.repo.teacher_contract(self.admin,self.org,state,c)
            self.assertEqual(self.repo.context(self.org,self.student).user_id,self.student)
    def test_student_payment_confirmation_required(self):
        self.repo.assign(self.admin,self.other,self.student,"student",False)
        with self.assertRaises(AuthError): self.repo.context(self.other,self.student)
    def test_issue_requires_paid_and_atomic_no_partial_user(self):
        with self.assertRaises(HistoryError): self.repo.issue_account(self.admin,self.org,"new@example.test","新規",False)
        with self.assertRaises(HistoryError): self.repo.issue_account(self.admin,self.org,"new@example.test","新規",True,-1)
        with self.auth.connection() as db:
            self.assertIsNone(db.execute("SELECT 1 FROM users WHERE normalized_email='new@example.test'").fetchone())
    def test_initial_password_not_operator_supplied_and_pending_gate(self):
        issued=self.repo.issue_account(self.admin,self.org,"new@example.test","新規",True)
        self.assertEqual(set(issued),{"id","email","setup_pending"})
        with self.assertRaises(AuthError): self.auth.login(issued["email"],PASSWORD)
        with self.auth.connection() as db:
            self.assertIsNone(db.execute("SELECT completed_at FROM user_initial_setup WHERE user_id=?",(issued["id"],)).fetchone()[0])
    def test_existing_reset_sets_initial_password_and_user_id_preserved(self):
        issued=self.repo.issue_account(self.admin,self.org,"new@example.test","新規",True)
        mail=MemoryMailTransport(); service=PasswordResetService(self.auth,mail,"https://app.example.test")
        service.request(issued["email"])
        token=mail.messages[-1].body.split("#token=")[1].split()[0]
        service.complete(token,PASSWORD)
        self.assertEqual(self.auth.login(issued["email"],PASSWORD)[0]["id"],issued["id"])
        with self.assertRaises(AuthError):service.complete(token,PASSWORD)
    def test_suspend_revokes_login_and_context(self):
        token=self.auth.login("student@example.test",PASSWORD)[1]
        self.repo.transition(self.admin,self.student,"suspend",NOW)
        with self.assertRaises(AuthError): self.auth.authenticate(token)
        with self.assertRaises(HistoryError): self.repo.context(self.org,self.student)
    def test_resume_requires_all_arrears_settled(self):
        a=self.repo.record_due(self.admin,self.org,self.student,"2026-08-01",2000)["id"]
        b=self.repo.record_due(self.admin,self.org,self.student,"2026-09-01",2000)["id"]
        self.repo.transition(self.admin,self.student,"suspend",NOW)
        self.repo.settle_due(self.admin,self.student,a)
        with self.assertRaises(HistoryError): self.repo.transition(self.admin,self.student,"resume",NOW)
        self.repo.settle_due(self.admin,self.student,b)
        self.repo.transition(self.admin,self.student,"resume",NOW)
        contract=self.repo.user(self.admin,self.student)["memberships"][0]
        self.assertEqual(contract["minimum_term_until"],"2026-12-08T00:00:00.000000+00:00")
    def test_no_new_fee_while_suspended(self):
        self.repo.transition(self.admin,self.student,"suspend",NOW)
        with self.assertRaises(HistoryError): self.repo.record_due(self.admin,self.org,self.student,"2026-11-01",2000)
    def test_dues_other_user_and_duplicate_rejected(self):
        a=self.repo.record_due(self.admin,self.org,self.student,"2026-08-01",2000)["id"]
        with self.assertRaises(HistoryError): self.repo.settle_due(self.admin,self.teacher,a)
        with self.assertRaises(HistoryError): self.repo.record_due(self.admin,self.org,self.student,"2026-08-01",2000)
    def test_admin_self_suspend_denied(self):
        with self.assertRaises(HistoryError): self.repo.transition(self.admin,self.admin,"suspend")
    def test_audit_atomic_and_content_free(self):
        before=len(self.repo.audit_list(self.admin))
        with self.assertRaises(HistoryError): self.repo.assign(self.admin,self.other,self.student,"unknown")
        self.assertEqual(len(self.repo.audit_list(self.admin)),before)
        self.repo.set_name(self.admin,self.student,"氏名")
        entries=self.repo.audit_list(self.admin)
        self.assertEqual(entries[0]["action"],"user-name-set")
        self.assertNotIn(PASSWORD,str(entries));self.assertNotIn("氏名",str(entries))
    def test_admin_projections_do_not_return_password_or_reading_content(self):
        for value in (self.repo.users(self.admin),self.repo.user(self.admin,self.student),self.repo.organization(self.admin,self.org)):
            self.assertNotIn("password_hash",str(value));self.assertNotIn("input_snapshot",str(value));self.assertNotIn("result_snapshot",str(value))
    def test_b2c_without_membership_is_unchanged(self):
        user=self.auth.create_user("b2c@example.test",PASSWORD)
        self.assertEqual(self.auth.login(user["email"],PASSWORD)[0],user)
        self.assertEqual(self.repo.access(user["id"])["memberships"],[])
    def test_two_month_grace_and_third_month_boundary(self):
        due=datetime(2026,1,31,tzinfo=timezone.utc)
        before=arrears_preview(due,due,datetime(2026,3,30,23,59,tzinfo=timezone.utc))
        after=arrears_preview(due,due,datetime(2026,3,31,tzinfo=timezone.utc))
        self.assertFalse(before["suspension_due"]);self.assertTrue(after["suspension_due"])
        self.assertFalse(after["automatic_actions_enabled"])
    def test_reminders_two_weeks_and_no_auto_action(self):
        self.assertFalse(arrears_preview(NOW,NOW,NOW+timedelta(days=13))["reminder_due"])
        self.assertTrue(arrears_preview(NOW,NOW,NOW+timedelta(days=14))["reminder_due"])
        self.assertEqual(arrears_preview(NOW,NOW,NOW,last_reminded_at=NOW+timedelta(days=14))["next_reminder_at"],NOW+timedelta(days=28))
    def test_leap_month_clamping(self):
        self.assertEqual(add_months(datetime(2028,1,31,tzinfo=timezone.utc),1).day,29)
        with self.assertRaises(ValueError):arrears_preview(NOW,NOW-timedelta(days=1),NOW)

if __name__=="__main__":unittest.main(verbosity=2)
