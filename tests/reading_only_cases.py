"""Current teacher app specification; restoration-only suites remain preserved separately."""
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import json
import os
import unittest
from unittest.mock import patch
from copy import deepcopy
import product_api_cases as fixtures
from deployment_boundary import DeploymentBoundary
from report_export_cases import FORM


class ReadingOnlyCases(unittest.TestCase):
    setUpClass = classmethod(fixtures.ProductAPICases.setUpClass.__func__)
    call = fixtures.ProductAPICases.call
    data = fixtures.ProductAPICases.data

    def setUp(self):
        fixtures.api_app.cache_clear()
        self.addCleanup(fixtures.api_app.cache_clear)
        fixtures.ProductAPICases.setUp(self)
        with self.auth.connection() as db:
            db.execute("UPDATE organizations SET slug='mari-mutsuro' WHERE id=?", (self.org,))
        self.surface = patch.dict(os.environ, {"FORTUNE_DEPLOYMENT_SURFACE": "teacher"})
        self.surface.start()
        self.inner = self.app
        self.app = DeploymentBoundary(self.inner, "teacher")
        self.app_patch.stop()
        self.app_patch = patch("auth_cases.api_app", return_value=self.app)
        self.app_patch.start()

    def tearDown(self):
        self.surface.stop()
        fixtures.ProductAPICases.tearDown(self)

    def state(self):
        with self.auth.connection() as db:
            return {r[0]: [tuple(row) for row in db.execute('SELECT * FROM "' + r[0] + '"')]
                    for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()}

    def test_anonymous_bootstrap_has_standard_theme_and_no_person(self):
        value = self.data("GET", "/api/reading/bootstrap", who="unknown")
        self.assertTrue(value["enabled"])
        self.assertIsNone(value["user"])
        self.assertIsNone(value["organization_id"])
        self.assertEqual(value["default_theme"]["definition"]["bg"], "#ffffff")

    def test_teacher_and_student_get_same_reading_context_without_management_fields(self):
        for who in ("teacher", "student"):
            value = self.data("GET", "/api/reading/bootstrap", who=who)
            self.assertEqual(value["organization_id"], self.org)
            self.assertNotIn("role", value)
            self.assertNotIn("memberships", value)
            self.assertNotIn("saved_histories_total", value)
            self.assertNotIn("is_operator", value)
            self.assertEqual(set(value["branding"]), {"display_name", "themes", "selected_theme_key", "presentation_mode", "thinking_groups"})

    def test_calculation_preserves_all_tables_and_matches_original_engine(self):
        before = self.state()
        for who in ("teacher", "student"):
            status, headers, body = self.call("POST", "/api/reading/fortune", FORM, who)
            self.assertEqual(status, 200, body)
            self.assertEqual(headers[b"cache-control"], b"no-store")
            self.assertEqual(json.loads(body), self.result)
            self.assertNotIn(b"excel_export_token", body)
        self.assertEqual(self.state(), before)

    def test_all_retired_api_methods_are_closed_before_authentication(self):
        rid = self.reading["id"]
        paths = ["/api/history", "/api/history/candidates", f"/api/history/{rid}", f"/api/history/{rid}/rerun",
                 f"/api/history/{rid}/memo", f"/api/history/{rid}/restore", "/api/history/deleted",
                 "/api/export/excel", "/api/export/xlsx", "/api/export/pdf", "/api/export-capabilities", "/api/account/summary",
                 f"/api/b2b/organizations/{self.org}/me", f"/api/b2b/organizations/{self.org}/teacher",
                 f"/api/b2b/organizations/{self.org}/fortune", f"/api/b2b/organizations/{self.org}/theme",
                 "/api/operations/users", "/api/fortune"]
        before = self.state()
        for who in ("student", "teacher", "admin", "unknown"):
            for path in paths:
                for method in ("GET", "POST", "PATCH", "DELETE"):
                    with self.subTest(who=who, path=path, method=method):
                        status, headers, body = self.call(method, path, {"memo": "never-save", "form": FORM}, who)
                        self.assertEqual(status, 404)
                        self.assertEqual(headers[b"cache-control"], b"no-store")
                        self.assertNotIn(b"PRIVATE-CONTENT", body)
        self.assertEqual(self.state(), before)

    def test_anonymous_other_class_and_operator_cannot_calculate(self):
        for who, status in (("unknown", 401), ("other", 403), ("admin", 403), ("b2c", 403)):
            self.assertEqual(self.call("POST", "/api/reading/fortune", FORM, who)[0], status)

    def test_supplied_scope_never_overrides_server_class(self):
        for key, value in (("organization_id", self.second), ("user_id", self.ids["other"]), ("role", "admin")):
            self.assertEqual(self.call("POST", "/api/reading/fortune", {**FORM, key: value})[0], 422)

    def test_csrf_invalid_json_and_oversized_input(self):
        self.assertEqual(self.call("POST", "/api/reading/fortune", FORM, origin="https://evil.example.test")[0], 403)
        self.assertEqual(self.call("POST", "/api/reading/fortune", raw=b"not-json")[0], 422)
        self.assertEqual(self.call("POST", "/api/reading/fortune", {**FORM, "consultation": "x" * 66000})[0], 422)

    def test_theme_save_is_personal_and_survives_new_session(self):
        for key in ("red", "blue", "black", "default"):
            self.assertEqual(self.data("POST", "/api/reading/theme", {"theme_key": key})["selected_theme_key"], key)
        self.data("POST", "/api/reading/theme", {"theme_key": "blue"})
        self.auth.logout(self.cookies["student"])
        self.cookies["student"] = self.auth.login("student@example.test", fixtures.PASSWORD)[1]
        self.assertEqual(self.data("GET", "/api/reading/bootstrap")["branding"]["selected_theme_key"], "blue")
        self.assertEqual(self.data("GET", "/api/reading/bootstrap", who="teacher")["branding"]["selected_theme_key"], "default")
        self.assertEqual(self.call("POST", "/api/reading/theme", {"theme_key": "red"}, origin="https://evil.example.test")[0], 403)
        self.assertEqual(self.call("POST", "/api/reading/theme", {"theme_key": "missing"})[0], 404)

    def test_revoked_contract_and_account_are_enforced(self):
        for who in ("teacher", "student"):
            with self.auth.connection() as db:
                db.execute("UPDATE memberships SET role='revoked' WHERE organization_id=? AND user_id=?", (self.org, self.ids[who]))
            self.assertEqual(self.call("POST", "/api/reading/fortune", FORM, who)[0], 403)

    def test_unpaid_and_suspended_students_are_denied(self):
        with self.auth.connection() as db:
            db.execute("UPDATE user_service_contracts SET initial_payment_confirmed=0 WHERE organization_id=? AND user_id=?", (self.org, self.ids["student"]))
        self.assertEqual(self.call("POST", "/api/reading/fortune", FORM)[0], 403)
        self.ops.transition(self.ids["admin"], self.ids["teacher"], "suspend")
        self.assertEqual(self.call("POST", "/api/reading/fortune", FORM, "teacher")[0], 401)

    def test_logout_invalidates_calculation_and_bootstrap(self):
        self.assertEqual(self.call("POST", "/api/auth/logout", {})[0], 200)
        self.assertEqual(self.call("POST", "/api/reading/fortune", FORM)[0], 401)
        self.assertIsNone(self.data("GET", "/api/reading/bootstrap")["user"])

    def test_access_revoked_while_calculating_cannot_return_result(self):
        def revoke(_payload):
            with self.auth.connection() as db:
                db.execute("UPDATE memberships SET role='revoked' WHERE organization_id=? AND user_id=?", (self.org, self.ids["student"]))
            return deepcopy(self.result)
        with patch("reading_only.calculate_fortune", side_effect=revoke):
            status, _, raw = self.call("POST", "/api/reading/fortune", FORM)
        self.assertEqual(status, 403)
        self.assertNotIn(b"star_data", raw)

    def test_failures_never_echo_or_log_personal_input(self):
        marker = "PRIVATE-NAME-BIRTH-1988-08-12"
        with patch("reading_only.calculate_fortune", side_effect=RuntimeError(marker)):
            with self.assertLogs("reading_only", level="ERROR") as logs:
                status, _, body = self.call("POST", "/api/reading/fortune", {**FORM, "name": marker})
        self.assertEqual(status, 500)
        self.assertNotIn(marker.encode(), body)
        self.assertNotIn(marker, " ".join(logs.output))

    def test_legacy_b2c_and_operator_surfaces_remain_available(self):
        os.environ["FORTUNE_DEPLOYMENT_SURFACE"] = "combined"
        self.app = self.inner
        self.app_patch.stop()
        self.app_patch = patch("auth_cases.api_app", return_value=self.app)
        self.app_patch.start()
        self.assertEqual(self.call("POST", "/api/fortune", FORM, "unknown")[0], 200)
        self.assertEqual(self.call("GET", "/api/operations/users", who="admin")[0], 200)
        self.assertEqual(self.call("GET", "/api/history", who="student")[0], 200)
        self.assertEqual(self.call("POST", "/api/reading/fortune", FORM)[0], 404)


