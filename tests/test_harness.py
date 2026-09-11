"""Verify failure detection using memory-only mutations, never application edits."""
import contextlib
from copy import deepcopy
import io
import unittest
from unittest.mock import patch
import check
import tier_a
import tier_b
import tier_c

class HarnessTests(unittest.TestCase):
    def test_empty_formal_fixture_is_incomplete(self):
        data=deepcopy(tier_a.fixture())
        data["cases"]=[]
        with patch.object(tier_a,"fixture",return_value=data):
            with self.assertRaises(ValueError):
                list(tier_a.cases())

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):
            check.run_cases("A",[("duplicate",lambda:None),("duplicate",lambda:None)])

    def test_exit_codes(self):
        self.assertEqual(check.exit_code([],[]),0)
        self.assertEqual(check.exit_code(["regression"],[]),1)
        self.assertEqual(check.exit_code([],["change"]),2)
        self.assertEqual(check.exit_code(["regression"],["change"]),1)
        self.assertEqual(check.exit_code([],[],True),3)

    def test_failure_does_not_hide_remaining_checks(self):
        visited=[]
        def fail():
            raise AssertionError("deliberate failure")
        with contextlib.redirect_stdout(io.StringIO()):
            count,errors=check.run_cases("A",[("a",fail),("b",lambda:visited.append(True))])
        self.assertEqual((count,len(errors),visited),(2,1,[True]))

    def test_b_change_is_review(self):
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            _,errors=check.run_cases("B",[("b",lambda:check.equal(1,2))])
        self.assertIn("REVIEW",stream.getvalue())
        self.assertEqual(check.exit_code([],errors),2)

    def test_changed_known_issue_does_not_demand_old_behavior(self):
        with patch.object(tier_c,"probe",return_value=False):
            with contextlib.redirect_stdout(io.StringIO()):
                issues=tier_c.probe_all()
        self.assertTrue(all("CHANGED" in state for _,state in issues))
        self.assertEqual(check.exit_code([],[]),0)

    def test_rounding_regression_detected(self):
        case=next(c for c in tier_a.fixture()["cases"] if c["kind"]=="round" and ":30" in c["input"])
        with patch.object(tier_a.sekki,"round_eacal_datetime_to_minute",
                          side_effect=lambda v:v.replace(second=0,microsecond=0)):
            with self.assertRaises(AssertionError):
                tier_a.check_case(case)

    def test_timezone_replacement_regression_detected(self):
        case=next(c for c in tier_a.fixture()["cases"] if c["kind"]=="timezone" and "+10:00" in c["input"])
        with patch.object(tier_a.sekki,"convert_eacal_datetime_to_fixed_jst",
                          side_effect=lambda v:v.replace(tzinfo=tier_a.sekki.FIXED_JST)):
            with self.assertRaises(AssertionError):
                tier_a.check_case(case)

    def test_pillar_reference_is_independent(self):
        case=deepcopy(next(c for c in tier_a.fixture()["cases"] if c["kind"]=="pillars"))
        case["expected"]["day"]="incorrect"
        with self.assertRaises(AssertionError):
            tier_a.check_case(case)

    def test_api_shape_missing_scores_detected(self):
        result=deepcopy(tier_b.service())
        del result["gogyo"]["scores"]
        with patch.object(tier_b,"service",return_value=result):
            with self.assertRaises(KeyError):
                tier_b.shape_check()

    def test_s_uses_reference_data(self):
        import comparison
        reference=comparison.load_pure_s(check.ROOT)
        reference["TSUHENSEI_TABLE"]=deepcopy(reference["TSUHENSEI_TABLE"])
        reference["TSUHENSEI_TABLE"]["甲"]["甲"]="reference-only change"
        self.assertNotEqual(reference["get_tsuhensei"]("甲","甲"),
                            comparison.core.get_tsuhensei("甲","甲"))


    def test_reference_integrity_rejects_missing_duplicate_and_wrong_provenance(self):
        import sekki_reference as ref
        original = ref.load()
        def duplicate(data):
            data["records"][1] = deepcopy(data["records"][0])
        def provenance(data):
            row = next(r for r in data["records"] if r["year"] == 1950)
            row["source"].remove("representative")
        for mutate in (lambda d:d["records"].pop(), duplicate, provenance):
            data = deepcopy(original)
            mutate(data)
            with self.assertRaises(ValueError):
                ref.validate(data)

    def test_reference_integrity_protects_verified_values_missing_and_exception(self):
        import sekki_reference as ref
        original = ref.load()
        changes = [
            ((2049,"啓蟄"), "confirmation_status", "unverified"),
            ((2049,"啓蟄"), "expected_tolerance", 120),
            ((2049,"啓蟄"), "reference_datetime", "2049-03-05 12:43"),
            ((1940,"小寒"), "reference_datetime", "1940-01-06 00:00"),
            ((1975,"啓蟄"), "reference_datetime", "1975-03-06 14:06"),
        ]
        for key,field,value in changes:
            data = deepcopy(original)
            row = next(r for r in data["records"] if (r["year"],r["term_name"]) == key)
            row[field] = value
            with self.subTest(key=key,field=field):
                with self.assertRaises(ValueError):
                    ref.validate(data)

    def test_reference_accuracy_rejects_engine_outside_tolerance(self):
        import sekki_reference as ref
        from datetime import datetime, timedelta
        row = next(r for r in ref.verified_records() if r["test_status"] == "tier_a_accuracy")
        entry = deepcopy(ref.actual_entry(row))
        entry["datetime"] = datetime.fromisoformat(row["reference_datetime"]) + timedelta(seconds=61)
        with patch.object(ref,"actual_entry",return_value=entry):
            with self.assertRaises(AssertionError):
                ref.check_accuracy(row)

    def test_known_exception_improvement_and_worsening_require_review(self):
        import sekki_reference as ref
        row = next(r for r in ref.verified_records() if r["test_status"] == "known_exception")
        for changed_delta in (-180,-60,0):
            with patch.object(ref,"delta_seconds",return_value=changed_delta):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    count,errors = check.run_cases("B",[("exception",lambda:ref.check_known_exception(row))])
                self.assertEqual((count,len(errors),check.exit_code([],errors)),(1,1,2))
                self.assertIn("REVIEW",output.getvalue())

    def test_reference_source_paths_are_not_runtime_dependencies(self):
        import sekki_reference as ref
        from pathlib import Path
        real_read_text = Path.read_text
        def only_p_fixture(path, *args, **kwargs):
            self.assertEqual(path.resolve(),(check.ROOT / "tests/fixtures/sekki_reference.json").resolve())
            return real_read_text(path,*args,**kwargs)
        with patch.object(Path,"read_text",only_p_fixture):
            self.assertEqual(len(list(ref.accuracy_cases())),195)
            self.assertEqual(len(list(ref.exception_cases())),1)

if __name__=="__main__":
    unittest.main()
