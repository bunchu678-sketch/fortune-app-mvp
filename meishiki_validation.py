from copy import deepcopy
from datetime import datetime

from calendar_logic import calculate_auto_meishiki, judge_getsurei_from_meishiki
from gogyou_logic import calculate_gogyo_scores_from_meishiki
from meishiki_model import (
    auto_meishiki_to_manual_format,
    build_analysis_context,
    build_birth_info,
)
from special_chart_logic import (
    build_ijou_kanshi_data_from_meishiki,
    build_special_meishiki_rows,
)


PILLAR_KEYS = ("year", "month", "day", "hour")
PILLAR_LABELS = {
    "year": "年",
    "month": "月",
    "day": "日",
    "hour": "時",
}
BIRTH_DATETIME_FORMAT = "%Y-%m-%d %H:%M"


# 現時点では検証用仮データのみを置く。
# 泰山流万年暦や先生の鑑定結果は、出典確認後に別途追加する。
VALIDATION_CASES = [
    {
        "case_id": "sample_2020_risshun_before",
        "description": "2020年立春直前の検証用サンプル",
        "birth_datetime": "2020-02-04 06:02",
        "birth_place": "日本",
        "expected": {
            "year": "己亥",
            "month": "丁丑",
            "day": None,
            "hour": None,
        },
        "source": "検証用仮データ",
        "note": "日柱・時柱はまだ正確な基準日確定前のため未設定",
    },
    {
        "case_id": "sample_2020_risshun_exact",
        "description": "2020年立春ちょうどの検証用サンプル",
        "birth_datetime": "2020-02-04 06:03",
        "birth_place": "日本",
        "expected": {
            "year": "庚子",
            "month": "戊寅",
            "day": None,
            "hour": None,
        },
        "source": "検証用仮データ",
        "note": "日柱・時柱はまだ正確な基準日確定前のため未設定",
    },
    {
        "case_id": "sample_2020_risshun_after",
        "description": "2020年立春後の検証用サンプル",
        "birth_datetime": "2020-02-05 12:00",
        "birth_place": "日本",
        "expected": {
            "year": "庚子",
            "month": "戊寅",
            "day": None,
            "hour": None,
        },
        "source": "検証用仮データ",
        "note": "日柱・時柱はまだ正確な基準日確定前のため未設定",
    },
    {
        "case_id": "sample_2020_risshu_exact",
        "description": "2020年立秋ちょうどの検証用サンプル",
        "birth_datetime": "2020-08-07 09:06",
        "birth_place": "日本",
        "expected": {
            "year": "庚子",
            "month": "甲申",
            "day": None,
            "hour": None,
        },
        "source": "検証用仮データ",
        "note": "日柱・時柱はまだ正確な基準日確定前のため未設定",
    },
]


def get_validation_cases() -> list:
    """
    検証ケース一覧を返す。

    呼び出し側で編集しても元データが変わらないようにコピーして返す。
    """
    return deepcopy(VALIDATION_CASES)


def _build_checked_map(expected: dict) -> dict:
    if not isinstance(expected, dict):
        expected = {}

    return {
        pillar_key: expected.get(pillar_key) is not None
        for pillar_key in PILLAR_KEYS
    }


def _get_auto_pillar_kanchi(auto_meishiki: dict, pillar_key: str):
    pillar_result = auto_meishiki.get(pillar_key)
    if not isinstance(pillar_result, dict):
        return None, f"{pillar_key} の計算結果がありません。"

    kanchi = pillar_result.get("kanchi")
    if kanchi is None:
        return None, f"{pillar_key}.kanchi がありません。"

    return kanchi, None


def compare_auto_meishiki_with_expected(auto_meishiki: dict, expected: dict) -> dict:
    """
    自動計算結果と期待結果を比較する。

    expected の year/month/day/hour に None が入っている場合は、
    その柱は比較対象外とする。
    """
    checked = {}
    differences = []
    errors = []

    if not isinstance(auto_meishiki, dict):
        auto_meishiki = {}
        errors.append("auto_meishiki は dict である必要があります。")

    if not isinstance(expected, dict):
        expected = {}
        errors.append("expected は dict である必要があります。")

    for pillar_key in PILLAR_KEYS:
        expected_kanchi = expected.get(pillar_key)
        should_check = expected_kanchi is not None
        checked[pillar_key] = should_check

        if not should_check:
            continue

        actual_kanchi, error = _get_auto_pillar_kanchi(auto_meishiki, pillar_key)
        if error:
            errors.append(error)

        if actual_kanchi != expected_kanchi:
            differences.append(
                {
                    "pillar": pillar_key,
                    "expected": expected_kanchi,
                    "actual": actual_kanchi,
                }
            )

    return {
        "matched": not differences and not errors,
        "differences": differences,
        "checked": checked,
        "errors": errors,
    }


