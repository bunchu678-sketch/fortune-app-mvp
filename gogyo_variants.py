"""Additive A/B/C gogyou results for the future product UI."""
from gogyou_external_effects import calculate_gogyo_scores_with_external_effects
from gogyou_logic import calculate_gogyo_scores_from_meishiki, get_gogyo_chart_order
from meishiki_model import build_analysis_context
from daiun_logic import select_current_daiun
from special_chart_logic import build_special_meishiki_rows


def _available(result, ijou_kanshi_data, chart_order):
    return {
        "status": "available",
        "gogyo": {**result, "chart_order": chart_order},
        "special_meishiki": build_special_meishiki_rows(ijou_kanshi_data, result),
    }


def build_gogyo_variants(
    meishiki, birth_date, reading_date, reading_choice, reading_pending,
    daiun_result, ijou_kanshi_data, day_tenkan, reading_boundary=None,
):
    """Calculate each available variant afresh from the unmodified natal chart."""
    chart_order = get_gogyo_chart_order(day_tenkan)
    context = None if reading_pending else build_analysis_context(reading_date, reading_choice)
    natal = calculate_gogyo_scores_from_meishiki(
        meishiki, context, include_kantei_year_gogyo_effects=False,
    )
    variants = {"A": _available(natal, ijou_kanshi_data, chart_order)}
    if reading_pending:
        pending = {"status": "boundary_pending", "reason": "reading_risshun",
                   "boundary_datetime": reading_boundary.isoformat()}
        variants["B"] = pending.copy()
        variants["C"] = pending.copy()
        return variants

    year = calculate_gogyo_scores_from_meishiki(
        meishiki, context, include_kantei_year_gogyo_effects=True,
    )
    variants["B"] = _available(year, ijou_kanshi_data, chart_order)
    selected = select_current_daiun(daiun_result, birth_date, reading_date)
    if not selected["ok"]:
        variants["C"] = {
            "status": "unavailable",
            "reason": selected["reason"],
            "age": selected.get("age"),
        }
        return variants

    row = selected["row"]
    combined = calculate_gogyo_scores_with_external_effects(
        meishiki,
        [
            {"source": "kantei_year", "tenkan": context["target_year_tenkan"],
             "chishi": context["target_year_chishi"]},
            {"source": "daiun", "tenkan": row["天干"], "chishi": row["地支"]},
        ],
    )
    variants["C"] = {
        **_available(combined, ijou_kanshi_data, chart_order),
        "age": selected["age"],
        "daiun": {
            "name": row["大運"],
            "kanshi": row["大運干支"],
            "tenkan": row["天干"],
            "chishi": row["地支"],
        },
    }
    return variants
