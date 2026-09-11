"""Run W regression tests; never update app files, fixtures or dependencies."""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import importlib.metadata
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EXCLUDED = {".git", ".venv", "venv", "env", "node_modules", ".next", "__pycache__",
            ".pytest_cache", "_backups", ".agents", ".codex", "tests"}

def source_hashes(root):
    result = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED]
        for name in files:
            path = Path(base) / name
            result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result

def equal(actual, expected):
    if actual != expected:
        raise AssertionError(f"expected={expected!r}; actual={actual!r}")

def run_cases(tier, cases):
    total, problems, seen = 0, [], set()
    for case_id, check in cases:
        total += 1
        if case_id in seen:
            raise ValueError(f"Duplicate {tier} case ID: {case_id}")
        seen.add(case_id)
        try:
            check()
        except Exception as exc:
            problems.append((case_id, type(exc).__name__, str(exc)))
    label = "FAIL" if tier == "A" else "REVIEW"
    for case_id, kind, detail in problems:
        print(f"Tier {tier} {label} {case_id}: {kind}: {detail}")
    return total, problems

def exit_code(a_problems, b_problems, infrastructure=False):
    if infrastructure:
        return 3
    if a_problems:
        return 1
    if b_problems:
        return 2
    return 0

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare-s", type=Path, metavar="REFERENCE_ROOT",
                        help="Optional read-only S comparison; W remains canonical")
    args = parser.parse_args(argv)
    roots = [ROOT]
    if args.compare_s:
        args.compare_s = args.compare_s.resolve()
        if not (args.compare_s / "personality_logic.py").is_file():
            parser.error("--compare-s must contain personality_logic.py")
        if args.compare_s != ROOT:
            roots.append(args.compare_s)
    before = {str(p): source_hashes(p) for p in roots}
    status = 3
    try:
        print(f"W root: {ROOT}")
        print(f"Python: {sys.executable} ({sys.version.split()[0]})")
        for name in ("eacal", "ephem", "pytz", "fastapi", "uvicorn"):
            print(f"{name}: {importlib.metadata.version(name)}")
        import sekki_reference
        sekki_reference.verified_records()
        import tier_a
        import tier_b
        import tier_c
        a_count, a_errors = run_cases("A", tier_a.cases())
        b_count, b_errors = run_cases("B", tier_b.cases())
        if args.compare_s:
            import comparison
            n, errors = run_cases("B", comparison.cases(args.compare_s))
            b_count += n
            b_errors += errors
            print(f"S comparison: {n} inputs; REVIEW {len(errors)}")
        else:
            print("S comparison: NOT RUN (optional; not counted as PASS)")
        issues = tier_c.probe_all()
        sekki_reference.print_summary()
        print(f"Tier A: {'FAIL' if a_errors else 'PASS'} {a_count-len(a_errors)}/{a_count}")
        print(f"Tier B: observation {b_count}; matched {b_count-len(b_errors)}; REVIEW {len(b_errors)}")
        print(f"Tier C: informational {len(issues)}; non-blocking")
        status = exit_code(a_errors, b_errors)
    except Exception as exc:
        print(f"INFRASTRUCTURE ERROR: {type(exc).__name__}: {exc}")
        print("Run incomplete; not PASS. No automatic installation.")
    finally:
        for root in roots:
            after, old = source_hashes(root), before[str(root)]
            changed = sorted(k for k in set(old) | set(after) if old.get(k) != after.get(k))
            print(f"Source hash check {root}: {len(old)} files; changes={len(changed)}")
            if changed:
                print("\n".join(changed))
                status = 3
    print(f"Exit: {status} (0=matched, 1=Tier A failed, 2=Tier B review, 3=incomplete/integrity error)")
    return status

if __name__ == "__main__":
    raise SystemExit(main())