def _parse_validation_birth_datetime(birth_datetime_text: str) -> datetime:
    if not isinstance(birth_datetime_text, str):
        raise ValueError("birth_datetime は 'YYYY-MM-DD HH:MM' 形式の文字列で指定してください。")

    try:
        return datetime.strptime(birth_datetime_text, BIRTH_DATETIME_FORMAT)
    except ValueError as exc:
        raise ValueError(
            "birth_datetime は 'YYYY-MM-DD HH:MM' 形式で指定してください。"
        ) from exc


def _build_birth_info_from_validation_case(case: dict) -> dict:
    birth_datetime = _parse_validation_birth_datetime(case.get("birth_datetime"))
    return build_birth_info(
        birth_datetime.date(),
        birth_datetime.time(),
        birth_place=case.get("birth_place", "日本"),
        birth_country=case.get("birth_country", "日本"),
        time_adjustment_enabled=False,
        time_adjustment_minutes=0,
    )


def _build_smoke_check(ok=None, errors=None, skipped=False, reason="", data=None) -> dict:
    result = {
        "ok": ok,
        "errors": errors or [],
    }
    if skipped:
        result["skipped"] = True
    if reason:
        result["reason"] = reason
    if data is not None:
        result["data"] = data
    return result


def _validate_manual_meishiki_format(manual_meishiki) -> dict:
    errors = []

    if not isinstance(manual_meishiki, dict):
        return _build_smoke_check(
            ok=False,
            errors=["manual_meishiki は dict である必要があります。"],
        )

    for pillar_key in PILLAR_KEYS:
        pillar = manual_meishiki.get(pillar_key)
        if not isinstance(pillar, dict):
            errors.append(f"manual_meishiki.{pillar_key} がありません。")
            continue

        for value_key in ("tenkan", "chishi", "zokkan"):
            if value_key not in pillar:
                errors.append(f"manual_meishiki.{pillar_key}.{value_key} がありません。")

        for value_key in ("tenkan", "chishi"):
            if pillar.get(value_key) is None:
                errors.append(f"manual_meishiki.{pillar_key}.{value_key} が None です。")

    try:
        repr(manual_meishiki)
    except Exception as exc:
        errors.append(f"manual_meishiki を repr() できません: {exc}")

    return _build_smoke_check(ok=not errors, errors=errors)


def _validate_auto_meishiki_source(auto_meishiki) -> dict:
    errors = []

    if not isinstance(auto_meishiki, dict):
        return _build_smoke_check(
            ok=False,
            errors=["auto_meishiki は dict である必要があります。"],
        )

    if auto_meishiki.get("error"):
        errors.append(f"auto_meishiki.error: {auto_meishiki['error']}")

    for pillar_key in PILLAR_KEYS:
        pillar = auto_meishiki.get(pillar_key)
        if not isinstance(pillar, dict):
            errors.append(f"auto_meishiki.{pillar_key} がありません。")
            continue

        for value_key in ("tenkan", "chishi"):
            if pillar.get(value_key) is None:
                errors.append(f"auto_meishiki.{pillar_key}.{value_key} が None です。")

    return _build_smoke_check(ok=not errors, errors=errors)


def _get_smoke_calculation_date(auto_meishiki):
    if not isinstance(auto_meishiki, dict):
        return None

    calculation_datetime = auto_meishiki.get("calculation_datetime")
    if hasattr(calculation_datetime, "date"):
        return calculation_datetime.date()

    birth_info = auto_meishiki.get("birth_info")
    if isinstance(birth_info, dict):
        adjusted_birth_datetime = birth_info.get("adjusted_birth_datetime")
        if hasattr(adjusted_birth_datetime, "date"):
            return adjusted_birth_datetime.date()

    return None


