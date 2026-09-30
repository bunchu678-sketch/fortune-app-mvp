"""Phase 4 persistence, identity, snapshot and API isolation tests (temporary DBs only)."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from history_repository import HistoryError, SQLiteHistoryRepository
from history_service import HistoryService, development_owner
from fortune_service import calculate_fortune
from tier_b import api_app, asgi_request

FORM = {
    "surname": "山田", "givenName": "太郎", "surnameKana": "ヤマダ", "givenNameKana": "たろう",
    "name": "山田太郎", "furigana": "ヤマダたろう", "birthDate": "1988-08-12", "birthTime": "09:00",
    "birthTimeUnknown": False, "gender": "男性", "birthPlace": "東京都", "readingDate": "2026-09-30",
    "includeGogyoVariants": True, "productAutoBoundary": True,
}


class HistoryCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = calculate_fortune(FORM)
        assert cls.result["ok"]

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = SQLiteHistoryRepository(Path(self.temp.name) / "history.sqlite3")
        self.service = HistoryService(self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def save(self, owner="one", memo="今回だけのメモ", link=None, **form):
        payload = {"input_snapshot": {"form": {**FORM, **form}, "manualChoices": {}, "boundarySelections": {}},
                   "result_snapshot": deepcopy(self.result), "memo": memo}
        if link:
            payload["link"] = link
        return self.service.create(owner, payload)

    def existing(self, reading, mode="existing_group"):
        return {"mode": mode, "person_id": reading["person_id"], "group_id": reading["group_id"],
                "source_reading_id": reading["id"]}

    def test_three_separate_ids_and_versions(self):
        row = self.save()
        self.assertEqual(len({row["id"], row["person_id"], row["group_id"]}), 3)
        self.assertTrue(row["app_version"] and row["calculation_logic_version"])
        self.assertEqual(row["data_schema_version"], 1)

    def test_candidate_normalization_and_optional_kana(self):
        self.save()
        rows = self.repo.candidates("one", {**FORM, "surname": "　山田 ", "givenName": " 太郎　", "surnameKana": ""})
        self.assertEqual(len(rows), 1)

    def test_candidate_nfkc(self):
        self.save(surname="Ａ", givenName="Ｂ")
        self.assertEqual(len(self.repo.candidates("one", {**FORM, "surname": "A", "givenName": "B"})), 1)

    def test_different_birth_and_partial_names_no_match(self):
        self.save()
        for values in ({"birthDate": "1988-08-13"}, {"surname": ""}, {"givenName": ""}):
            self.assertEqual(self.repo.candidates("one", {**FORM, **values}), [])

    def test_not_automatically_merged(self):
        self.save()
        with self.assertRaises(HistoryError) as error:
            self.save()
        self.assertEqual(error.exception.status, 409)

    def test_multiple_candidates_are_independent(self):
        one = self.save()
        two = self.save(link={"mode": "new_person"})
        self.assertNotEqual(one["person_id"], two["person_id"])
        self.assertEqual(len(self.repo.candidates("one", FORM)), 2)

    def test_existing_group_new_reading_and_no_memo_copy(self):
        one = self.save(memo="前回")
        two = self.save(memo="今回", link=self.existing(one))
        self.assertEqual(one["person_id"], two["person_id"])
        self.assertEqual(one["group_id"], two["group_id"])
        self.assertNotEqual(one["id"], two["id"])
        self.assertEqual(two["memo"], "今回")
        self.assertEqual(self.repo.memos("one", one["group_id"], two["id"])[0]["memo"], "前回")

    def test_new_group_isolates_memos(self):
        one = self.save()
        two = self.save(link=self.existing(one, "new_group"))
        self.assertEqual(one["person_id"], two["person_id"])
        self.assertNotEqual(one["group_id"], two["group_id"])
        self.assertEqual(self.repo.memos("one", two["group_id"], two["id"]), [])

    def test_person_update_does_not_mutate_snapshots(self):
        row = self.save()
        self.repo.update_person("one", row["person_id"], {"form": {**FORM, "surname": "変更姓", "birthTime": "10:00"}})
        after = self.repo.detail("one", row["id"])
        self.assertEqual(after["input_snapshot"], row["input_snapshot"])
        self.assertEqual(after["result_snapshot"], row["result_snapshot"])
        self.assertEqual(self.service.prepare("one", row["id"], "new_group")["form"]["surname"], "変更姓")

    def test_snapshot_is_independent_and_never_calculated(self):
        row = self.save()
        with patch("fortune_service.calculate_fortune", side_effect=AssertionError("no recalculation")):
            self.assertEqual(self.service.detail("one", row["id"])["result_snapshot"], self.result)
        self.result["ok"] = False
        try:
            self.assertTrue(self.repo.detail("one", row["id"])["result_snapshot"]["ok"])
        finally:
            self.result["ok"] = True

    def test_memo_update_only_memo_and_updated_time(self):
        one = self.save()
        two = self.repo.update_memo("one", one["id"], "変更後", one["updated_at"])
        for key in ("input_snapshot", "result_snapshot", "saved_at", "person_id", "group_id"):
            self.assertEqual(two[key], one[key])
        self.assertEqual(two["memo"], "変更後")
        self.assertNotEqual(two["updated_at"], one["updated_at"])

    def test_memo_concurrent_conflict(self):
        one = self.save()
        self.repo.update_memo("one", one["id"], "先に変更", one["updated_at"])
        with self.assertRaises(HistoryError) as error:
            self.repo.update_memo("one", one["id"], "古い画面", one["updated_at"])
        self.assertEqual(error.exception.status, 409)

    def test_list_saved_order_not_reading_date(self):
        one = self.save(readingDate="2030-01-01")
        two = self.save(readingDate="2020-01-01", link=self.existing(one))
        self.assertEqual([x["id"] for x in self.repo.list("one")], [two["id"], one["id"]])

    def test_search_fields_and_period(self):
        one = self.save()
        for query in ("山田", "太郎", "山田太郎", "山田 太郎", "ヤマダ", "たろう", "1988-08-12"):
            self.assertEqual(self.repo.list("one", query)[0]["id"], one["id"])
        self.assertEqual(self.repo.list("one", start="2026-10-01"), [])
        self.assertEqual(self.repo.list("one", end="2026-09-29"), [])
        self.assertEqual(len(self.repo.list("one", start="2026-09-30", end="2026-09-30")), 1)

    def test_search_uses_contemporaneous_name(self):
        row = self.save()
        self.repo.update_person("one", row["person_id"], {"form": {**FORM, "surname": "別姓"}})
        self.assertEqual(len(self.repo.list("one", "山田")), 1)
        self.assertEqual(self.repo.list("one", "別姓"), [])

    def test_sql_injection_is_literal(self):
        self.save()
        self.assertEqual(self.repo.list("one", "' OR 1=1 --"), [])

    def test_soft_deleted_not_listed_or_opened_or_reused(self):
        row = self.save()
        self.repo.soft_delete("one", row["id"])
        self.assertEqual(self.repo.list("one"), [])
        self.assertEqual(self.repo.candidates("one", FORM), [])
        self.assertEqual(self.repo.memos("one", row["group_id"]), [])
        with self.assertRaises(HistoryError):
            self.repo.detail("one", row["id"])
        with self.repo.connection() as db:
            deleted = db.execute("SELECT deleted_at FROM readings WHERE id=?", (row["id"],)).fetchone()
            self.assertTrue(deleted["deleted_at"])

    def test_owner_read_list_candidate_memo_isolation(self):
        row = self.save()
        self.assertEqual(self.repo.list("two"), [])
        self.assertEqual(self.repo.candidates("two", FORM), [])
        for fn in (lambda: self.repo.detail("two", row["id"]),
                   lambda: self.repo.memos("two", row["group_id"]),
                   lambda: self.repo.update_memo("two", row["id"], "侵入", row["updated_at"]),
                   lambda: self.repo.soft_delete("two", row["id"]),
                   lambda: self.service.prepare("two", row["id"], "existing_group"),
                   lambda: self.repo.update_person("two", row["person_id"], {"form": FORM})):
            with self.assertRaises(HistoryError):
                fn()

    def test_owner_link_isolation_and_rollback(self):
        one = self.save()
        with self.assertRaises(HistoryError):
            self.save(owner="two", link=self.existing(one))
        self.assertEqual(self.repo.list("two"), [])

    def test_wrong_group_person_and_source_rejected(self):
        one = self.save()
        two = self.save(link={"mode": "new_person"})
        for link in ({**self.existing(one), "group_id": two["group_id"]},
                     {**self.existing(one), "source_reading_id": two["id"]}):
            with self.assertRaises(HistoryError):
                self.save(link=link)
        self.assertEqual(len(self.repo.list("one")), 2)

    def test_rerun_today_and_input_and_memos(self):
        one = self.save()
        for mode in ("existing_group", "new_group"):
            draft = self.service.prepare("one", one["id"], mode)
            today = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
            self.assertEqual(draft["form"]["readingDate"], today)
            for key in ("surname", "givenName", "surnameKana", "givenNameKana", "birthDate", "birthTime",
                        "birthTimeUnknown", "gender", "birthPlace"):
                self.assertEqual(draft["form"][key], FORM[key])
            self.assertEqual(len(draft["pastMemos"]), 1 if mode == "existing_group" else 0)
        self.assertEqual(self.repo.detail("one", one["id"]), one)

    def test_rerun_birth_override_only(self):
        payload = {"input_snapshot": {"form": FORM, "manualChoices": {"birth": "before", "reading": "after"},
                   "boundarySelections": {"birth": {"choice": "before", "boundary_datetime": "2020-02-04T18:03:00"},
                                          "reading": {"choice": "after", "boundary_datetime": "2020-02-04T18:03:00"}}},
                   "result_snapshot": self.result}
        row = self.service.create("one", payload)
        draft = self.service.prepare("one", row["id"], "new_group")
        self.assertEqual(draft["manualChoices"], {"birth": "before"})
        self.assertEqual(list(draft["boundarySelections"]), ["birth"])

    def test_persistence_across_repository_restart(self):
        row = self.save()
        self.assertEqual(SQLiteHistoryRepository(self.repo.path).detail("one", row["id"]), row)

    def test_no_name_no_kana_no_auto_match(self):
        row = self.save(surname="", givenName="", surnameKana="", givenNameKana="", name="無記名")
        self.assertEqual(self.repo.list("one")[0]["name"], "無記名")
        self.assertEqual(self.repo.candidates("one", row["input_snapshot"]["form"]), [])

    def test_split_name_does_not_change_calculation(self):
        one = calculate_fortune(FORM)
        two = calculate_fortune({**FORM, "name": "別名", "surname": "変更", "givenName": "名前", "furigana": "自由ABC"})
        for key in ("meishiki", "star_data", "gogyo_variants", "personality", "daiun", "yearly_flow", "yearly_overall"):
            self.assertEqual(one[key], two[key])

    def test_invalid_payload_rolls_back(self):
        for payload in ({}, {"input_snapshot": {"form": FORM}, "result_snapshot": {"ok": False}},
                        {"input_snapshot": {"form": {**FORM, "birthDate": "bad"}}, "result_snapshot": self.result}):
            with self.assertRaises(HistoryError):
                self.service.create("one", payload)
        self.assertEqual(self.repo.list("one"), [])

    def test_invalid_snapshot_corrections_are_rejected(self):
        for values in ({"manualChoices": None}, {"manualChoices": {"birth": "unknown"}},
                       {"boundarySelections": {"birth": {"choice": "before", "boundary_datetime": "bad"}}},
                       {"manualChoices": {"birth": "before"},
                        "boundarySelections": {"birth": {"choice": "after", "boundary_datetime": "2020-02-04T18:03:00"}}}):
            with self.assertRaises(HistoryError):
                self.service.create("one", {"input_snapshot": {"form": FORM, **values}, "result_snapshot": self.result})
        self.assertEqual(self.repo.list("one"), [])

    def test_storage_error_returns_safe_json(self):
        with patch.dict(os.environ, {"FORTUNE_ENV": "development", "FORTUNE_HISTORY_DEV_USER_ID": "one",
                                    "FORTUNE_HISTORY_DB_PATH": self.temp.name}):
            with patch("logging.Logger.exception"):
                status, body = asyncio.run(asgi_request(api_app(), "GET", "/api/history"))
            self.assertEqual(status, 503)
            self.assertEqual(body["error"], "履歴の保存先を利用できません。設定を確認してください。")

    def test_production_disabled_even_with_dev_user(self):
        with patch.dict(os.environ, {"FORTUNE_ENV": "production", "FORTUNE_HISTORY_DEV_USER_ID": "local"}, clear=True):
            with self.assertRaises(HistoryError) as error:
                development_owner()
            self.assertEqual(error.exception.status, 503)

    def test_no_implicit_development_owner(self):
        for env in ({}, {"FORTUNE_ENV": "development"}, {"FORTUNE_HISTORY_DEV_USER_ID": "local"}):
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(HistoryError):
                    development_owner()

    def test_api_create_detail_memo_delete_no_calculation(self):
        env = {"FORTUNE_ENV": "development", "FORTUNE_HISTORY_DEV_USER_ID": "one",
               "FORTUNE_HISTORY_DB_PATH": str(self.repo.path)}
        def request(method, route, payload=None):
            return asyncio.run(asgi_request(api_app(), method, "/api/history"+route,
                                            json.dumps(payload or {}).encode()))
        with patch.dict(os.environ, env):
            status, body = request("POST", "", {"input_snapshot": {"form": FORM, "manualChoices": {}},
                                    "result_snapshot": self.result, "memo": "APIメモ", "user_id": "two"})
            self.assertEqual(status, 200)
            row = body["data"]
            self.assertEqual(row["owner_user_id"], "one")
            with patch("fortune_service.calculate_fortune", side_effect=AssertionError("calculation forbidden")):
                status, body = request("GET", "/" + row["id"])
                self.assertEqual(status, 200)
                self.assertEqual(body["data"]["result_snapshot"], self.result)
            status, body = request("PATCH", "/"+row["id"]+"/memo", {"memo": "更新", "updated_at": row["updated_at"]})
            self.assertEqual(status, 200)
            self.assertEqual(body["data"]["memo"], "更新")
            status, body = request("POST", "/"+row["id"]+"/rerun", {"mode": "new_group", "user_id": "two"})
            self.assertEqual(status, 200)
            self.assertEqual(body["data"]["pastMemos"], [])
            self.assertEqual(request("DELETE", "/"+row["id"])[0], 200)
            self.assertEqual(request("GET", "/"+row["id"])[0], 404)

    def test_api_foreign_owner_and_invalid_configuration(self):
        row = self.save()
        with patch.dict(os.environ, {"FORTUNE_ENV": "development", "FORTUNE_HISTORY_DEV_USER_ID": "two",
                                    "FORTUNE_HISTORY_DB_PATH": str(self.repo.path)}):
            status, body = asyncio.run(asgi_request(api_app(), "GET", "/api/history/" + row["id"]))
            self.assertEqual(status, 404)
        with patch.dict(os.environ, {"FORTUNE_ENV": "production", "FORTUNE_HISTORY_DEV_USER_ID": "one"}):
            self.assertEqual(asyncio.run(asgi_request(api_app(), "GET", "/api/history"))[0], 503)


if __name__ == "__main__":
    unittest.main(verbosity=2)
