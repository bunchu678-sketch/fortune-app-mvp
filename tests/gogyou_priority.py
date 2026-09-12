"""Formal fallback rules confirmed by the user's gogyou bug-fix instruction.
Source: attachments/738a097f-ed54-44cf-80ac-9b5d972d9e97/pasted-text.txt,
sections 7-17, 20-28. Only this priority/fallback scope is promoted to Tier A.
Expected points below are derived from the explicit rules, not current outputs.
"""
from check import equal
import gogyou_logic as g

MAIN = ("戊","甲","戊","己","辰","寅","戌","未")


def branch_points(result, label):
    return [(r["五行"],r["点数"]) for r in result["details"] if r["対象"] == label]


def check_main():
    result = g.calculate_gogyo_scores(*MAIN,kantei_year_chishi="午")
    equal(result["scores"],{"土":6,"金":0,"水":0,"木":1,"火":8})
    flags = result["special_flags"]
    equal(flags["sango"],{"formed":True,"element":"火","members":["午","戌","寅"]})
    equal([(r["element"],set(r["members"]),r["same_as_sango"]) for r in flags["hangou"]],
          [("火",{"午","未"},True)])
    equal(flags["hougou"]["formed"],False)
    equal(branch_points(result,"年支"),[("土",1)])
    equal(branch_points(result,"月支"),[("火",3)])
    equal(branch_points(result,"日支"),[("火",3)])
    equal(branch_points(result,"時支"),[("火",2),("土",2)])
    equal([(r["五行"],r["点数"]) for r in result["details"] if r["対象"].endswith("干")],
          [("土",1),("木",1),("土",1),("土",1)])
    # No scored row for the analysis-year stem or branch.
    equal({r["対象"] for r in result["details"]},
          {"年干","月干","日干","時干","年支","月支","日支","時支"})


def check_other_storage(storage, participants, element):
    result = g.calculate_gogyo_scores("","","","",storage,*participants)
    equal(result["special_flags"]["sango"]["element"],element)
    equal(branch_points(result,"年支"),[("土",1)])
    equal(result["scores"],{e:(1 if e=="土" else 9 if e==element else 0) for e in ("木","火","土","金","水")})


def check_normal_wood(partner):
    result = g.calculate_gogyo_scores("","","","","辰",partner,"","")
    equal(result["scores"],{"木":5,"火":0,"土":0,"金":0,"水":0})
    equal(branch_points(result,"年支"),[("木",2)])
    equal(branch_points(result,"月支"),[("木",3)])
    equal([(r["element"],set(r["members"])) for r in result["special_flags"]["hangou"]],
          [("木",{partner,"辰"})])


def check_chong_only_removes_target():
    result = g.calculate_gogyo_scores("","","","","辰","寅","申","酉")
    equal(result["special_flags"]["chong"]["zero_score_targets"],["寅"])
    equal(branch_points(result,"月支"),[("木",0)])
    equal(branch_points(result,"年支"),[("土",1)])
    equal(result["scores"],{"木":0,"火":0,"土":1,"金":4,"水":0})
    equal([(r["element"],set(r["members"])) for r in result["special_flags"]["hangou"]],
          [("金",{"申","酉"})])


def check_chong_fire_fallback():
    result = g.calculate_gogyo_scores("甲","丙","戊","庚","子","午","卯","未")
    equal(result["scores"],{"木":2,"火":1,"土":2,"金":1,"水":1})
    equal(branch_points(result,"月支"),[("火",0)])
    equal(branch_points(result,"時支"),[("土",1)])
    equal(result["special_flags"]["hangou"],[])


def check_same_element_reuse():
    result = g.calculate_gogyo_scores("","","","","戌","巳","酉","丑")
    equal(result["scores"],{"木":0,"火":0,"土":0,"金":11,"水":0})
    equal(branch_points(result,"年支"),[("金",2)])
    equal(result["special_flags"]["sango"]["element"],"金")
    equal([(r["element"],set(r["members"]),r["same_as_sango"]) for r in result["special_flags"]["hangou"]],
          [("金",{"酉","戌"},True)])


