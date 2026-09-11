"""K07: OFF isolation is formal; ON results remain observed behavior.
Source: user instruction 2026-09-11, sections 12-16.
No astronomical expected values are promoted by these tests.
"""
from unittest.mock import patch
from check import equal
import fortune_service as engine

BASE = {"birthDate":"1988-08-12", "birthTime":"09:00", "birthPlace":"東京都",
        "gender":"男性", "readingDate":"2026-09-08", "specificDatetimeEnabled":False}
NORMAL = [{"date":"2026-09-09", "time":"12:00"}]


def check_off(candidates):
    from tier_b import request
    baseline = engine.calculate_fortune(BASE)
    equal(baseline["ok"], True)
    payload = {**BASE, "specificDatetimeCandidates":candidates}
    with patch.object(engine, "normalize_specific_candidates",
                      side_effect=AssertionError("OFF parsed candidates")) as normalize, \
         patch.object(engine, "build_specific_datetime_fortunes",
                      side_effect=AssertionError("OFF calculated candidates")) as calculate:
        equal(engine.calculate_fortune(payload), baseline)
        status, result = request("POST", "/api/fortune", payload)
        equal(status, 200)
        equal(result, baseline)
        normalize.assert_not_called()
        calculate.assert_not_called()


def check_off_variants(values):
    for value in values:
        check_off(value)


def check_off_no_access():
    class UnreadableCandidates(dict):
        def get(self, key, default=None):
            if key == "specificDatetimeCandidates":
                raise AssertionError("OFF accessed candidates")
            return super().get(key, default)
    equal(engine.calculate_fortune(UnreadableCandidates(BASE)), engine.calculate_fortune(BASE))


def formal_cases():
    yield "A-K07-off-normal", lambda: check_off(NORMAL)
    yield "A-K07-off-invalid-date", lambda: check_off([{"date":"2026-02-30", "time":"12:00"}])
    yield "A-K07-off-invalid-format", lambda: check_off_variants([
        [{"date":"invalid", "time":"bad"}], ["not-an-object"], {"bad":"shape"}, 42])
    yield "A-K07-off-empty", lambda: check_off_variants([[], None, "", [{"date":"", "time":""}]])
    yield "A-K07-off-four-candidates", lambda: check_off(NORMAL * 4)
    yield "A-K07-off-no-access", check_off_no_access


def check_on_normal():
    from tier_b import request
    # Also preserve K02: four candidates still work. No new limit is introduced.
    for candidates in (NORMAL, NORMAL * 4):
        payload = {**BASE, "specificDatetimeEnabled":True, "specificDatetimeCandidates":candidates}
        with patch.object(engine, "normalize_specific_candidates",
                          wraps=engine.normalize_specific_candidates) as normalize, \
             patch.object(engine, "build_specific_datetime_fortunes",
                          wraps=engine.build_specific_datetime_fortunes) as calculate:
            result = engine.calculate_fortune(payload)
            normalize.assert_called_once_with(candidates)
            calculate.assert_called_once()
            equal(calculate.call_args.args[0], engine.normalize_specific_candidates(candidates))
        equal(result["ok"], True)
        equal(len(result["specific_datetime"]["rows"]), len(candidates))
        status, body = request("POST", "/api/fortune", payload)
        equal(status, 200)
        equal(body, result)


def check_on_invalid():
    from tier_b import request
    # This is the observed API error contract, not a recommendation for future APIs.
    payload = {**BASE, "specificDatetimeEnabled":True,
               "specificDatetimeCandidates":[{"date":"invalid", "time":"12:00"}]}
    message = "time data 'invalid' does not match format '%Y-%m-%d'"
    with patch.object(engine, "build_specific_datetime_fortunes") as calculate:
        try:
            engine.calculate_fortune(payload)
        except ValueError as exc:
            equal(str(exc), message)
        else:
            raise AssertionError("ON invalid candidate was accepted")
        status, body = request("POST", "/api/fortune", payload)
        equal(status, 500)
        equal(body, {"ok":False, "errors":[message]})
        calculate.assert_not_called()


def observed_cases():
    yield "B-K07-on-normal", check_on_normal
    yield "B-K07-on-invalid", check_on_invalid
