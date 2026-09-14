"""Adopted specifications from formal.json and the verified sekki reference ledger."""
from datetime import datetime, timedelta
import json
from pathlib import Path
from check import equal
import calendar_logic as calendar
import calendar_reference as reference
import taizan_sekki_correction as sekki
from fortune_service import calculate_fortune

def fixture():
    return json.loads((Path(__file__).parent / "fixtures/formal.json").read_text(encoding="utf-8"))

def auto_at(value):
    context = reference.get_calendar_context_for_birth_year(value.year)
    equal(context["ok"], True)
    return calendar.calculate_auto_meishiki(
        {"adjusted_birth_datetime": value},
        **{key: context[key] for key in ("risshun_datetime", "sekki_entries", "base_date", "base_day_kanchi")})

def check_case(case):
    kind, inp, expected = case["kind"], case["input"], case["expected"]
    if kind == "round":
        actual = sekki.round_eacal_datetime_to_minute(datetime.fromisoformat(inp))
        equal(actual.isoformat(), expected)
    elif kind == "timezone":
        source = datetime.fromisoformat(inp)
        converted = sekki.convert_eacal_datetime_to_fixed_jst(source)
        equal(converted.isoformat(), expected)
        equal(converted.timestamp(), source.timestamp())
        equal(converted.utcoffset(), timedelta(hours=9))
    elif kind == "boundary":
        context = reference.get_calendar_context_for_birth_year(inp["year"])
        equal(context["ok"], True)
        entry = next(e for e in context["sekki_entries"]
                     if e["year"] == inp["year"] and e["name"] == inp["term"])
        at = entry["datetime"] + timedelta(seconds=inp["offset_seconds"])
        month = calendar.find_month_branch_by_sekki(at, context["sekki_entries"])
        equal(month["matched_sekki_name"], expected["matched_term"])
        if inp["term"] == "立春":
            year = calendar.calculate_year_pillar(at, context["risshun_datetime"])
            equal(year["is_before_risshun"], inp["offset_seconds"] < 0)
            equal(year["year_kanchi"], expected["year_pillar"])
    elif kind == "warning":
        at = datetime(1950, 6, 6, 15, 51)
        actual = sekki.get_taizan_sekki_boundary_warnings(
            at + timedelta(seconds=inp), [{"year":1950, "name":"芒種", "datetime":at}])
        equal(sorted(w["code"] for w in actual), expected)
    elif kind == "pillars":
        at = datetime.fromisoformat(inp)
        result = auto_at(at)
        equal({p:result[p]["kanchi"] for p in expected}, expected)
        result = calculate_fortune({"birthDate":str(at.date()), "birthTime":at.strftime("%H:%M"),
                                   "birthPlace":"未選択", "readingDate":"2026-09-08"})
        equal(result["ok"], True)
        equal({p:result["meishiki"][p]["tenkan"]+result["meishiki"][p]["chishi"]
               for p in expected}, expected)
    elif kind == "day_hour":
        result = auto_at(datetime.fromisoformat(inp))
        equal({p:result[p]["kanchi"] for p in ("day","hour")}, expected)
    elif kind == "hour_basis":
        result = calendar.get_hour_tenkan_basis_for_taizan(
            datetime(2021,2,3,inp["hour"]), inp["day_stem"])
        equal(result["hour_day_tenkan"], expected["hour_stem_basis"])
        equal(result["uses_next_day_tenkan"], expected["next_day"])
    else:
        raise ValueError(f"Unknown Tier A kind: {kind}")

def cases():
    data = fixture()
    if not data["cases"] or len(data["cases"]) != data["case_count"]:
        raise ValueError("Formal cases missing or count mismatch")
    ids = set()
    for case in data["cases"]:
        required = {"id", "tier", "specification", "kind", "input", "expected", "source", "reference"}
        if not required <= case.keys() or case["tier"] != "A":
            raise ValueError("Invalid formal case metadata")
        if case["id"] in ids or not case["source"] or not case["reference"]:
            raise ValueError("Invalid/duplicate formal evidence")
        if case["source"] not in data["sources"]:
            raise ValueError("Formal source ID is not defined")
        ids.add(case["id"])
        yield case["id"], lambda c=case: check_case(c)

    from specific_datetime_guard import formal_cases
    yield from formal_cases()

    from sekki_reference import accuracy_cases
    yield from accuracy_cases()

    from gogyou_priority import cases as gogyou_priority_cases
    yield from gogyou_priority_cases()

    from gogyou_priority import formal_cases as gogyou_formal_cases
    yield from gogyou_formal_cases()

    from gogyou_concurrent import cases as concurrent_cases
    yield from concurrent_cases()