def check_analysis_stem(analysis_stem):
    result = g.calculate_gogyo_scores("甲","甲","甲","甲",*MAIN[4:],
                                     kantei_year_tenkan=analysis_stem,kantei_year_chishi="午")
    equal(result["scores"],{"木":4,"火":8,"土":3 if analysis_stem else 1,"金":0,"水":0})
    equal(branch_points(result,"時支"),[("火",2),("土",2)] if analysis_stem else [("火",2)])


def check_transformed_analysis_branch():
    result = g.calculate_gogyo_scores("","","","","辰","午","戌","",kantei_year_chishi="寅")
    equal(result["scores"],{"木":0,"火":6,"土":1,"金":0,"水":0})
    equal(branch_points(result,"年支"),[("土",1)])
    equal(result["special_flags"]["sango"]["element"],"火")


def cases():
    yield "A-gogyou-priority-reported-chart",check_main
    for storage,participants,element in (("未",("巳","酉","丑"),"金"),
                                          ("戌",("申","子","辰"),"水"),
                                          ("丑",("亥","卯","未"),"木")):
        yield f"A-gogyou-priority-fallback-{storage}",lambda s=storage,p=participants,e=element:check_other_storage(s,p,e)
    for partner in ("寅","卯"):
        yield f"A-gogyou-priority-normal-{partner}辰",lambda p=partner:check_normal_wood(p)
    yield "A-gogyou-priority-chong-target-only",check_chong_only_removes_target
    yield "A-gogyou-priority-chong-fire-fallback",check_chong_fire_fallback
    yield "A-gogyou-priority-same-element-reuse",check_same_element_reuse
    for stem in ("","戊"):
        yield f"A-gogyou-priority-analysis-stem-{stem or 'absent'}",lambda s=stem:check_analysis_stem(s)
    yield "A-gogyou-priority-transformed-analysis-branch",check_transformed_analysis_branch


# Additional formal rules: user instruction e0b2cbcd-48cb-4be1-9a09-47f548b80b84,
# sections 7-18, 20, 23, 25. Expectations below are specification arithmetic.
# Empty pillars isolate an effect; they are engine inputs, not calendar fixtures.
# Do not import production tables to construct the oracle.
def assert_formal_result(result, expected_scores, expected_branches):
    equal(result["scores"], {e: expected_scores.get(e, 0) for e in ("木", "火", "土", "金", "水")})
    for label, expected in expected_branches.items():
        equal(branch_points(result, label), expected)
    equal({r["対象"] for r in result["details"]},
          {"年干", "月干", "日干", "時干", "年支", "月支", "日支", "時支"})
    for element in ("木", "火", "土", "金", "水"):
        equal(sum(r["点数"] for r in result["details"] if r["五行"] == element), result["scores"][element])


def check_stem_mapping(stem, element):
    result = g.calculate_gogyo_scores(stem, stem, stem, stem, "", "", "", "")
    assert_formal_result(result, {element: 4}, {})
    equal([(r["対象"], r["五行"], r["点数"]) for r in result["details"][:4]],
          [(label, element, 1) for label in ("年干", "月干", "日干", "時干")])


def check_hidden_stems_ignored():
    from copy import deepcopy
    from meishiki_model import build_meishiki_from_manual_input
    chart = build_meishiki_from_manual_input("甲", "丙", "庚", "壬", "寅", "巳", "戌", "丑")
    expected = {"木": 2, "火": 4, "土": 2, "金": 1, "水": 1}
    baseline = g.calculate_gogyo_scores_from_meishiki(chart)
    assert_formal_result(baseline, expected, {})
    for hidden in ("甲", "戊", "癸"):
        changed = deepcopy(chart)
        for pillar in changed.values():
            pillar["zokkan"] = hidden
        # In particular, hidden 戊 must not trigger extra earth points for 巳.
        actual = g.calculate_gogyo_scores_from_meishiki(changed)
        assert_formal_result(actual, expected, {})
        equal(actual, baseline)


def check_base_points():
    result = g.calculate_gogyo_scores("", "", "", "", "寅", "巳", "戌", "丑")
    assert_formal_result(result, {"木": 1, "火": 3, "土": 2},
                        {"年支": [("木", 1)], "月支": [("火", 3)],
                         "日支": [("土", 1)], "時支": [("土", 1)]})
    equal(result["special_flags"]["hangou"], [])
    for flag in ("sango", "hougou"):
        equal(result["special_flags"][flag]["formed"], False)
    equal(result["special_flags"]["chong"]["has_chong"], False)


