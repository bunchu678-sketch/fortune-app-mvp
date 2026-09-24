"""Formal Risshun and request-scoped sekki confirmation cases."""

from datetime import date, datetime, timedelta
import json
from pathlib import Path

from check import equal
from boundary_confirmation import get_birth_boundary
from calendar_reference import get_calendar_context_for_birth_year
from fortune_service import calculate_fortune
from meishiki_model import build_analysis_context


BASE = {"birthDate": "1988-08-12", "birthTime": "09:00", "birthPlace": "未選択",
        "readingDate": "2026-09-08"}


def formal_years():
    records = json.loads((Path(__file__).parent / "fixtures/formal.json").read_text(encoding="utf-8"))["cases"]
    by_id = {record["id"]: record for record in records}
    for year in (2020, 2021, 2022):
        before = by_id[f"A-boundary-{year}-01--1"]["expected"]["year_pillar"]
        after = by_id[f"A-boundary-{year}-01-+0"]["expected"]["year_pillar"]
        yield year, before, after


def analysis_kanchi(target_date, choice=None):
    context = build_analysis_context(target_date, choice)
    return context["target_year_tenkan"] + context["target_year_chishi"]


def check_analysis_year(target_date, choice, expected):
    equal(analysis_kanchi(target_date, choice), expected)


def check_birth_window(offset_minutes, required):
    context = get_calendar_context_for_birth_year(2020)
    boundary = context["risshun_datetime"]
    adjusted = boundary + timedelta(minutes=offset_minutes)
    entry = get_birth_boundary(adjusted.date(), adjusted, False, context["sekki_entries"])
    equal(bool(entry), required)
    if entry:
        equal(entry["datetime"], boundary)


def selection(confirmation, choice):
    return {"boundary_datetime": confirmation["boundary_datetime"], "choice": choice}


def check_birth_known():
    payload = {**BASE, "birthDate": "2020-02-04", "birthTime": "18:03"}
    first = calculate_fortune(payload)
    equal(first["confirmation_required"], True)
    equal(len(first["boundary_confirmations"]), 1)
    item = first["boundary_confirmations"][0]
    equal((item["kind"], item["exact"], item["birth_time_unknown"]), ("birth", True, False))
    results = {}
    for choice in ("before", "after"):
        result = calculate_fortune({**payload, "boundarySelections": {"birth": selection(item, choice)}})
        equal(result["ok"], True)
        results[choice] = result
    equal((results["before"]["meishiki"]["year"]["tenkan"],
           results["before"]["meishiki"]["year"]["chishi"]), ("己", "亥"))
    equal((results["after"]["meishiki"]["year"]["tenkan"],
           results["after"]["meishiki"]["year"]["chishi"]), ("庚", "子"))
    equal((results["before"]["meishiki"]["month"]["tenkan"],
           results["before"]["meishiki"]["month"]["chishi"]), ("丁", "丑"))
    equal((results["after"]["meishiki"]["month"]["tenkan"],
           results["after"]["meishiki"]["month"]["chishi"]), ("戊", "寅"))
    for pillar in ("day", "hour"):
        equal(results["before"]["meishiki"][pillar], results["after"]["meishiki"][pillar])


def check_birthplace_adjustment():
    payload = {**BASE, "birthDate": "2020-02-04", "birthTime": "17:44", "birthPlace": "東京都"}
    first = calculate_fortune(payload)
    equal(first["confirmation_required"], True)
    item = first["boundary_confirmations"][0]
    equal(item["kind"], "birth")
    adjusted = datetime.fromisoformat(item["adjusted_birth_datetime"])
    boundary = datetime.fromisoformat(item["boundary_datetime"])
    equal(abs(adjusted - boundary) <= timedelta(minutes=5), True)
    equal(abs(datetime(2020, 2, 4, 17, 44) - boundary) > timedelta(minutes=5), True)


def check_birth_unknown():
    normal = calculate_fortune({**BASE, "birthDate": "2020-02-05", "birthTimeUnknown": True})
    equal(normal["ok"], True)
    equal(normal["meishiki"]["hour"]["tenkan"], "")
    payload = {**BASE, "birthDate": "2020-02-04", "birthTimeUnknown": True}
    first = calculate_fortune(payload)
    equal(first["confirmation_required"], True)
    item = first["boundary_confirmations"][0]
    equal((item["kind"], item["birth_time_unknown"]), ("birth", True))
    for choice, expected_year, expected_month in (
        ("before", "己亥", "丁丑"), ("after", "庚子", "戊寅"),
    ):
        result = calculate_fortune({**payload, "boundarySelections": {"birth": selection(item, choice)}})
        equal(result["ok"], True)
        equal(result["meishiki"]["year"]["tenkan"] + result["meishiki"]["year"]["chishi"], expected_year)
        equal(result["meishiki"]["month"]["tenkan"] + result["meishiki"]["month"]["chishi"], expected_month)
        equal(result["meishiki"]["hour"]["tenkan"], "")
        equal(result["basic_info"][1]["内容"], "出生時刻不明")


