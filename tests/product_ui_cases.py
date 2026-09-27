"""Product-only API additions and legacy compatibility checks."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fortune_service import calculate_fortune
from fortune_core_logic import get_month_pair_comment


BASE = {
    "birthDate": "2020-02-04", "birthTime": "18:03", "birthPlace": "未選択",
    "readingDate": "2026-09-27", "includeGogyoVariants": True,
}


class ProductServiceCases(unittest.TestCase):
    def test_legacy_birth_still_requires_confirmation(self):
        result = calculate_fortune(BASE)
        self.assertTrue(result["confirmation_required"])
        self.assertEqual(result["boundary_confirmations"][0]["kind"], "birth")

    def test_product_birth_auto_uses_existing_pillars(self):
        product = calculate_fortune({**BASE, "productAutoBoundary": True})
        self.assertTrue(product["ok"])
        boundary = product["calendar"]["auto_boundaries"][0]
        self.assertEqual(boundary["choice"], "after")
        explicit = calculate_fortune({**BASE, "boundarySelections": {"birth": {
            "boundary_datetime": boundary["boundary_datetime"], "choice": "after",
        }}})
        self.assertEqual(product["meishiki"], explicit["meishiki"])

    def test_product_manual_birth_overrides_auto(self):
        auto = calculate_fortune({**BASE, "productAutoBoundary": True})
        boundary = auto["calendar"]["auto_boundaries"][0]
        before = calculate_fortune({**BASE, "productAutoBoundary": True, "boundarySelections": {"birth": {
            "boundary_datetime": boundary["boundary_datetime"], "choice": "before",
        }}})
        self.assertTrue(before["ok"])
        self.assertNotEqual(before["meishiki"]["year"], auto["meishiki"]["year"])
        self.assertNotEqual(before["meishiki"]["month"], auto["meishiki"]["month"])

    def test_reading_risshun_is_product_only_auto(self):
        payload = {**BASE, "birthDate": "1988-08-12", "birthTime": "09:00", "readingDate": "2020-02-04"}
        self.assertTrue(calculate_fortune({**payload, "includeGogyoVariants": False})["confirmation_required"])
        product = calculate_fortune({**payload, "productAutoBoundary": True})
        self.assertTrue(product["ok"])
        self.assertEqual(product["calendar"]["auto_boundaries"][0]["choice"], "before")
        self.assertEqual(product["gogyo_variants"]["B"]["status"], "available")

    def test_reading_manual_choice_changes_year_effect(self):
        payload = {**BASE, "birthDate": "1988-08-12", "birthTime": "09:00", "readingDate": "2020-02-04", "productAutoBoundary": True}
        auto = calculate_fortune(payload)
        boundary = auto["calendar"]["auto_boundaries"][0]
        after = calculate_fortune({**payload, "boundarySelections": {"reading": {
            "boundary_datetime": boundary["boundary_datetime"], "choice": "after",
        }}})
        self.assertTrue(after["ok"])
        self.assertNotEqual(auto["gogyo"]["kantei_year"], after["gogyo"]["kantei_year"])
        self.assertEqual(after["gogyo_variants"]["B"]["status"], "available")

    def test_variant_states_without_fabricated_scores(self):
        pending = calculate_fortune({**BASE, "birthDate": "1988-08-12", "birthTime": "09:00", "readingDate": "2020-02-04"})
        self.assertEqual([pending["gogyo_variants"][key]["status"] for key in "ABC"],
                         ["available", "boundary_pending", "boundary_pending"])
        unavailable = calculate_fortune({**BASE, "productAutoBoundary": True})
        self.assertEqual(unavailable["gogyo_variants"]["C"]["status"], "unavailable")
        self.assertNotIn("gogyo", unavailable["gogyo_variants"]["C"])

    def test_variant_c_available_with_gender(self):
        result = calculate_fortune({**BASE, "birthDate": "1950-01-01", "birthTime": "00:00", "gender": "男性", "productAutoBoundary": True})
        self.assertEqual(result["gogyo_variants"]["C"]["status"], "available")
        self.assertIn("scores", result["gogyo_variants"]["C"]["gogyo"])

    def test_current_stage_pair_reuses_existing_text(self):
        payload = {**BASE, "birthDate": "1950-01-01", "birthTime": "00:00", "productAutoBoundary": True}
        result = calculate_fortune(payload)
        pair = result["personality"]["current_life_stage_pair"]
        self.assertEqual(pair["age"], 76)
        self.assertEqual(pair["stage"], "65歳以降")
        self.assertEqual(pair["public_comment"], get_month_pair_comment(pair["inner"], pair["outer"], "public"))
        legacy = calculate_fortune({key: val for key, val in payload.items() if key != "productAutoBoundary"})
        self.assertNotIn("current_life_stage_pair", legacy["personality"])

    def test_month_periods_are_sekki_intervals(self):
        product = calculate_fortune({**BASE, "productAutoBoundary": True})
        monthly = product["yearly_flow"]["rows"]
        self.assertEqual(len(monthly), 12)
        self.assertEqual([row["月番号"] for row in monthly], list(range(2, 13)) + [1])
        self.assertEqual(monthly[0]["対象期間"]["start_term"], "立春")
        self.assertEqual(monthly[-1]["対象期間"]["start_term"], "小寒")
        for current, next_row in zip(monthly, monthly[1:]):
            self.assertEqual(current["対象期間"]["end_exclusive"], next_row["対象期間"]["start"])
        legacy = calculate_fortune({**BASE, "boundarySelections": {"birth": {
            "boundary_datetime": product["calendar"]["auto_boundaries"][0]["boundary_datetime"],
            "choice": "after",
        }}})
        self.assertNotIn("対象期間", legacy["yearly_flow"]["rows"][0])


if __name__ == "__main__":
    unittest.main()
