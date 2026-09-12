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