def _run_gogyou_smoke_check(manual_meishiki, auto_meishiki) -> tuple[dict, dict | None]:
    try:
        calculation_date = _get_smoke_calculation_date(auto_meishiki)
        analysis_context = (
            build_analysis_context(calculation_date)
            if calculation_date is not None
            else None
        )
        gogyo_result = calculate_gogyo_scores_from_meishiki(
            manual_meishiki,
            analysis_context,
        )
        return _build_smoke_check(
            ok=True,
            data={
                "scores": gogyo_result.get("scores", {}),
                "formula_chishi": gogyo_result.get("formula_chishi", []),
                "special_flags_keys": list(gogyo_result.get("special_flags", {}).keys()),
            },
        ), gogyo_result
    except Exception as exc:
        return _build_smoke_check(ok=False, errors=[str(exc)]), None


def _run_special_chart_smoke_check(manual_meishiki, gogyo_result) -> dict:
    if gogyo_result is None:
        return _build_smoke_check(
            ok=None,
            skipped=True,
            reason="五行計算が成功していないため、特殊な命式判定はスキップしました。",
        )

    try:
        ijou_kanshi_data = build_ijou_kanshi_data_from_meishiki(manual_meishiki)
        special_rows = build_special_meishiki_rows(ijou_kanshi_data, gogyo_result)
        return _build_smoke_check(
            ok=True,
            data={
                "ijou_kanshi_data": ijou_kanshi_data,
                "special_rows": special_rows,
            },
        )
    except Exception as exc:
        return _build_smoke_check(ok=False, errors=[str(exc)])


def _run_getsurei_smoke_check(manual_meishiki) -> dict:
    try:
        getsurei_result = judge_getsurei_from_meishiki(manual_meishiki)
        return _build_smoke_check(
            ok=getsurei_result.get("ok") is True,
            errors=getsurei_result.get("errors", []),
            data=getsurei_result,
        )
    except Exception as exc:
        return _build_smoke_check(ok=False, errors=[str(exc)])


def _load_personality_logic_for_smoke_test():
    try:
        from personality_logic import get_juuni_unsei, get_kubou, get_tsuhensei
    except Exception as exc:
        return None, str(exc)

    return {
        "get_juuni_unsei": get_juuni_unsei,
        "get_kubou": get_kubou,
        "get_tsuhensei": get_tsuhensei,
    }, ""


def _run_personality_logic_smoke_checks(manual_meishiki) -> dict:
    functions, import_error = _load_personality_logic_for_smoke_test()
    if functions is None:
        skipped_check = _build_smoke_check(
            ok=None,
            skipped=True,
            reason=(
                "personality_logic.py が Streamlit 依存のため、"
                f"この実行環境ではインポートできずスキップしました: {import_error}"
            ),
        )
        return {
            "kuubou": skipped_check.copy(),
            "tsuhen": skipped_check.copy(),
            "zokkan_tsuhen": skipped_check.copy(),
            "juuni_unsei": skipped_check.copy(),
        }

    day_tenkan = manual_meishiki.get("day", {}).get("tenkan", "")
    day_chishi = manual_meishiki.get("day", {}).get("chishi", "")

    checks = {}
    try:
        checks["kuubou"] = _build_smoke_check(
            ok=True,
            data=functions["get_kubou"](day_tenkan, day_chishi),
        )
    except Exception as exc:
        checks["kuubou"] = _build_smoke_check(ok=False, errors=[str(exc)])

    try:
        checks["tsuhen"] = _build_smoke_check(
            ok=True,
            data={
                pillar_key: functions["get_tsuhensei"](
                    day_tenkan,
                    manual_meishiki.get(pillar_key, {}).get("tenkan", ""),
                )
                for pillar_key in ("hour", "month", "year")
            },
        )
    except Exception as exc:
        checks["tsuhen"] = _build_smoke_check(ok=False, errors=[str(exc)])

    try:
        checks["zokkan_tsuhen"] = _build_smoke_check(
            ok=True,
            data={
                pillar_key: functions["get_tsuhensei"](
                    day_tenkan,
                    manual_meishiki.get(pillar_key, {}).get("zokkan", ""),
                )
                for pillar_key in PILLAR_KEYS
            },
        )
    except Exception as exc:
        checks["zokkan_tsuhen"] = _build_smoke_check(ok=False, errors=[str(exc)])

    try:
        checks["juuni_unsei"] = _build_smoke_check(
            ok=True,
            data={
                pillar_key: functions["get_juuni_unsei"](
                    day_tenkan,
                    manual_meishiki.get(pillar_key, {}).get("chishi", ""),
                )
                for pillar_key in PILLAR_KEYS
            },
        )
    except Exception as exc:
        checks["juuni_unsei"] = _build_smoke_check(ok=False, errors=[str(exc)])

    return checks


