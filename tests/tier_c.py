"""Non-blocking probes. Disappearance is a review cue, not a reason to restore bugs."""
from datetime import datetime
from tier_b import BASE, service, request
from calendar_reference import get_calendar_context_for_birth_year

ISSUES = [
    ("K01", "Year-specific interpretation", "2027 request can contain 2026 advice"),
    ("K02", "Server-side candidate limit", "UI offers 1-3; service can process 4"),
    ("K03", "Private API fields", "Non-displayed practitioner content is returned"),
    ("K04", "2050 monthly edge", "Next January 2051 is outside current supported range"),
    ("K05", "S/W presentation differences", "SVG, abnormal pillars, setsu, kubou, target time, private text"),
    ("K06", "Historical reference boundary", "2021 source 23:58 versus adopted engine 23:59"),
]

def probe(case_id):
    if case_id=="K01":
        value=service(readingDate="2027-01-01")["yearly_overall"]
        return value["year"]==2027 and "2026" in value["comment"]
    if case_id=="K02":
        value=service(specificDatetimeEnabled=True,specificDatetimeCandidates=[
            {"date":"2026-09-09","time":t} for t in ("00:00","12:00","22:59","23:00")])
        return len(value["specific_datetime"]["rows"])>3
    if case_id=="K03":
        status,value=request("POST","/api/fortune",BASE)
        if status!=200:
            raise ValueError(f"Unexpected status {status}")
        def contains_private(obj):
            if isinstance(obj,dict):
                return any(("private" in key and bool(v)) or contains_private(v) for key,v in obj.items())
            if isinstance(obj,list):
                return any(contains_private(v) for v in obj)
            return False
        return contains_private(value.get("personality",{}))
    if case_id=="K04":
        value=service(readingDate="2050-09-08")["yearly_flow"]
        return any(r["年"]==2051 and r["月番号"]==1 and bool(r["error"]) for r in value["rows"])
    if case_id=="K05":
        return None
    if case_id=="K06":
        actual=get_calendar_context_for_birth_year(2021)["risshun_datetime"]
        return actual!=datetime(2021,2,3,23,58)
    raise ValueError(case_id)

def classify(present):
    if present is None:
        return "MANUAL REVIEW"
    return "PRESENT" if present else "CHANGED / RECHECK (not automatically resolved)"

def probe_all():
    results=[]
    for case_id,title,description in ISSUES:
        try:
            state=classify(probe(case_id))
        except Exception as exc:
            state=f"UNVERIFIED ({type(exc).__name__}: {exc})"
        print(f"Tier C {case_id}: {state}; {title}: {description}")
        results.append((case_id,state))
    print("K07: RESOLVED; OFF isolation protected by Tier A A-K07-off-* (blocking)")
    return results
