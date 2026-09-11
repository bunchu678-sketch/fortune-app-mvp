"""Optional S/W comparison of 14 pure functions; no Streamlit/chart imports."""
import ast
from copy import deepcopy
import itertools
from pathlib import Path
from check import equal
import fortune_core_logic as core

FUNCTIONS = (
    "get_tsuhensei","get_kubou","get_juuni_unsei","get_tsuhensei_comment",
    "get_month_pair_comment","get_juuni_unsei_comment","get_juuni_unsei_thinking_tendency",
    "get_juuni_unsei_display_name","get_juuni_unsei_group_display",
    "get_juuni_unsei_keywords_display","get_juuni_unsei_theme_display",
    "get_juuni_unsei_reading_points_display","aggregate_juuni_unsei_thinking_tendency",
    "fill_missing_scores",
)

def literal_assignments(path):
    values={}
    for node in ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path)).body:
        if isinstance(node,ast.Assign):
            try:
                value=ast.literal_eval(node.value)
            except (ValueError,TypeError):
                continue
            for target in node.targets:
                if isinstance(target,ast.Name):
                    values[target.id]=value
    return values

def load_pure_s(root):
    path=root/"personality_logic.py"
    tree=ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    namespace=literal_assignments(path)
    # Use reference dictionaries, never substitute W's dictionaries for S data.
    for node in tree.body:
        if isinstance(node,ast.ImportFrom) and node.module in ("fortune_data","comments"):
            values=literal_assignments(root/(node.module+".py"))
            for alias in node.names:
                namespace[alias.asname or alias.name]=deepcopy(values[alias.name])
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in FUNCTIONS]
    equal(set(n.name for n in nodes),set(FUNCTIONS))
    if any(n.decorator_list for n in nodes):
        raise ValueError("Reference changed: decorated function needs manual review")
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),"exec"),namespace)
    return namespace

def vectors():
    stems=list("甲乙丙丁戊己庚辛壬癸")+["",None,"invalid"]
    branches=list("子丑寅卯辰巳午未申酉戌亥")+["",None,"invalid"]
    stars=["比肩","劫財","食神","傷官","偏財","正財","偏官","正官","偏印","印綬"]+["","－",None,"invalid"]
    unsei=["長生","沐浴","冠帯","建禄","帝旺","衰","病","死","墓","絶","胎","養"]+["",None,"invalid"]
    types=["public","private","invalid"]
    yield "get_tsuhensei",itertools.product(stems,stems)
    yield "get_kubou",itertools.product(stems,branches)
    yield "get_juuni_unsei",itertools.product(stems,branches)
    yield "get_tsuhensei_comment",itertools.product(stars,types)
    yield "get_month_pair_comment",itertools.product(stars,stars,types)
    yield "get_juuni_unsei_comment",itertools.product(unsei,types)
    for name in ("get_juuni_unsei_thinking_tendency","get_juuni_unsei_display_name",
                 "get_juuni_unsei_group_display","get_juuni_unsei_keywords_display"):
        yield name,((x,) for x in unsei)
    for name in ("get_juuni_unsei_theme_display","get_juuni_unsei_reading_points_display"):
        yield name,((x,) for x in ("year","month","day","hour","invalid",""))
    yield "fill_missing_scores",iter([({},["左脳","右脳"]),({"左脳":50},["左脳","右脳"])])
    aggregate=[{}]+[{p:x for p in ("year","month","day","hour")} for x in unsei]
    aggregate.append({"year":"長生","month":"帝旺","day":"墓","hour":""})
    yield "aggregate_juuni_unsei_thinking_tendency",((x,) for x in aggregate)

def cases(root):
    reference=load_pure_s(Path(root))
    for name,args_list in vectors():
        for index,args in enumerate(args_list):
            def compare(n=name,a=args):
                actual=getattr(core,n)(*deepcopy(a))
                expected=reference[n](*deepcopy(a))
                equal(actual,expected)
            yield f"B-S-{name}-{index:04}",compare