def _build_skipped_check(reason: str) -> dict:
    return _build_smoke_check(ok=None, skipped=True, reason=reason)


def run_auto_meishiki_logic_smoke_test(auto_meishiki: dict) -> dict:
    """
    自動計算された auto_meishiki を既存の手入力 meishiki 形式へ変換し、
    既存ロジックに渡しても最低限エラーにならないかを確認する。

    この関数は開発用の内部検証であり、画面表示や本番鑑定には使わない。
    """
    result = {
        "ok": False,
        "manual_meishiki": None,
        "checks": {},
        "errors": [],
        "warnings": [],
    }

    auto_source_check = _validate_auto_meishiki_source(auto_meishiki)
    result["checks"]["auto_source"] = auto_source_check

    try:
        manual_meishiki = auto_meishiki_to_manual_format(auto_meishiki)
    except Exception as exc:
        error_message = f"auto_meishiki_to_manual_format() でエラーが発生しました: {exc}"
        result["errors"].append(error_message)
        result["checks"]["manual_format"] = _build_smoke_check(
            ok=False,
            errors=[error_message],
        )
        return result

    result["manual_meishiki"] = manual_meishiki
    manual_format_check = _validate_manual_meishiki_format(manual_meishiki)
    result["checks"]["manual_format"] = manual_format_check

    if not auto_source_check["ok"]:
        result["errors"].extend(auto_source_check["errors"])

    if not auto_source_check["ok"] or not manual_format_check["ok"]:
        result["errors"].extend(manual_format_check["errors"])
        skip_reason = "手入力 meishiki 形式チェックが失敗したため、既存ロジック呼び出しをスキップしました。"
        if not auto_source_check["ok"]:
            skip_reason = "auto_meishiki の元データチェックが失敗したため、既存ロジック呼び出しをスキップしました。"
        for check_name in (
            "gogyou",
            "special_chart",
            "kuubou",
            "tsuhen",
            "zokkan_tsuhen",
            "juuni_unsei",
            "getsurei",
        ):
            result["checks"][check_name] = _build_skipped_check(skip_reason)
        return result

    gogyou_check, gogyo_result = _run_gogyou_smoke_check(
        manual_meishiki,
        auto_meishiki,
    )
    result["checks"]["gogyou"] = gogyou_check
    result["checks"]["special_chart"] = _run_special_chart_smoke_check(
        manual_meishiki,
        gogyo_result,
    )

    result["checks"].update(_run_personality_logic_smoke_checks(manual_meishiki))
    result["checks"]["getsurei"] = _run_getsurei_smoke_check(manual_meishiki)

    for check_name, check in result["checks"].items():
        if check.get("skipped"):
            result["warnings"].append(
                f"{check_name}: {check.get('reason', 'スキップしました。')}"
            )
        if check.get("ok") is False:
            result["errors"].extend(check.get("errors", []))

    result["ok"] = not result["errors"]
    return result