def check_isolated_storage(storage):
    result = g.calculate_gogyo_scores("", "", "", "", storage, "", "", "")
    assert_formal_result(result, {"土": 1}, {"年支": [("土", 1)]})


def check_storage_half(storage, partner, element):
    result = g.calculate_gogyo_scores("", "", "", "", storage, partner, "", "")
    assert_formal_result(result, {element: 5},
                        {"年支": [(element, 2)], "月支": [(element, 3)]})
    equal([(r["element"], set(r["members"])) for r in result["special_flags"]["hangou"]],
          [(element, {storage, partner})])


def check_full_relation(kind, members, element, analysis=False):
    branches = (members[0], "", members[1], "") if analysis else (*members, "")
    result = g.calculate_gogyo_scores("", "", "", "", *branches,
                                     kantei_year_chishi=members[2] if analysis else "")
    labels = ("年支", "日支") if analysis else ("年支", "月支", "日支")
    assert_formal_result(result, {element: 6 if analysis else 9},
                        {label: [(element, 3)] for label in labels})
    relation = result["special_flags"][kind]
    equal((relation["formed"], relation["element"], set(relation["members"])),
          (True, element, set(members)))


def check_analysis_half(storage, partner, element):
    result = g.calculate_gogyo_scores("", "", "", "", storage, "", "", "",
                                     kantei_year_chishi=partner)
    assert_formal_result(result, {element: 2}, {"年支": [(element, 2)]})
    equal([(r["element"], set(r["members"])) for r in result["special_flags"]["hangou"]],
          [(element, {storage, partner})])


def check_chong_remaining(kind):
    # 子 -> 午 is already confirmed by A-gogyou-priority-chong-fire-fallback.
    members = ("申", "子", "辰") if kind == "sango" else ("亥", "子", "丑")
    result = g.calculate_gogyo_scores("", "", "", "", *members, "午")
    assert_formal_result(result, {"水": 9},
                        {"年支": [("水", 3)], "月支": [("水", 3)],
                         "日支": [("水", 3)], "時支": [("火", 0)]})
    equal(result["special_flags"]["chong"]["zero_score_targets"], ["午"])
    equal(result["special_flags"][kind]["formed"], True)


def check_analysis_chong():
    result = g.calculate_gogyo_scores("", "", "", "", "午", "寅", "辰", "",
                                     kantei_year_chishi="子")
    assert_formal_result(result, {"木": 5},
                        {"年支": [("火", 0)], "月支": [("木", 3)], "日支": [("木", 2)]})
    equal(result["special_flags"]["chong"]["zero_score_targets"], ["午"])
    equal([(r["element"], set(r["members"])) for r in result["special_flags"]["hangou"]],
          [("木", {"寅", "辰"})])


def check_earth_half(natal, analysis):
    # 巳 at year = fire2, 未 at month = fire3; qualifying stem adds earth5,
    # and only a natal stem additionally contributes its own earth1.
    stems = (natal, "", "", "") if natal != "己" else ("", "", natal, "")
    result = g.calculate_gogyo_scores(*stems, "巳", "未", "", "", kantei_year_tenkan=analysis)
    active = bool(natal or analysis)
    assert_formal_result(result, {"火": 5, "土": (5 if active else 0) + (1 if natal else 0)},
                        {"年支": [("火", 2)] + ([("土", 2)] if active else []),
                         "月支": [("火", 3)] + ([("土", 3)] if active else [])})


def check_earth_full():
    result = g.calculate_gogyo_scores("戊", "", "", "", "巳", "午", "未", "")
    assert_formal_result(result, {"火": 9, "土": 10},
                        {label: [("火", 3), ("土", 3)] for label in ("年支", "月支", "日支")})


def check_earth_transformed_out():
    result = g.calculate_gogyo_scores("戊", "", "", "", "巳", "酉", "丑", "")
    assert_formal_result(result, {"金": 9, "土": 1},
                        {label: [("金", 3)] for label in ("年支", "月支", "日支")})


def check_earth_fire_sango():
    result = g.calculate_gogyo_scores("戊", "", "", "", "寅", "午", "戌", "")
    assert_formal_result(result, {"火": 9, "土": 4},
                        {"年支": [("火", 3)], "月支": [("火", 3), ("土", 3)], "日支": [("火", 3)]})