def entitlement_case(state, expected):
    def verify(self):
        from security_scope_cases import SecurityScopeCases
        SecurityScopeCases.state(self, state)
        self.assertEqual(self.call("POST", "/api/reading/fortune", FORM)[0], expected)
        self.assertEqual(self.call("POST", "/api/reading/theme", {"theme_key": "red"})[0], expected)
        value = self.data("GET", "/api/reading/bootstrap")
        self.assertEqual(bool(value.get("branding")), expected == 200)
    return verify


for _state, _status in (("arrears", 403), ("terminated", 403), ("trial", 200), ("trial_ended", 403)):
    setattr(ReadingOnlyCases, "test_entitlement_" + _state, entitlement_case(_state, _status))


def expired_session(self):
    with self.auth.connection() as db:
        db.execute("UPDATE auth_sessions SET expires_at=0 WHERE user_id=?", (self.ids["student"],))
    self.assertEqual(self.call("POST", "/api/reading/fortune", FORM)[0], 401)
    self.assertEqual(self.call("POST", "/api/reading/theme", {"theme_key": "red"})[0], 401)
    self.assertIsNone(self.data("GET", "/api/reading/bootstrap")["user"])


ReadingOnlyCases.test_expired_session = expired_session


if __name__ == "__main__": unittest.main()
