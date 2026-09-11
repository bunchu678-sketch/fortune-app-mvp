"""Observed behavior. Differences require review, not automatic baseline replacement."""
from __future__ import annotations
import asyncio
from datetime import date, datetime
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
from check import ROOT, equal
import calendar_logic
import calendar_reference
import daiun_logic
import fortune_core_logic as core
import gogyou_logic
import meishiki_model
import time_adjustment_logic
import yearly_flow_logic
import yearly_overall_logic
from fortune_service import calculate_fortune, to_jsonable

BASE = {"birthDate":"1988-08-12", "birthTime":"09:00", "birthPlace":"東京都",
        "gender":"男性", "readingDate":"2026-09-08", "specificDatetimeEnabled":False}

@lru_cache(maxsize=32)
def service_json(payload_json):
    return calculate_fortune(json.loads(payload_json))

def service(**overrides):
    return service_json(json.dumps({**BASE, **overrides}, ensure_ascii=False, sort_keys=True))

def select(mapping, keys):
    return {key:mapping[key] for key in keys}

def projection(result):
    if not result["ok"]:
        return {"ok":False, "errors_type":type(result["errors"]).__name__}
    d = result["daiun"]
    return {
        "meishiki":result["meishiki"], "star_data":result["star_data"], "kubou":result["kubou"],
        "birth_adjustment":result["birth_adjustment"],
        "gogyo":select(result["gogyo"], ("scores","special_flags","chart_order","kantei_year")),
        "daiun":{"ok":d["ok"], "direction":d["direction"], "kigun_age":d["kigun_age"],
                 "rows":[select(r, ("大運干支","開始年齢","終了年齢","十二運星",
                                   "次の大運との間が接木運","接木運_開始年齢","接木運_終了年齢"))
                         for r in d["rows"]]},
        "monthly":[select(r, ("年","月番号","代表日","月干支","通変星","空亡"))
                   for r in result["yearly_flow"]["rows"]],
        "yearly":select(result["yearly_overall"], ("year","year_kanchi","tsuhensei")),
    }

def observation(kind, inp):
    if kind == "service":
        return projection(service(**inp))
    if kind == "table":
        fn = getattr(core, inp["function"])
        return [[fn(*args) for args in row] for row in inp["rows"]]
    if kind == "hidden":
        return [[calendar_logic.get_taizan_hidden_stem(branch, day)
                 for branch in inp["branches"]] for day in inp["days"]]
    if kind == "gogyo":
        result = gogyou_logic.calculate_gogyo_scores(**inp)
        return select(result, ("scores","special_flags"))
    if kind == "longitude":
        return to_jsonable(time_adjustment_logic.apply_birthplace_time_adjustment(
            datetime.fromisoformat(inp["datetime"]), inp["place"]))
    if kind == "directions":
        return [[daiun_logic.determine_daiun_direction(stem, gender)["direction"]
                 for gender in inp["genders"]] for stem in inp["stems"]]
    if kind == "kigun":
        return daiun_logic.calculate_kigun_age_by_days(
            datetime.fromisoformat(inp[0]),datetime.fromisoformat(inp[1]))
    if kind == "analysis_year":
        return meishiki_model.build_analysis_context(date.fromisoformat(inp))
    if kind == "specific":
        from specific_datetime_logic import build_specific_datetime_fortunes
        inputs=[{"date":date.fromisoformat(r["date"]),
                 "time":datetime.strptime(r["time"],"%H:%M").time()} for r in inp]
        result=to_jsonable(build_specific_datetime_fortunes(inputs,"己"))
        # Only computational fields; do not freeze interpretation wording.
        def without_text(value):
            if isinstance(value,dict):
                return {k:without_text(v) for k,v in value.items()
                        if k not in ("comment","keyword","keywords","theme","label","title","display_datetime","display_name")}
            if isinstance(value,list):
                return [without_text(v) for v in value]
            return value
        return without_text(result)
    raise ValueError(kind)

