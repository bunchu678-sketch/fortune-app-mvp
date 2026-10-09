"""Approved K01/K03 regression: frozen pre-change evidence; synthetic isolated DBs only."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from copy import deepcopy
from contextlib import closing
from dataclasses import asdict
from datetime import date
import hashlib
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import comments
from fortune_service import calculate_fortune
from history_cases import FORM
from history_repository import SQLiteHistoryRepository, HistoryError
from history_service import HistoryService
from yearly_overall_logic import build_yearly_overall_fortune
from yearly_overall_comments import YEARLY_OVERALL_COMMENTS, interpretation_fields, registration_inventory, UNREGISTERED_MESSAGE
from reading_snapshot import public_result_snapshot
from report_data import build_reading_report
from report_export_service import ExportTokens, export_reading
from report_pdf import export_pdf_reading
from report_pdf_cases import RecordingConverter
from report_export_cases import unpack, sheet_cells
from research import run_migrate_test_history as migration
from product_api_cases import ProductAPICases

BASELINE = json.loads((ROOT / "tests/fixtures/k01_k03_baseline.json").read_text(encoding="utf-8"))
STARS = tuple(BASELINE["year2026"])


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        default=lambda x: sorted(x), separators=(",", ":")).encode()).hexdigest()


def private_keys(value):
    if isinstance(value, dict):
        return sum(k in ("outer_private_comment", "inner_private_comment", "private_comment", "private") for k in value) + sum(private_keys(v) for v in value.values())
    if isinstance(value, list):
        return sum(private_keys(v) for v in value)
    return 0


def old_result(year=2026):
    result = calculate_fortune({**FORM, "readingDate": f"{year}-09-30"})
    for row in result["personality"]["life_stage_tsuhensei"]:
        row.update(outer_private_comment="SYNTHETIC_PRIVATE", inner_private_comment="SYNTHETIC_PRIVATE")
    result["personality"]["month_pair"]["private_comment"] = "SYNTHETIC_PRIVATE"
    for row in result["personality"]["juuni_unsei"]["rows"]:
        row["private_comment"] = "SYNTHETIC_PRIVATE"
    annual = result["yearly_overall"]
    for key in list(annual):
        if key.startswith("interpretation_"): annual.pop(key)
    annual.update(BASELINE["year2026"][annual["tsuhensei"]])
    return result


class InterpretationCases(unittest.TestCase):
    def test_registered_2026_all_stars(self):
        found = set()
        for stem in "甲乙丙丁戊己庚辛壬癸":
            value = build_yearly_overall_fortune(date(2026, 9, 30), stem)
            found.add(value["tsuhensei"])
            self.assertTrue(value["ok"])
            self.assertEqual(value["interpretation_status"], "registered")
            self.assertEqual(value["interpretation_version"], "2026.1")
            self.assertEqual(value["interpretation_author"], "無津呂麻理")
        self.assertEqual(found, set(STARS))

    def test_missing_years_all_stars(self):
        for year in (2025, 2027, 2028):
            for stem in "甲乙丙丁戊己庚辛壬癸":
                value = build_yearly_overall_fortune(date(year, 9, 30), stem)
                self.assertTrue(value["ok"])
                self.assertTrue(value["year_kanchi"] and value["tsuhensei"])
                self.assertEqual((value["theme"], value["comment"], value["error"]), ("", "", ""))
                self.assertEqual(value["interpretation_status"], "unregistered")
                self.assertEqual(value["interpretation_version"], "")
                self.assertEqual(value["interpretation_message"], UNREGISTERED_MESSAGE)

    def test_missing_star_no_fallback(self):
        with patch.dict(YEARLY_OVERALL_COMMENTS[2026]["stars"], {}, clear=True):
            value = build_yearly_overall_fortune(date(2026, 9, 30), "己")
            self.assertTrue(value["ok"])
            self.assertEqual(value["comment"], "")
            self.assertEqual(value["interpretation_status"], "unregistered")

    def test_incomplete_star_no_partial_text(self):
        with patch.dict(YEARLY_OVERALL_COMMENTS[2026]["stars"]["印綬"], {"comment": ""}):
            self.assertEqual(interpretation_fields(2026, "印綬")["theme"], "")
            self.assertEqual(interpretation_fields(2026, "印綬")["interpretation_status"], "unregistered")

    def test_calculation_failure_is_not_missing_manuscript(self):
        value = build_yearly_overall_fortune(date(2026, 9, 30), "己", {"ok": False})
        self.assertFalse(value["ok"])
        self.assertTrue(value["error"])
        self.assertFalse(value.get("interpretation_message"))

    def test_inventory_ten_stars_and_revision(self):
        rows = registration_inventory()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["year"], 2026)
        self.assertEqual(rows[0]["version"], "2026.1")
        self.assertEqual(rows[0]["stars"], dict.fromkeys(STARS, "registered"))
        with patch.dict(YEARLY_OVERALL_COMMENTS[2026]["stars"], {}, clear=True):
            self.assertEqual(registration_inventory()[0]["stars"], dict.fromkeys(STARS, "unregistered"))

    def test_inventory_invalid_metadata_rejected(self):
        with patch.dict(YEARLY_OVERALL_COMMENTS[2026], {"version": ""}):
            with self.assertRaises(ValueError): registration_inventory()

    def test_public_dictionaries_exactly_preserved_and_122_private_removed(self):
        values = {name: getattr(comments, name) for name in ("TSUHENSEI_COMMENTS", "MONTH_TSUHENSEI_PAIR_COMMENTS", "JUUNI_UNSEI_COMMENTS")}
        self.assertEqual([len(v) for v in values.values()], [10, 100, 12])
        self.assertEqual(sum(len(v) for v in values.values()), 122)
        self.assertEqual(private_keys(values), 0)
        self.assertEqual(digest(values), BASELINE["public_digest"])

    def test_new_result_no_private_and_memo_structure_preserved(self):
        result = calculate_fortune(FORM)
        self.assertEqual(private_keys(result), 0)
        for row in result["personality"]["life_stage_tsuhensei"]:
            self.assertIn("outer_comment", row); self.assertIn("inner_comment", row)
        self.assertIn("public_comment", result["personality"]["current_life_stage_pair"])
        self.assertIn("month_pair", result["personality"])
        for row in result["personality"]["juuni_unsei"]["rows"]:
            self.assertIn("public_comment", row); self.assertIn("reading_points", row)
        page = (ROOT / "fortune-next-app/app/main-fortune.tsx").read_text(encoding="utf-8")
        for required in ("鑑定者用メモ", "未設定", "pastMemos", "gogyo?.details", "interpretation_message"):
            self.assertIn(required, page)
        self.assertIn("interpretation_message", (ROOT / "fortune-next-app/app/product/result/page.tsx").read_text(encoding="utf-8"))

    def test_legacy_projection_is_narrow_and_input_not_mutated(self):
        old = old_result(2027); copy = deepcopy(old)
        old["other_data"] = {"memo": "privateという自由文", "other_private_setting": True}
        new = public_result_snapshot(old)
        self.assertEqual(private_keys(new), 0)
        self.assertEqual(new["other_data"], old["other_data"])
        self.assertEqual(private_keys(old), 13)
        self.assertEqual(old["yearly_overall"], copy["yearly_overall"])
        self.assertEqual(new["yearly_overall"]["comment"], "")

    def test_2026_report_entirely_unchanged(self):
        result = calculate_fortune(FORM)
        self.assertEqual(digest(asdict(build_reading_report(FORM, result))), BASELINE["report2026"])

    def test_missing_year_excel_pdf_completed_workbook(self):
        form = {**FORM, "readingDate": "2027-09-30"}; result = calculate_fortune(form)
        tokens = ExportTokens(); token = tokens.issue("synthetic", form, result)
        _, xlsx = export_reading("synthetic", {"export_token": token}, tokens=tokens)
        parts = unpack(xlsx); cells = sheet_cells(parts)
        self.assertEqual(cells["L60"], "2027")
        self.assertEqual(cells.get("G61", ""), "")
        raw = b"".join(parts.values())
        self.assertIn(UNREGISTERED_MESSAGE.encode(), raw)
        self.assertNotIn("2026年行動アドバイス".encode(), raw)
        adapter = RecordingConverter()
        export_pdf_reading("synthetic", {"export_token": token}, tokens=tokens, converter=adapter)
        self.assertEqual(unpack(adapter.inputs[0]), parts)


for index, star in enumerate(STARS):
    def text_case(self, star=star):
        actual = YEARLY_OVERALL_COMMENTS[2026]["stars"][star]
        self.assertEqual(actual, BASELINE["year2026"][star])
    setattr(InterpretationCases, f"test_2026_original_{index:02}", text_case)
for index, (day, expected) in enumerate(BASELINE["calculations"].items()):
    def calculation_case(self, day=day, expected=expected):
        value = calculate_fortune({**FORM, "readingDate": day})
        annual = value["yearly_overall"]
        for key in list(annual):
            if key in ("theme", "comment") or key.startswith("interpretation_"): annual.pop(key)
        self.assertEqual(digest(value), expected)
    setattr(InterpretationCases, f"test_calculation_unchanged_{index:02}", calculation_case)


class SnapshotMigrationCases(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.path = Path(self.temp.name) / "synthetic.sqlite3"
        self.repo = SQLiteHistoryRepository(self.path); self.service = HistoryService(self.repo)
        self.one = self.service.create("synthetic", {"input_snapshot": {"form": FORM}, "result_snapshot": calculate_fortune(FORM), "memo": "自由メモ private"})
        link = {"mode": "existing_group", "person_id": self.one["person_id"], "group_id": self.one["group_id"], "source_reading_id": self.one["id"]}
        self.two = self.service.create("synthetic", {"input_snapshot": {"form": {**FORM, "readingDate": "2027-09-30"}}, "result_snapshot": calculate_fortune({**FORM, "readingDate": "2027-09-30"}), "link": link, "memo": "別メモ"})
        with self.repo.connection() as db:
            db.execute("CREATE TABLE reading_organization_scopes(reading_id TEXT PRIMARY KEY REFERENCES readings(id), organization_id TEXT, owner_user_id TEXT)")
            db.execute("INSERT INTO reading_organization_scopes VALUES (?,?,?)", (self.one["id"], "synthetic-org", "synthetic"))
            for row, year in ((self.one, 2026), (self.two, 2027)):
                db.execute("UPDATE readings SET result_snapshot=?,data_schema_version=1 WHERE id=?", (json.dumps(old_result(year), ensure_ascii=False), row["id"]))
            db.execute("UPDATE readings SET deleted_at=saved_at WHERE id=?", (self.two["id"],))
        with closing(sqlite3.connect(self.path)) as db: self.before = migration.state(db)
    def tearDown(self): self.temp.cleanup()

    def test_dry_run_does_not_modify_bytes(self):
        before = self.path.read_bytes()
        result = migration.migrate(self.path, test_data_confirmed=True)
        self.assertEqual(result["changed"], 2); self.assertEqual(self.path.read_bytes(), before)

    def test_apply_all_rows_backup_integrity_retained_fields_and_idempotency(self):
        result = migration.migrate(self.path, Path(self.temp.name) / "backup", True, True)
        self.assertEqual(result["changed"], 2)
        with closing(sqlite3.connect(result["backup"])) as db: self.assertEqual(migration.state(db), self.before)
        with closing(sqlite3.connect(self.path)) as db:
            migration.check_integrity(db)
            columns = [r[1] for r in db.execute("PRAGMA table_info(readings)")]
            after = migration.state(db)
            updates = [(r[columns.index("result_snapshot")], r[columns.index("data_schema_version")], r[columns.index("id")]) for r in after["readings"]]
            migration.verify_unchanged(self.before, after, columns, updates)
            for row in after["readings"]:
                value = json.loads(row[columns.index("result_snapshot")])
                self.assertEqual(private_keys(value), 0)
                self.assertEqual(row[columns.index("data_schema_version")], 2)
                year = value["yearly_overall"]
                if year["year"] == 2026:
                    self.assertEqual({k: year[k] for k in ("theme", "comment")}, BASELINE["year2026"][year["tsuhensei"]])
                else: self.assertEqual(year["comment"], "")
                old = next(json.loads(r[columns.index("result_snapshot")]) for r in self.before["readings"] if r[columns.index("id")] == row[columns.index("id")])
                for key in value:
                    if key not in ("personality", "yearly_overall"): self.assertEqual(value[key], old[key])
        again = migration.migrate(self.path, Path(self.temp.name) / "backup", True, True)
        self.assertEqual(again["changed"], 0); self.assertIsNone(again["backup"])

    def test_failed_verification_rolls_back(self):
        with patch.object(migration, "verify_unchanged", side_effect=ValueError("synthetic verification failure")):
            with self.assertRaises(ValueError): migration.migrate(self.path, Path(self.temp.name) / "backup", True, True)
        with closing(sqlite3.connect(self.path)) as db: self.assertEqual(migration.state(db), self.before)

    def test_missing_test_confirmation_and_repository_backup_rejected(self):
        with self.assertRaises(ValueError): migration.migrate(self.path)
        with self.assertRaises(ValueError): migration.migrate(self.path, ROOT / "data", True, True)

    def test_old_read_memo_restore_and_search_safe_without_db_rewrite(self):
        row = self.service.detail("synthetic", self.one["id"])
        self.assertEqual(private_keys(row["result_snapshot"]), 0)
        self.assertEqual(row["memo"], "自由メモ private")
        changed = self.repo.update_memo("synthetic", row["id"], "追記", row["updated_at"])
        self.assertEqual(private_keys(changed["result_snapshot"]), 0)
        self.assertEqual(len(self.repo.list("synthetic")), 1)
        self.repo.restore("synthetic", self.two["id"])
        self.assertEqual(self.service.detail("synthetic", self.two["id"])["result_snapshot"]["yearly_overall"]["comment"], "")
        with self.assertRaises(HistoryError): self.service.detail("another", self.one["id"])

    def test_versioned_snapshot_and_revision_frozen_on_registry_update(self):
        row = self.service.create("new", {"input_snapshot": {"form": FORM}, "result_snapshot": calculate_fortune(FORM)})
        with patch.dict(YEARLY_OVERALL_COMMENTS[2026], {"version": "SYNTHETIC_NEW_REVISION"}):
            fetched = self.service.detail("new", row["id"])
            self.assertEqual(fetched["result_snapshot"], row["result_snapshot"])
            self.assertEqual(fetched["result_snapshot"]["yearly_overall"]["interpretation_version"], "2026.1")
        draft = self.service.prepare("new", row["id"], "existing_group")
        self.assertEqual(draft["link"]["source_reading_id"], row["id"])
        new_result = calculate_fortune(draft["form"])
        new = self.service.create("new", {"input_snapshot": {"form": draft["form"]}, "result_snapshot": new_result, "link": draft["link"]})
        self.assertNotEqual(new["id"], row["id"]); self.assertEqual(private_keys(new["result_snapshot"]), 0)


class K01K03APICases(unittest.TestCase):
    setUp = ProductAPICases.setUp
    tearDown = ProductAPICases.tearDown
    call = ProductAPICases.call
    data = ProductAPICases.data
    fortune = ProductAPICases.fortune
    @classmethod
    def setUpClass(cls): cls.result = calculate_fortune(FORM)

    def test_b2c_anonymous_and_authenticated_no_private(self):
        for who in (None, "b2c", "admin", "teacher", "student"):
            status, _, body = self.call("POST", "/api/fortune", {**FORM, "readingDate": "2027-09-30"}, who=who)
            self.assertEqual(status, 200)
            value = json.loads(body); self.assertEqual(private_keys(value), 0)
            self.assertEqual(value["yearly_overall"]["interpretation_status"], "unregistered")

    def test_b2b_teacher_student_no_private_and_unregistered(self):
        for who in ("teacher", "student"):
            status, _, body = self.fortune(who=who, payload={**FORM, "readingDate": "2027-09-30"})
            self.assertEqual(status, 200, body)
            value = json.loads(body)
            self.assertEqual(private_keys(value), 0)
            self.assertEqual(value["yearly_overall"]["comment"], "")

    def test_stale_client_save_detail_memo_and_storage_no_private_b2c_b2b(self):
        for who, org in (("b2c", None), ("student", self.org)):
            payload = {"input_snapshot": {"form": FORM}, "result_snapshot": old_result(), "memo": "SYNTHETIC_FREE_MEMO", "link": {"mode": "new_person"}}
            if org: payload["organization_id"] = org
            row = self.data("POST", "/api/history", payload, who=who)
            self.assertEqual(private_keys(row["result_snapshot"]), 0)
            detail = self.data("GET", f"/api/history/{row['id']}", who=who)
            self.assertEqual(detail["memo"], "SYNTHETIC_FREE_MEMO")
            self.assertEqual(detail["result_snapshot"]["yearly_overall"]["interpretation_version"], "2026.1")
            changed = self.data("PATCH", f"/api/history/{row['id']}/memo", {"memo": "SYNTHETIC_UPDATED", "updated_at": detail["updated_at"]}, who=who)
            self.assertEqual(private_keys(changed["result_snapshot"]), 0)
            with self.ops.product.history.connection() as db:
                raw = db.execute("SELECT result_snapshot FROM readings WHERE id=?", (row["id"],)).fetchone()[0]
                self.assertEqual(private_keys(json.loads(raw)), 0)

    def test_unmigrated_snapshot_cannot_expose_private_and_authorization_maintained(self):
        with self.ops.product.history.connection() as db:
            db.execute("UPDATE readings SET result_snapshot=? WHERE id=?", (json.dumps(old_result(2027)), self.reading["id"]))
        value = self.data("GET", f"/api/history/{self.reading['id']}")
        self.assertEqual(private_keys(value["result_snapshot"]), 0)
        self.assertEqual(value["result_snapshot"]["yearly_overall"]["comment"], "")
        for who in (None, "teacher", "admin", "other", "b2c"):
            self.assertEqual(self.call("GET", f"/api/history/{self.reading['id']}", who=who)[0], 401 if who is None else 404)
        for who, org, expected in ((None, self.org, 401), ("admin", self.org, 404), ("other", self.org, 404), ("student", self.second, 404)):
            self.assertEqual(self.fortune(who=who, org=org)[0], expected)

# Do not discover the imported existing suite twice.
del ProductAPICases

def formal_cases():
    for name in unittest.defaultTestLoader.getTestCaseNames(InterpretationCases):
        def check(name=name):
            case = InterpretationCases(name)
            getattr(case, name)()
        yield "A-K01-K03-" + name.removeprefix("test_"), check

if __name__ == "__main__": unittest.main(verbosity=2)
