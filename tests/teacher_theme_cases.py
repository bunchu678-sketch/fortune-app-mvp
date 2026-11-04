"""Disposable database tests for Mari presentation and authenticated preferences."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import json
import tempfile
import unittest
from auth_service import AuthRepository
from product_repository import ProductRepository
from teacher_presentation import THREE_GROUPS, MARI_THEMES
from fortune_data import JUUNI_UNSEI_PILLAR_WEIGHTS, JUUNI_UNSEI_THINKING_TENDENCY
from comments import JUUNI_UNSEI_COMMENTS
from history_repository import HistoryError
from product_api_cases import ProductAPICases


class TeacherThemeCases(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "theme.sqlite3"
        auth = AuthRepository(self.path)
        self.a = auth.create_user("a@example.test", "synthetic-password-1234")["id"]
        self.b = auth.create_user("b@example.test", "synthetic-password-1234")["id"]
        self.repo = ProductRepository(self.path)
        self.org = self.repo.create_organization("先生版", "mari-mutsuro")["id"]
        self.other = self.repo.create_organization("博士版検証", "other")["id"]
        for org in (self.org, self.other):
            self.repo.add_membership(org, self.a, "teacher")
        self.repo.add_membership(self.org, self.b, "student")

    def tearDown(self): self.temp.cleanup()

    def test_read_has_four_themes_without_writing(self):
        with self.repo.auth.connection() as db: before = db.iterdump(); before = list(before)
        value = self.repo.branding(self.org, self.a)
        self.assertEqual([t["key"] for t in value["themes"]], ["default", "red", "blue", "black"])
        self.assertEqual(value["selected_theme_key"], "default")
        with self.repo.auth.connection() as db: self.assertEqual(list(db.iterdump()), before)

    def test_selection_persists_per_user_and_org(self):
        for key in MARI_THEMES:
            self.repo.select_theme(self.org, self.a, key)
            fresh = ProductRepository(self.path)
            self.assertEqual(fresh.branding(self.org, self.a)["selected_theme_key"], key)
            self.assertEqual(fresh.branding(self.org, self.b)["selected_theme_key"], "default")
            self.assertEqual(fresh.branding(self.other, self.a)["selected_theme_key"], "default")

    def test_other_brand_and_invalid_selection_unchanged(self):
        self.assertNotIn("presentation_mode", self.repo.branding(self.other, self.a))
        for org, user, key in ((self.other, self.a, "red"), (self.other, self.b, "default"), (self.org, self.a, "missing")):
            with self.assertRaises(HistoryError): self.repo.select_theme(org, user, key)

    def test_organization_can_limit_themes(self):
        with self.repo.auth.connection() as db:
            db.execute("UPDATE organizations SET settings_json=? WHERE id=?", (json.dumps({"available_theme_keys": ["blue"]}), self.org))
        self.assertEqual([t["key"] for t in self.repo.branding(self.org, self.a)["themes"]], ["default", "blue"])
        with self.assertRaises(HistoryError): self.repo.select_theme(self.org, self.a, "red")

    def test_custom_definition_preserved(self):
        self.repo.add_theme(self.org, "blue", "教室の青", {"accent": "#123456"})
        self.repo.select_theme(self.org, self.a, "blue")
        selected = next(t for t in self.repo.branding(self.org, self.a)["themes"] if t["key"] == "blue")
        self.assertEqual(selected["display_name"], "教室の青")
        self.assertEqual(selected["definition"]["accent"], "#123456")

    def test_all_twelve_classifications_and_legacy_unchanged(self):
        self.assertEqual(THREE_GROUPS, {star: data["group"] for star, data in JUUNI_UNSEI_COMMENTS.items()})
        self.assertEqual(len(THREE_GROUPS), 12)
        self.assertEqual([THREE_GROUPS[s] for s in ("胎", "養", "絶")], ["地球", "月", "太陽"])
        self.assertEqual([JUUNI_UNSEI_THINKING_TENDENCY[s]["three_group"] for s in ("胎", "養", "絶")], ["月", "太陽", "地球"])
        self.assertEqual(JUUNI_UNSEI_PILLAR_WEIGHTS, {"year": 15, "month": 30, "day": 50, "hour": 5})


class TeacherThemeAPICases(unittest.TestCase):
    setUpClass = classmethod(ProductAPICases.setUpClass.__func__)
    setUp = ProductAPICases.setUp
    tearDown = ProductAPICases.tearDown
    call = ProductAPICases.call
    data = ProductAPICases.data

    def test_theme_save_relogin_csrf_and_isolation(self):
        with self.auth.connection() as db: db.execute("UPDATE organizations SET slug='mari-mutsuro' WHERE id=?", (self.org,))
        path = f"/api/b2b/organizations/{self.org}/theme"
        for key in MARI_THEMES:
            value = self.data("POST", path, {"theme_key": key})
            self.assertEqual(value["selected_theme_key"], key)
        self.auth.logout(self.cookies["student"])
        self.cookies["student"] = self.auth.login("student@example.test", "synthetic-password-1234")[1]
        self.assertEqual(self.data("GET", f"/api/b2b/organizations/{self.org}/me")["branding"]["selected_theme_key"], "black")
        self.assertEqual(self.call("POST", path, {"theme_key": "red"}, origin="https://evil.example.test")[0], 403)
        self.assertNotEqual(self.call("POST", path, {"theme_key": "red"}, who="other")[0], 200)
        self.assertNotEqual(self.call("POST", path, {"theme_key": "red"}, who="unknown")[0], 200)
        self.assertEqual(self.data("GET", f"/api/b2b/organizations/{self.org}/me", who="teacher")["branding"]["selected_theme_key"], "default")


if __name__ == "__main__": unittest.main()