def check_non_risshun_birth_boundary():
    payload = {**BASE, "birthDate": "2020-01-06", "birthTimeUnknown": True}
    first = calculate_fortune(payload)
    equal(first["confirmation_required"], True)
    item = first["boundary_confirmations"][0]
    equal((item["kind"], item["term_name"]), ("birth", "小寒"))
    results = {}
    for choice in ("before", "after"):
        results[choice] = calculate_fortune({
            **payload, "boundarySelections": {"birth": selection(item, choice)},
        })
        equal(results[choice]["ok"], True)
    before, after = results["before"]["meishiki"], results["after"]["meishiki"]
    equal(before["year"], after["year"])
    equal(before["day"], after["day"])
    equal(before["hour"], after["hour"])
    equal(before["month"] == after["month"], False)


def check_resolved_year_on_off():
    payload = {**BASE, "birthDate": "1987-05-12", "readingDate": "2020-01-15"}
    default_on = calculate_fortune(payload)
    explicit_on = calculate_fortune({**payload, "includeKanteiYearGogyoEffects": True})
    off = calculate_fortune({**payload, "includeKanteiYearGogyoEffects": False})
    equal(default_on, explicit_on)
    equal((default_on["ok"], off["ok"]), (True, True))
    equal(default_on["gogyo"]["kantei_year"], {"tenkan": "己", "chishi": "亥"})
    equal(default_on["gogyo"]["scores"]["火"], 1)
    equal(off["gogyo"]["scores"]["火"], 5)
    equal(off["gogyo"]["include_kantei_year_gogyo_effects"], False)


def check_reading_day():
    payload = {**BASE, "readingDate": "2020-02-04"}
    first = calculate_fortune(payload)
    equal(first["confirmation_required"], True)
    item = first["boundary_confirmations"][0]
    equal(item["kind"], "reading")
    for choice, expected in (("before", "己亥"), ("after", "庚子")):
        selected = {**payload, "boundarySelections": {"reading": selection(item, choice)}}
        result = calculate_fortune(selected)
        equal(result["ok"], True)
        actual = result["gogyo"]["kantei_year"]
        equal(actual["tenkan"] + actual["chishi"], expected)
        equal(result["gogyo"]["include_kantei_year_gogyo_effects"], True)
        explicit = calculate_fortune({**selected, "includeKanteiYearGogyoEffects": True})
        equal(result, explicit)
    off = calculate_fortune({**payload, "includeKanteiYearGogyoEffects": False})
    equal(off["ok"], True)
    equal(off["gogyo"]["kantei_year"], {"tenkan": "", "chishi": ""})
    equal(off["gogyo"]["include_kantei_year_gogyo_effects"], False)


def check_api_confirmation():
    from tier_b import request
    payload = {**BASE, "readingDate": "2020-02-04"}
    status, first = request("POST", "/api/fortune", payload)
    equal(status, 422)
    equal(first["confirmation_required"], True)
    item = first["boundary_confirmations"][0]
    status, result = request("POST", "/api/fortune", {
        **payload, "boundarySelections": {"reading": selection(item, "after")},
    })
    equal(status, 200)
    equal(result["ok"], True)


def check_stale_and_invalid():
    payload = {**BASE, "readingDate": "2020-02-04"}
    first = calculate_fortune(payload)
    item = first["boundary_confirmations"][0]
    stale = calculate_fortune({**payload, "boundarySelections": {"reading": {
        "boundary_datetime": "2021-02-03T23:59:00", "choice": "after",
    }}})
    equal(stale["confirmation_required"], True)
    invalid = calculate_fortune({**payload, "boundarySelections": {"reading": selection(item, "maybe")}})
    equal(invalid["ok"], False)
    equal(bool(invalid["errors"]), True)


def cases():
    for year, before, after in formal_years():
        boundary = get_calendar_context_for_birth_year(year)["risshun_datetime"].date()
        for name, target_date, choice, expected in (
            ("january", date(year, 1, 15), None, before),
            ("previous-day", boundary - timedelta(days=1), None, before),
            ("day-before", boundary, "before", before),
            ("day-after", boundary, "after", after),
            ("next-day", boundary + timedelta(days=1), None, after),
        ):
            yield f"A-reading-risshun-{year}-{name}", lambda d=target_date,c=choice,e=expected:check_analysis_year(d,c,e)
    for offset in (-6, -5, -1, 0, 1, 5, 6):
        yield f"A-birth-window-{offset:+}", lambda m=offset:check_birth_window(m, abs(m) <= 5)
    yield "A-birth-known-choice", check_birth_known
    yield "A-birth-adjusted-time", check_birthplace_adjustment
    yield "A-birth-unknown-choice", check_birth_unknown
    yield "A-birth-non-risshun-choice", check_non_risshun_birth_boundary
    yield "A-resolved-year-on-off", check_resolved_year_on_off
    yield "A-reading-day-choice-and-off", check_reading_day
    yield "A-reading-day-api", check_api_confirmation
    yield "A-boundary-selection-validation", check_stale_and_invalid
