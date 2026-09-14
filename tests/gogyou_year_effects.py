"""Formal year-effect switch. Source: 2ced89ab-d24c-42a1-a00f-e72b1d8fc793 §§15-43.
Only already-supplied year stems/branches are formalized; year generation stays Tier B.
"""
from check import equal
import gogyou_logic as g
from gogyou_priority import assert_formal_result
from gogyou_concurrent import CASES
from special_chart_logic import build_special_meishiki_rows

PARAM = "includeKanteiYearGogyoEffects"
FLAG = "include_kantei_year_gogyo_effects"


def calculate(branches, year="", stem="", enabled=True, natal=("","","","")):
    return g.calculate_gogyo_scores(*natal,*branches,kantei_year_chishi=year,
                                    kantei_year_tenkan=stem,include_kantei_year_gogyo_effects=enabled)


def assert_off_display(result):
    equal(result[FLAG],False)
    equal(any("鑑定年" in r["理由"] for r in result["details"]),False)
    equal(any("鑑定年" in r["結果"] for r in build_special_meishiki_rows([],result)),False)


def check_year_relation(kind,branches,year,on_scores,off_scores):
    on=calculate(branches,year)
    off=calculate(branches,year,enabled=False)
    assert_formal_result(on,on_scores,{})
    assert_formal_result(off,off_scores,{})
    if kind=="hangou":
        equal(bool(on["special_flags"][kind]),True)
        equal(off["special_flags"][kind],[])
    elif kind=="chong":
        equal(on["special_flags"][kind]["zero_score_targets"],["午"])
        equal(off["special_flags"][kind]["has_chong"],False)
    else:
        equal(on["special_flags"][kind]["formed"],True)
        equal(off["special_flags"][kind]["formed"],False)
    assert_off_display(off)
    equal(off["kantei_year"],on["kantei_year"])


def check_year_earth(stem):
    on=calculate(("巳","","未",""),stem=stem)
    off=calculate(("巳","","未",""),stem=stem,enabled=False)
    assert_formal_result(on,{"火":4,"土":4},{"年支":[("火",2),("土",2)],"日支":[("火",2),("土",2)]})
    assert_formal_result(off,{"火":4},{"年支":[("火",2)],"日支":[("火",2)]})
    assert_off_display(off)


def check_no_year_points():
    for enabled in (True,False):
        assert_formal_result(calculate(("","","",""),"午","己",enabled),{},{})


def check_natal_kept(branches,year,stem,natal):
    off=calculate(branches,year,stem,False,natal)
    # Expected behavior is explicitly the same four pillars with no year material.
    baseline=g.calculate_gogyo_scores(*natal,*branches)
    for key in ("scores","details","special_flags","formula_chishi"):
        equal(off[key],baseline[key])
    assert_off_display(off)


def check_g_off(name,expected):
    branches,year,*_=CASES[name]
    result=calculate(branches,year,enabled=False)
    assert_formal_result(result,expected,{})
    assert_off_display(result)
    if name=="G04":
        equal(result["special_flags"]["sango"]["formed"],True)
        equal(result["special_flags"]["hougou"]["formed"],False)


def check_adapter_default():
    from meishiki_model import build_meishiki_from_manual_input
    chart=build_meishiki_from_manual_input("甲","甲","甲","甲","辰","寅","戌","未")
    context={"target_year_tenkan":"己","target_year_chishi":"午"}
    default=g.calculate_gogyo_scores_from_meishiki(chart,context)
    on=g.calculate_gogyo_scores_from_meishiki(chart,context,include_kantei_year_gogyo_effects=True)
    off=g.calculate_gogyo_scores_from_meishiki(chart,context,include_kantei_year_gogyo_effects=False)
    equal(default,on)
    equal(g.calculate_gogyo_scores("","","","","寅","","戌","",kantei_year_chishi="午"),
          calculate(("寅","","戌",""),"午"))
    assert_formal_result(off,{"木":9,"土":2},{})
    equal(context,{"target_year_tenkan":"己","target_year_chishi":"午"})
    assert_off_display(off)


def check_service_api(api=False):
    from tier_b import BASE,request
    from fortune_service import calculate_fortune
    payload={**BASE,"readingDate":"2020-09-08","specificDatetimeEnabled":True,
             "specificDatetimeCandidates":[{"date":"2026-09-08","time":"14:00"}]}
    def call(value):
        if api:
            status,result=request("POST","/api/fortune",value)
            equal(status,200)
            return result
        return calculate_fortune(value)
    default=call(payload)
    on=call({**payload,PARAM:True})
    off=call({**payload,PARAM:False})
    equal(default,on)
    equal(on["ok"],True);equal(off["ok"],True)
    equal([on["meishiki"][p]["chishi"] for p in ("year","month","day","hour")],list("辰申亥巳"))
    # 巳 is zeroed by natal 亥. ON: 辰申 water3 each + 亥 water2;
    # OFF: 辰 earth1, 申 gold3, 亥 water1. Stems 戊庚己己 add earth3+gold1.
    assert_formal_result(on["gogyo"],{"土":3,"金":1,"水":8},{})
    assert_formal_result(off["gogyo"],{"土":4,"金":4,"水":1},{})
    assert_off_display(off["gogyo"])
    equal({k:v for k,v in on.items() if k not in ("gogyo","special_meishiki")},
          {k:v for k,v in off.items() if k not in ("gogyo","special_meishiki")})
    # Keep non-gogyou abnormal-pillar presentation, too.
    equal([r for r in on["special_meishiki"]["rows"] if r["判定"]=="異常干支"],
          [r for r in off["special_meishiki"]["rows"] if r["判定"]=="異常干支"])


def check_invalid_bool():
    from tier_b import BASE,request
    for value in ("false",0,None):
        status,result=request("POST","/api/fortune",{**BASE,PARAM:value})
        equal(status,422);equal(result["ok"],False)


def cases():
    for args in (("sango",("寅","","戌",""),"午",{"火":6},{"木":1,"土":1}),
                 ("hougou",("寅","","卯",""),"辰",{"木":6},{"木":4}),
                 ("hangou",("辰","","",""),"寅",{"木":2},{"土":1}),
                 ("chong",("午","","",""),"子",{},{"火":1})):
        yield "A-gogyou-year-"+args[0],lambda a=args:check_year_relation(*a)
    for stem in "戊己":
        yield "A-gogyou-year-earth-"+stem,lambda s=stem:check_year_earth(s)
    yield "A-gogyou-year-no-direct-points",check_no_year_points
    for name,branches,year,stem,natal in (
        ("natal-sango","亥卯未辰","卯","己",("","","","")),
        ("natal-hougou","寅卯辰丑","寅","戊",("","","","")),
        ("natal-half",("巳","未","",""),"巳","己",("","","","")),
        ("natal-chong","子午卯未","午","戊",("","","","")),
        ("natal-earth",("巳","未","",""),"子","己",("戊","","",""))):
        yield "A-gogyou-year-keeps-"+name,lambda b=branches,y=year,s=stem,n=natal:check_natal_kept(b,y,s,n)
    for name,expected in (("G01",{"木":5,"火":4}),("G02",{"木":9,"金":1}),
                          ("G03",{"木":9,"火":1}),("G04",{"木":11})):
        yield "A-gogyou-year-off-"+name,lambda n=name,e=expected:check_g_off(n,e)
    yield "A-gogyou-year-adapter-default",check_adapter_default
    yield "A-gogyou-year-service",check_service_api
    yield "A-gogyou-year-api",lambda:check_service_api(True)
    yield "A-gogyou-year-invalid-bool",check_invalid_bool
