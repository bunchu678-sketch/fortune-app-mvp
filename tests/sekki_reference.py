"""Test-only reference integrity, absolute accuracy and known-difference review."""
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
from check import equal
import taizan_sekki_correction as engine

TERMS = "小寒 立春 啓蟄 清明 立夏 芒種 小暑 立秋 白露 寒露 立冬 大雪".split()
REPRESENTATIVE_YEARS = (1940,1950,1963,1975,1988,2000,2013,2025,2038,2049)
GROUP_KEYS = {
    "representative": {(y,t) for y in REPRESENTATIVE_YEARS for t in TERMS},
    "reference_36": {(y,t) for y in (2020,2021,2022) for t in TERMS},
    "reference_48": {(y,t) for y in (1948,1949,1950,1951) for t in TERMS},
    "extra_5": {(1947,"立春"),(1952,"啓蟄"),(1970,"芒種"),(1995,"白露"),(2030,"大雪")},
}
MISSING = (1940,"小寒")
EXCEPTION = (1975,"啓蟄")


def load():
    return json.loads((Path(__file__).parent / "fixtures/sekki_reference.json").read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError("Reference integrity: " + message)


def validate(data):
    require(data["format_version"] == 1, "unknown format")
    require(data["tolerance_unit"] == "seconds", "wrong tolerance unit")
    require(data["difference_convention"] == "current_engine_minus_reference", "wrong delta convention")
    require(data["counts"] == {"populated_unique":196,"missing":1,"normal_accuracy":195,
                               "known_exception":1,"merged_duplicates":12}, "wrong counts")
    require(data["confirmation_source"] == "confirmation" and
            "confirmation" in data["sources"], "missing user confirmation source")
    for source in data["sources"].values():
        require(bool(source.get("description")) and bool(source.get("file") or source.get("url")),
                "incomplete provenance")
    records = data["records"]
    require(len(records) == 197, "196 populated + one missing required")
    keys = [(r["year"],r["term_name"]) for r in records]
    require(len(set(keys)) == len(keys), "duplicate year/term")
    require(set(keys) == set().union(*GROUP_KEYS.values()), "missing or unexpected year/term")
    required = {"year","term_name","reference_datetime","confirmation_status","source",
                "source_detail","note","test_status","expected_tolerance"}
    for r,key in zip(records,keys):
        require(required <= r.keys(), "missing record fields")
        groups = {g for g,expected in GROUP_KEYS.items() if key in expected}
        require(len(r["source"]) == len(groups) and set(r["source"]) == groups,
                f"wrong provenance groups: {key}")
        require(len(r["source_detail"]) == len(groups) and
                {s["source"] for s in r["source_detail"]} == groups and
                all(s["location"] and s["source"] in data["sources"] for s in r["source_detail"]),
                f"incomplete source detail: {key}")
        if key == MISSING:
            require(r["reference_datetime"] is None and r["confirmation_status"] == "missing_reference"
                    and r["test_status"] == "missing_reference" and r["expected_tolerance"] is None,
                    "1940 small cold must remain missing")
            continue
        require(r["confirmation_status"] == "user_verified", f"confirmation downgraded: {key}")
        value = datetime.strptime(r["reference_datetime"], "%Y-%m-%d %H:%M")
        require(value.year == r["year"], f"wrong reference year: {key}")
        if key == EXCEPTION:
            require(r["reference_datetime"] == "1975-03-06 14:08" and
                    r["test_status"] == "known_exception" and r["expected_tolerance"] is None and
                    r["observed_delta_seconds"] == -120, "1975 verified exception altered")
        else:
            require(r["test_status"] == "tier_a_accuracy" and r["expected_tolerance"] == 60,
                    f"normal accuracy must remain 60 seconds: {key}")
    digest = hashlib.sha256(json.dumps(records,ensure_ascii=False,sort_keys=True,
                                       separators=(",",":")).encode()).hexdigest()
    require(digest == data["records_sha256"], "record content changed; review source before updating digest")
    return records


def verified_records():
    return validate(load())


def actual_entry(record):
    entries = engine.get_corrected_taizan_sekki_entries_by_year(record["year"])
    equal(len(entries),12)
    matches = [e for e in entries if e["name"] == record["term_name"]]
    equal(len(matches),1)
    return matches[0]


def delta_seconds(record):
    return (actual_entry(record)["datetime"] -
            datetime.fromisoformat(record["reference_datetime"])).total_seconds()


def check_accuracy(record):
    entry = actual_entry(record)
    actual = entry["datetime"]
    delta = abs((actual - datetime.fromisoformat(record["reference_datetime"])).total_seconds())
    if delta > record["expected_tolerance"]:
        raise AssertionError(f'{record["year"]} {record["term_name"]}: {delta}s exceeds 60s')
    # Preserve all former 48-case timezone/rounding checks.
    original = entry["original_eacal_datetime"]
    equal(entry["corrected_eacal_datetime"].utcoffset(),timedelta(hours=9))
    equal(engine.convert_eacal_datetime_to_fixed_jst(original).timestamp(),original.timestamp())
    equal(actual.tzinfo,None)
    equal(actual,engine.correct_eacal_datetime_for_taizan(original).replace(tzinfo=None))


def accuracy_cases():
    for record in verified_records():
        if record["test_status"] == "tier_a_accuracy":
            yield f'A-ref-{record["year"]}-{record["term_name"]}', lambda r=record: check_accuracy(r)


def check_known_exception(record):
    delta = delta_seconds(record)
    if delta != record["observed_delta_seconds"]:
        raise AssertionError(f'1975 verified reference remains {record["reference_datetime"]}; '
                             f'observed delta changed from -120s to {delta}s. '
                             'REVIEW even if improved; do not restore old engine behavior.')


def exception_cases():
    for record in verified_records():
        if record["test_status"] == "known_exception":
            yield "B-sekki-known-exception-1975", lambda r=record: check_known_exception(r)


def print_summary():
    records = verified_records()
    populated = [r for r in records if r["reference_datetime"] is not None]
    deltas = [delta_seconds(r) for r in populated]
    print("Reference integrity: PASS; 196 user_verified, 1 missing, 12 duplicates merged")
    print(f"Reference accuracy (196 unique): exact={sum(d==0 for d in deltas)}; "
          f"within60={sum(abs(d)<=60 for d in deltas)}; over60={sum(abs(d)>60 for d in deltas)}; "
          f"max_abs_seconds={max(map(abs,deltas)):g}; known_exception=1")
    record = next(r for r in populated if (r["year"],r["term_name"]) == EXCEPTION)
    print(f'Known exception: 1975 keichitsu; user_verified reference={record["reference_datetime"]}; '
          f'current={actual_entry(record)["datetime"]}; delta_seconds={delta_seconds(record):g}; '
          'excluded from normal 60-second PASS count, changed delta requires Tier B review')
