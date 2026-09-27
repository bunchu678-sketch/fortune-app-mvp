"""Formal product A/B/C gogyou cases from the user-approved instruction."""
from datetime import date

from check import equal
from daiun_logic import select_current_daiun
from fortune_service import calculate_fortune
from gogyou_external_effects import calculate_gogyo_scores_with_external_effects
from gogyou_logic import calculate_gogyo_scores_from_meishiki
from meishiki_model import build_meishiki_from_manual_input


BASE = {
    "birthDate": "1988-08-12", "birthTime": "09:00",
    "birthPlace": "東京都", "gender": "男性", "readingDate": "2026-09-08",
}
YEAR = {"source": "kantei_year", "tenkan": "", "chishi": ""}
DAIUN = {"source": "daiun", "tenkan": "", "chishi": ""}


def chart(branches, stems=("", "", "", "")):
    return build_meishiki_from_manual_input(*stems, *branches)


def multi(branches, year="", daiun="", year_stem="", daiun_stem="", stems=("", "", "", "")):
    return calculate_gogyo_scores_with_external_effects(
        chart(branches, stems),
        [
            {**YEAR, "tenkan": year_stem, "chishi": year},
            {**DAIUN, "tenkan": daiun_stem, "chishi": daiun},
        ],
    )


def points(result):
    return [(row["対象"], row["五行"], row["点数"]) for row in result["details"]]


def relations(result):
    flags = result["special_flags"]
    return (
        flags["chong"],
        [(item["element"], tuple(item["members"])) for item in flags["sango_all"]],
        [(item["element"], tuple(item["members"])) for item in flags["hougou_all"]],
        [(item["element"], tuple(item["members"])) for item in flags["hangou"]],
    )


def check_legacy_variants():
    payload = {**BASE, "includeGogyoVariants": True}
    result = calculate_fortune(payload)
    equal(result["ok"], True)
    variants = result["gogyo_variants"]
    equal([variants[k]["status"] for k in ("A", "B", "C")],
          ["available", "available", "available"])
    old_on = calculate_fortune(BASE)
    old_off = calculate_fortune({**BASE, "includeKanteiYearGogyoEffects": False})
    equal(variants["A"]["gogyo"], old_off["gogyo"])
    equal(variants["B"]["gogyo"], old_on["gogyo"])
    equal({k: v for k, v in result.items() if k != "gogyo_variants"}, old_on)


def check_year_only_common():
    for branches, year in (
        (("寅", "", "戌", ""), "午"),
        (("寅", "", "卯", ""), "辰"),
        (("辰", "", "", ""), "寅"),
        (("午", "", "", ""), "子"),
        (("亥", "卯", "未", "寅"), "辰"),
    ):
        meishiki = chart(branches)
        legacy = calculate_gogyo_scores_from_meishiki(
            meishiki, {"target_year_chishi": year}
        )
        combined = calculate_gogyo_scores_with_external_effects(
            meishiki, [{**YEAR, "chishi": year}]
        )
        equal(combined["scores"], legacy["scores"])
        equal(combined["details"], legacy["details"])
        for kind in ("chong", "sango", "hougou", "hangou"):
            equal(combined["special_flags"][kind], legacy["special_flags"][kind])


def check_no_direct_points():
    result = multi(("", "", "", ""), "午", "戌", "己", "戊")
    equal(result["scores"], {element: 0 for element in result["scores"]})
    equal(result["details"] == [], False)
    equal({row["対象"] for row in result["details"]},
          {"年干", "月干", "日干", "時干", "年支", "月支", "日支", "時支"})


def check_daiun_chong():
    result = multi(("午", "", "", ""), daiun="子")
    equal(result["scores"]["火"], 0)
    equal(result["special_flags"]["chong"]["zero_score_targets"], ["午"])


def check_daiun_sango():
    result = multi(("寅", "", "戌", ""), daiun="午")
    equal(result["scores"]["火"], 6)
    equal(result["special_flags"]["sango_all"][0]["element"], "火")


def check_daiun_hougou():
    result = multi(("寅", "", "卯", ""), daiun="辰")
    equal(result["scores"]["木"], 6)
    equal(result["special_flags"]["hougou_all"][0]["element"], "木")


def check_daiun_hangou():
    result = multi(("辰", "", "", ""), daiun="寅")
    equal(result["scores"]["木"], 2)
    equal(result["special_flags"]["hangou"][0]["element"], "木")


def check_daiun_earth_stem():
    result = multi(("巳", "", "", ""), daiun_stem="戊")
    equal(result["scores"]["火"], 1)
    equal(result["scores"]["土"], 1)


def check_two_sango():
    result = multi(("亥", "卯", "寅", "午"), year="未", daiun="戌")
    equal(result["scores"], {"木": 6, "火": 6, "土": 0, "金": 0, "水": 0})
    equal([item["element"] for item in result["special_flags"]["sango_all"]],
          ["木", "火"])
    equal(points(result)[4:], [
        ("年支", "木", 3), ("月支", "木", 3),
        ("日支", "火", 3), ("時支", "火", 3),
    ])


def check_two_hougou():
    result = multi(("寅", "卯", "亥", "子"), year="辰", daiun="丑")
    equal([item["element"] for item in result["special_flags"]["hougou_all"]],
          ["木", "水"])
    equal(result["scores"]["木"], 6)
    equal(result["scores"]["水"], 6)


def check_overlap_no_double_points():
    result = multi(("亥", "卯", "未", "寅"), year="辰", daiun="辰")
    equal(result["scores"]["木"], 12)
    equal(sum(row["点数"] for row in result["details"]), 12)
    equal([item["element"] for item in result["special_flags"]["sango_all"]],
          ["木"])
    equal([item["element"] for item in result["special_flags"]["hougou_all"]],
          ["木"])