# 日柱基準日は未確定であり、泰山流万年暦または信頼できる暦データとの照合が必要。
# この検証ランナーは、基準日を外から渡して差分検証できるようにするための土台である。
def run_validation_case(
    case: dict,
    risshun_datetime,
    sekki_entries,
    base_date,
    base_day_kanchi: str,
) -> dict:
    """
    1件の検証ケースを実行する。

    birth_datetime は "YYYY-MM-DD HH:MM" 形式の文字列を想定する。
    今回は出生地補正を行わず、raw_birth_datetime == adjusted_birth_datetime とする。
    """
    if not isinstance(case, dict):
        case = {}

    expected = case.get("expected", {})
    result = {
        "case_id": case.get("case_id"),
        "description": case.get("description", ""),
        "expected": deepcopy(expected) if isinstance(expected, dict) else {},
        "auto_meishiki": None,
        "comparison": {
            "matched": False,
            "differences": [],
            "checked": _build_checked_map(expected),
            "errors": [],
        },
        "matched": False,
    }

    try:
        birth_info = _build_birth_info_from_validation_case(case)
    except ValueError as exc:
        error_message = str(exc)
        result["error"] = error_message
        result["comparison"]["errors"].append(error_message)
        return result

    try:
        auto_meishiki = calculate_auto_meishiki(
            birth_info,
            risshun_datetime,
            sekki_entries,
            base_date,
            base_day_kanchi,
        )
    except Exception as exc:
        error_message = f"自動命式計算中にエラーが発生しました: {exc}"
        result["birth_info"] = birth_info
        result["error"] = error_message
        result["comparison"]["errors"].append(error_message)
        return result

    comparison = compare_auto_meishiki_with_expected(auto_meishiki, expected)

    if isinstance(auto_meishiki, dict) and auto_meishiki.get("error"):
        comparison["errors"].append(auto_meishiki["error"])
        comparison["matched"] = False

    result["birth_info"] = birth_info
    result["auto_meishiki"] = auto_meishiki
    result["comparison"] = comparison
    result["matched"] = comparison["matched"]

    return result


def run_validation_cases(
    risshun_datetime,
    sekki_entries,
    base_date,
    base_day_kanchi: str,
    cases=None,
) -> dict:
    """
    複数の検証ケースをまとめて実行する。

    cases が None の場合は get_validation_cases() を使う。
    """
    validation_cases = get_validation_cases() if cases is None else cases
    results = [
        run_validation_case(
            case,
            risshun_datetime,
            sekki_entries,
            base_date,
            base_day_kanchi,
        )
        for case in validation_cases
    ]
    matched_count = sum(1 for result in results if result.get("matched") is True)
    total = len(results)

    return {
        "total": total,
        "matched_count": matched_count,
        "unmatched_count": total - matched_count,
        "results": results,
    }


def _extract_actual_pillars(auto_meishiki) -> tuple[dict, list]:
    actual = {pillar_key: None for pillar_key in PILLAR_KEYS}
    errors = []

    if not isinstance(auto_meishiki, dict):
        errors.append("auto_meishiki がありません。")
        return actual, errors

    for pillar_key in PILLAR_KEYS:
        pillar_result = auto_meishiki.get(pillar_key)
        if not isinstance(pillar_result, dict):
            errors.append(f"auto_meishiki.{pillar_key} がありません。")
            continue

        actual[pillar_key] = pillar_result.get("kanchi")
        if actual[pillar_key] is None:
            errors.append(f"auto_meishiki.{pillar_key}.kanchi がありません。")

    return actual, errors


def _normalize_expected_pillars(expected) -> tuple[dict, list]:
    errors = []
    if not isinstance(expected, dict):
        expected = {}
        errors.append("expected がありません。")

    return {
        pillar_key: expected.get(pillar_key)
        for pillar_key in PILLAR_KEYS
    }, errors


def _collect_case_errors(case_result: dict, comparison, actual_errors: list) -> list:
    errors = []

    if not case_result.get("case_id"):
        errors.append("case_id がありません。")

    case_error = case_result.get("error")
    if case_error:
        errors.append(case_error)

    if not isinstance(comparison, dict):
        errors.append("comparison がありません。")
    else:
        comparison_errors = comparison.get("errors")
        if comparison_errors is None:
            comparison_errors = []
        if not isinstance(comparison_errors, list):
            comparison_errors = [comparison_errors]
        errors.extend(error for error in comparison_errors if error)

        if "differences" not in comparison:
            errors.append("comparison.differences がありません。")

    errors.extend(actual_errors)

    deduplicated_errors = []
    for error in errors:
        if error not in deduplicated_errors:
            deduplicated_errors.append(error)

    return deduplicated_errors


def _extract_differences(comparison) -> list:
    if not isinstance(comparison, dict):
        return []

    differences = comparison.get("differences", [])
    if not isinstance(differences, list):
        return []

    return differences