def check_trigger_only():
    result = g.calculate_gogyo_scores("", "", "", "", "", "", "", "",
                                     kantei_year_tenkan="己", kantei_year_chishi="午")
    assert_formal_result(result, {}, {})
    equal(all(r["点数"] == 0 for r in result["details"]), True)


def formal_cases():
    for stem, element in zip("甲乙丙丁戊己庚辛壬癸", "木木火火土土金金水水"):
        yield f"A-gogyou-formal-stem-{stem}", lambda s=stem, e=element: check_stem_mapping(s, e)
    yield "A-gogyou-formal-hidden-ignored", check_hidden_stems_ignored
    yield "A-gogyou-formal-base-points", check_base_points
    for storage in "辰未戌丑":
        yield f"A-gogyou-formal-isolated-{storage}", lambda s=storage: check_isolated_storage(s)
    for storage, partners, element in (("未", "巳午", "火"), ("戌", "申酉", "金"), ("丑", "亥子", "水")):
        for partner in partners:
            yield f"A-gogyou-formal-half-{partner}{storage}", lambda s=storage, p=partner, e=element: check_storage_half(s, p, e)
    for element, members in (("木", "寅卯辰"), ("火", "巳午未"), ("金", "申酉戌"), ("水", "亥子丑")):
        for analysis in (False, True):
            yield f"A-gogyou-formal-hougou-{element}-{'year' if analysis else 'natal'}", lambda m=members, e=element, a=analysis: check_full_relation("hougou", m, e, a)
        yield f"A-gogyou-formal-half-{element}-year", lambda m=members, e=element: check_analysis_half(m[2], m[0], e)
    for element, members in (("木", "亥卯未"), ("火", "寅午戌"), ("金", "巳酉丑"), ("水", "申子辰")):
        yield f"A-gogyou-formal-sango-{element}", lambda m=members, e=element: check_full_relation("sango", m, e)
    for kind in ("sango", "hougou"):
        yield f"A-gogyou-formal-chong-keeps-{kind}", lambda k=kind: check_chong_remaining(k)
    yield "A-gogyou-formal-analysis-chong", check_analysis_chong
    for natal, analysis in (("", ""), ("戊", ""), ("己", ""), ("", "己")):
        yield f"A-gogyou-formal-earth-half-{natal or 'none'}-{analysis or 'none'}", lambda n=natal, a=analysis: check_earth_half(n, a)
    yield "A-gogyou-formal-earth-full", check_earth_full
    yield "A-gogyou-formal-earth-transformed-out", check_earth_transformed_out
    yield "A-gogyou-formal-earth-fire-sango", check_earth_fire_sango
    yield "A-gogyou-formal-trigger-only", check_trigger_only
    for element, branches in (("木", "亥卯未辰"), ("水", "申子辰丑")):
        yield f"A-gogyou-formal-same-element-{element}", lambda e=element, b=branches: check_remaining_same_element(e, b)
    yield "A-gogyou-formal-meishiki-context", check_meishiki_context


def check_remaining_same_element(element, branches):
    result = g.calculate_gogyo_scores("", "", "", "", *branches)
    assert_formal_result(result, {element: 11},
                        {"年支": [(element, 3)], "月支": [(element, 3)],
                         "日支": [(element, 3)], "時支": [(element, 2)]})
    equal(result["special_flags"]["sango"]["element"], element)
    equal([(r["element"], r["same_as_sango"]) for r in result["special_flags"]["hangou"]], [(element, True)])


def check_meishiki_context():
    from meishiki_model import build_meishiki_from_manual_input
    chart = build_meishiki_from_manual_input("甲", "甲", "甲", "甲", *MAIN[4:])
    # Already supplied context only: no Gregorian/risshun policy assertion.
    result = g.calculate_gogyo_scores_from_meishiki(chart,
               {"target_year_tenkan": "己", "target_year_chishi": "午"})
    assert_formal_result(result, {"木": 4, "火": 8, "土": 3},
                        {"年支": [("土", 1)], "月支": [("火", 3)],
                         "日支": [("火", 3)], "時支": [("火", 2), ("土", 2)]})
    equal(result["kantei_year"], {"tenkan": "己", "chishi": "午"})