def check_order_independent():
    examples = [
        (("亥", "卯", "寅", "午"), "未", "戌"),
        (("亥", "卯", "未", "寅"), "辰", "辰"),
        (("辰", "寅", "戌", "未"), "午", "卯"),
        (("午", "寅", "辰", ""), "子", "未"),
    ]
    for branches, year, daiun in examples:
        meishiki = chart(branches)
        effects = [{**YEAR, "chishi": year}, {**DAIUN, "chishi": daiun}]
        first = calculate_gogyo_scores_with_external_effects(meishiki, effects)
        second = calculate_gogyo_scores_with_external_effects(meishiki, list(reversed(effects)))
        equal(first["scores"], second["scores"])
        equal(points(first), points(second))
        equal(relations(first), relations(second))


def check_full_age():
    table = {
        "ok": True,
        "rows": [
            {"開始年齢数値": 0, "終了年齢数値": 25, "大運干支": "甲子"},
            {"開始年齢数値": 26, "終了年齢数値": 35, "大運干支": "乙丑"},
        ],
    }
    birth = date(2000, 8, 12)
    before = select_current_daiun(table, birth, date(2026, 8, 11))
    after = select_current_daiun(table, birth, date(2026, 8, 12))
    equal((before["age"], before["row"]["大運干支"]), (25, "甲子"))
    equal((after["age"], after["row"]["大運干支"]), (26, "乙丑"))
    equal(select_current_daiun(table, birth, date(1999, 8, 12))["reason"], "before_birth")
    equal(select_current_daiun(table, birth, date(2040, 8, 12))["reason"], "age_out_of_range")


def check_unavailable():
    result = calculate_fortune({
        **BASE, "gender": "未選択", "includeGogyoVariants": True,
    })
    equal(result["ok"], True)
    variants = result["gogyo_variants"]
    equal([variants[k]["status"] for k in ("A", "B", "C")],
          ["available", "available", "unavailable"])
    equal(variants["C"]["reason"], "daiun_not_available")


def check_risshun_pending():
    payload = {**BASE, "readingDate": "2020-02-04",
               "includeGogyoVariants": True,
               "includeKanteiYearGogyoEffects": False}
    result = calculate_fortune(payload)
    equal(result["ok"], True)
    equal([result["gogyo_variants"][k]["status"] for k in ("A", "B", "C")],
          ["available", "boundary_pending", "boundary_pending"])
    legacy = calculate_fortune({k: v for k, v in payload.items() if k != "includeGogyoVariants"})
    equal(legacy["ok"], True)
    equal(result["gogyo"], legacy["gogyo"])
    equal(result["gogyo_variants"]["B"]["reason"], "reading_risshun")
    equal("boundary_datetime" in result["gogyo_variants"]["B"], True)


def check_risshun_on_pending():
    payload = {**BASE, "readingDate": "2020-02-04",
               "includeGogyoVariants": True}
    result = calculate_fortune(payload)
    equal(result["ok"], True)
    equal([result["gogyo_variants"][k]["status"] for k in ("A", "B", "C")],
          ["available", "boundary_pending", "boundary_pending"])
    legacy = calculate_fortune({k: v for k, v in payload.items() if k != "includeGogyoVariants"})
    equal(legacy["confirmation_required"], True)


def check_risshun_choices():
    from calendar_reference import get_calendar_context_for_birth_year
    boundary = get_calendar_context_for_birth_year(2020)["risshun_datetime"]
    payload = {**BASE, "readingDate": "2020-02-04",
               "includeGogyoVariants": True,
               "includeKanteiYearGogyoEffects": False}
    for choice, expected in (("before", "己亥"), ("after", "庚子")):
        result = calculate_fortune({
            **payload, "boundarySelections": {
                "reading": {"boundary_datetime": boundary.isoformat(), "choice": choice}
            },
        })
        equal(result["ok"], True)
        variants = result["gogyo_variants"]
        equal([variants[k]["status"] for k in ("A", "B", "C")],
              ["available", "available", "available"])
        year = variants["B"]["gogyo"]["kantei_year"]
        equal(year["tenkan"] + year["chishi"], expected)
        equal(variants["C"]["gogyo"]["kantei_year"], year)


def check_repeatability():
    payload = {**BASE, "includeGogyoVariants": True}
    equal(calculate_fortune(payload), calculate_fortune(payload))


def check_api():
    from tier_b import request
    status, result = request("POST", "/api/fortune", {**BASE, "includeGogyoVariants": True})
    equal(status, 200)
    equal([result["gogyo_variants"][k]["status"] for k in ("A", "B", "C")],
          ["available", "available", "available"])


def cases():
    for name, check in (
        ("legacy-variants", check_legacy_variants),
        ("single-year-common", check_year_only_common),
        ("no-direct-points", check_no_direct_points),
        ("daiun-chong", check_daiun_chong),
        ("daiun-sango", check_daiun_sango),
        ("daiun-hougou", check_daiun_hougou),
        ("daiun-hangou", check_daiun_hangou),
        ("daiun-earth-stem", check_daiun_earth_stem),
        ("two-sango", check_two_sango),
        ("two-hougou", check_two_hougou),
        ("overlap-no-double", check_overlap_no_double_points),
        ("order-independent", check_order_independent),
        ("full-age", check_full_age),
        ("unavailable", check_unavailable),
        ("risshun-pending", check_risshun_pending),
        ("risshun-on-pending", check_risshun_on_pending),
        ("risshun-choices", check_risshun_choices),
        ("repeatability", check_repeatability),
        ("api", check_api),
    ):
        yield "A-gogyou-daiun-" + name, check