def summarize_validation_result(validation_result: dict) -> dict:
    """
    run_validation_cases() の戻り値を、人間が確認しやすい要約 dict に整形する。
    """
    top_level_errors = []
    if not isinstance(validation_result, dict):
        validation_result = {}
        top_level_errors.append("validation_result は dict である必要があります。")

    results = validation_result.get("results", [])
    if not isinstance(results, list):
        results = []
        top_level_errors.append("validation_result.results がありません。")

    case_summaries = []
    for case_result in results:
        if not isinstance(case_result, dict):
            case_result = {
                "case_id": None,
                "description": "",
                "expected": {},
                "auto_meishiki": None,
                "comparison": None,
                "matched": False,
                "error": "case_result は dict である必要があります。",
            }

        expected, expected_errors = _normalize_expected_pillars(
            case_result.get("expected")
        )
        actual, actual_errors = _extract_actual_pillars(
            case_result.get("auto_meishiki")
        )
        comparison = case_result.get("comparison")
        differences = _extract_differences(comparison)
        errors = _collect_case_errors(case_result, comparison, actual_errors)
        errors.extend(error for error in expected_errors if error not in errors)

        matched = (
            case_result.get("matched") is True
            and not differences
            and not errors
        )

        case_summaries.append(
            {
                "case_id": case_result.get("case_id") or "(case_idなし)",
                "description": case_result.get("description", ""),
                "matched": matched,
                "expected": expected,
                "actual": actual,
                "differences": differences,
                "errors": errors,
            }
        )

    total = len(case_summaries)
    matched_count = sum(1 for case_summary in case_summaries if case_summary["matched"])
    error_count = sum(1 for case_summary in case_summaries if case_summary["errors"])
    unmatched_count = total - matched_count

    return {
        "total": total,
        "matched_count": matched_count,
        "unmatched_count": unmatched_count,
        "error_count": error_count,
        "all_matched": total > 0 and matched_count == total and error_count == 0,
        "case_summaries": case_summaries,
        "errors": top_level_errors,
    }


def _format_pillars_for_text(pillars: dict) -> str:
    parts = []
    for pillar_key in PILLAR_KEYS:
        value = pillars.get(pillar_key)
        display_value = value if value is not None else "未設定"
        parts.append(f"{PILLAR_LABELS[pillar_key]}={display_value}")

    return " / ".join(parts)


def _format_difference_for_text(difference: dict) -> str:
    pillar = difference.get("pillar", "unknown")
    expected = difference.get("expected")
    actual = difference.get("actual")
    expected_text = expected if expected is not None else "未設定"
    actual_text = actual if actual is not None else "未設定"

    return f"- {pillar}: 期待={expected_text} / 計算={actual_text}"


def format_validation_summary_text(summary: dict) -> str:
    """
    summarize_validation_result() の結果を、コピーしやすいテキストに整形する。
    """
    if not isinstance(summary, dict):
        summary = summarize_validation_result(summary)

    lines = [
        "自動命式計算 検証結果",
        f"合計: {summary.get('total', 0)}件",
        f"一致: {summary.get('matched_count', 0)}件",
        f"不一致: {summary.get('unmatched_count', 0)}件",
        f"エラー: {summary.get('error_count', 0)}件",
        "",
    ]

    for case_summary in summary.get("case_summaries", []):
        errors = case_summary.get("errors", [])
        differences = case_summary.get("differences", [])
        if errors:
            status = "ERROR"
        elif case_summary.get("matched") is True:
            status = "OK"
        else:
            status = "NG"

        lines.extend(
            [
                f"[{status}] {case_summary.get('case_id', '(case_idなし)')}",
                f"説明: {case_summary.get('description', '')}",
                f"期待: {_format_pillars_for_text(case_summary.get('expected', {}))}",
                f"計算: {_format_pillars_for_text(case_summary.get('actual', {}))}",
            ]
        )

        if differences:
            lines.append("差分:")
            lines.extend(_format_difference_for_text(difference) for difference in differences)

        if errors:
            lines.append("エラー:")
            lines.extend(f"- {error}" for error in errors)

        lines.append("")

    return "\n".join(lines).rstrip()
