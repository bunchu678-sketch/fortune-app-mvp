"""User-confirmed concurrent relations (2026-09-14).
Source: attachment 2ced89ab-d24c-42a1-a00f-e72b1d8fc793, sections 5-14, 29, 37.
Literal expectations are rule arithmetic, not snapshots of implementation output.
"""
from itertools import permutations
from check import equal
import gogyou_logic as g
from gogyou_priority import assert_formal_result
from special_chart_logic import build_special_meishiki_rows

# branch order: year, month, day, hour; all natal stems absent.
CASES = {
    "G01": ("寅辰巳未", "", {"木":5,"火":4}, (("木",2),("木",3),("火",2),("火",2)),
            "", "", (("木","寅辰"),("火","巳未"))),
    "G02": ("亥卯未申", "戌", {"木":9,"金":2}, (("木",3),("木",3),("木",3),("金",2)),
            "木", "", (("金","申戌"),)),
    "G03": ("寅卯辰巳", "未", {"木":9,"火":2}, (("木",3),("木",3),("木",3),("火",2)),
            "", "木", (("火","巳未"),)),
    "G04": ("亥卯未寅", "辰", {"木":12}, (("木",3),)*4, "木", "木", ()),
}


def check_concurrent(case):
    branches, year, scores, points, sango, hougou, halves = case
    result = g.calculate_gogyo_scores("","","","",*branches,kantei_year_chishi=year)
    assert_formal_result(result,scores,dict(zip(("年支","月支","日支","時支"),([p] for p in points))))
    flags=result["special_flags"]
    equal(flags["sango"]["element"],sango)
    equal(flags["hougou"]["element"],hougou)
    equal(flags["sango"]["formed"],bool(sango))
    equal(flags["hougou"]["formed"],bool(hougou))
    equal([(r["element"],set(r["members"])) for r in flags["hangou"]],
          [(e,set(m)) for e,m in halves])
    # Actual service display builder must expose every accepted relationship.
    rows={r["判定"]:r["結果"] for r in build_special_meishiki_rows([],result)}
    equal("三合会局" in rows,bool(sango))
    equal("方合" in rows,bool(hougou))
    equal("方合半会" in rows,bool(halves))
    for element,_ in halves:
        equal(element+"の方合半会" in rows["方合半会"],True)
    formatted={r["判定"]:r["結果"] for r in g.format_gogyo_special_flags(flags)}
    equal(formatted["三合会局"] != "なし",bool(sango))
    equal(formatted["方合"] != "なし",bool(hougou))
    for element,_ in halves:
        equal(element in formatted["方合半会"],True)


def check_permuted_overlap():
    for branches in permutations("亥卯未寅"):
        check_concurrent((branches,"辰",{"木":12},(("木",3),)*4,"木","木",()))


def cases():
    for name,case in CASES.items():
        yield "A-gogyou-concurrent-"+name,lambda c=case:check_concurrent(c)
    variants=(
        ("independent-halves","申戌亥丑","",{"金":5,"水":4},(("金",2),("金",3),("水",2),("水",2)),"","",(("金","申戌"),("水","亥丑"))),
        ("water-sango-fire-half","申辰巳未","子",{"水":6,"火":4},(("水",3),("水",3),("火",2),("火",2)),"水","",(("火","巳未"),)),
        ("water-hougou-gold-half","亥子丑申","戌",{"水":9,"金":2},(("水",3),("水",3),("水",3),("金",2)),"","水",(("金","申戌"),)),
    )
    for name,*case in variants:
        yield "A-gogyou-concurrent-"+name,lambda c=case:check_concurrent(c)
    for element,branches,year in (("火","巳午未寅","戌"),("金","巳酉丑申","戌"),("水","申子辰亥","丑")):
        case=(branches,year,{element:12},((element,3),)*4,element,element,())
        yield "A-gogyou-concurrent-full-overlap-"+element,lambda c=case:check_concurrent(c)
    yield "A-gogyou-concurrent-G04-pillar-permutations",check_permuted_overlap