@lru_cache(maxsize=1)
def api_app():
    path = ROOT / "fortune-next-app/backend/server.py"
    spec = importlib.util.spec_from_file_location("regression_w_api", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app

async def asgi_request(app, method, path, raw=b""):
    """Actual FastAPI routing in memory. No listening socket and no httpx."""
    messages = []
    delivered = False
    async def receive():
        nonlocal delivered
        if delivered:
            return {"type":"http.disconnect"}
        delivered = True
        return {"type":"http.request", "body":raw, "more_body":False}
    async def send(message):
        messages.append(message)
    scope = {"type":"http", "asgi":{"version":"3.0", "spec_version":"2.3"},
             "http_version":"1.1", "method":method, "scheme":"http",
             "path":path, "raw_path":path.encode(), "query_string":b"",
             "root_path":"", "headers":[(b"content-type",b"application/json")],
             "server":("test",80), "client":("test",1)}
    await app(scope, receive, send)
    status = next(m["status"] for m in messages if m["type"] == "http.response.start")
    body = b"".join(m.get("body",b"") for m in messages if m["type"] == "http.response.body")
    return status, json.loads(body)

def request(method, path, payload=None, raw=None):
    body = raw if raw is not None else json.dumps(payload or {}).encode()
    return asyncio.run(asgi_request(api_app(),method,path,body))

def shape_check():
    result = service()
    types = {"ok":bool, "meishiki":dict, "meishiki_table":list, "star_data":dict,
             "kubou":str, "gogyo":dict, "personality":dict, "daiun":dict,
             "yearly_flow":dict, "yearly_overall":dict, "specific_datetime":dict}
    for key, typ in types.items():
        equal(type(result[key]), typ)
    for pillar in ("year","month","day","hour"):
        for key in ("tenkan","chishi","zokkan"):
            equal(type(result["meishiki"][pillar][key]), str)
    for key in ("木","火","土","金","水"):
        if type(result["gogyo"]["scores"][key]) not in (int,float):
            raise AssertionError("Five-element score must be numeric")
    for section in ("daiun","yearly_flow","specific_datetime"):
        equal(type(result[section]["rows"]), list)
    # Private fields intentionally excluded. Additional fields are allowed.
    json.dumps(result, ensure_ascii=False, allow_nan=False)

def api_check(method, path, payload, expected_status):
    status, result = request(method,path,payload)
    equal(status,expected_status)
    if expected_status in (200,422):
        equal(result["ok"],expected_status==200)
    if expected_status==422:
        equal(type(result["errors"]),list)
    if path=="/health":
        equal(result, {"ok":True,"service":"fortune-api"})
    elif expected_status==200:
        equal(result["meishiki"],service()["meishiki"])
        json.dumps(result,allow_nan=False)

def representative_month():
    with patch.object(yearly_flow_logic, "calculate_month_pillar",
                      wraps=yearly_flow_logic.calculate_month_pillar) as fn:
        result = yearly_flow_logic.build_yearly_monthly_flow_row(2026,1,"己","辰巳")
        equal(result["error"],"")
        equal(fn.call_args.args[0],datetime(2026,1,15,12))

def representative_year():
    with patch.object(yearly_overall_logic, "calculate_year_pillar",
                      wraps=yearly_overall_logic.calculate_year_pillar) as fn:
        result = yearly_overall_logic.build_yearly_overall_fortune(date(2026,1,1),"己")
        equal(result["ok"],True)
        equal(fn.call_args.args[0],datetime(2026,2,15,12))

def hidden_shared_days():
    at = datetime(2020,6,1,12)
    ctx = calendar_reference.get_calendar_context_for_birth_year(at.year)
    with patch.object(calendar_logic, "get_taizan_hidden_stem",
                      wraps=calendar_logic.get_taizan_hidden_stem) as fn:
        result=calendar_logic.calculate_auto_meishiki(
            {"adjusted_birth_datetime":at}, **{k:ctx[k] for k in
             ("risshun_datetime","sekki_entries","base_date","base_day_kanchi")})
        equal(len(fn.call_args_list),4)
        equal([c.args[1] for c in fn.call_args_list],[result["hidden_stem_day_count"]]*4)

def cases():
    data=json.loads((Path(__file__).parent/"fixtures/observed.json").read_text(encoding="utf-8"))
    if not data["cases"] or len(data["cases"]) != data["case_count"]:
        raise ValueError("Observation cases missing or count mismatch")
    for item in data["cases"]:
        if item["tier"]!="B":
            raise ValueError("Observation metadata must be Tier B")
        yield item["id"], lambda c=item: equal(to_jsonable(observation(c["kind"],c["input"])), c["expected"])
    yield "B-response-shape", shape_check
    yield "B-month-representative-time", representative_month
    yield "B-year-representative-time", representative_year
    yield "B-hidden-shared-days", hidden_shared_days
    for case_id,method,path,payload,status in (
        ("B-api-health","GET","/health",{},200),
        ("B-api-fortune","POST","/api/fortune",BASE,200),
        ("B-api-range","POST","/api/fortune",{**BASE,"birthDate":"1939-12-31"},422),
        ("B-api-notfound","GET","/absent",{},404),
    ):
        yield case_id, lambda m=method,p=path,b=payload,s=status: api_check(m,p,b,s)
