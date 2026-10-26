from __future__ import annotations

from yearly_overall_comments import interpretation_fields
from datetime import date, datetime, time as datetime_time

from calendar_logic import calculate_year_pillar
from calendar_reference import get_calendar_context_for_birth_year
from fortune_core_logic import get_tsuhensei




def normalize_to_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.today()


def build_yearly_overall_fortune(reading_date, day_tenkan, calendar_context=None):
    base_date = normalize_to_date(reading_date)
    year = base_date.year
    representative_datetime = datetime.combine(
        date(year, 2, 15),
        datetime_time(12, 0),
    )
    context = calendar_context or get_calendar_context_for_birth_year(year)

    if not context.get("ok"):
        return {
            "ok": False,
            "year": year,
            "year_kanchi": "",
            "tenkan": "",
            "chishi": "",
            "tsuhensei": "",
            "theme": "",
            "comment": "",
            "error": "年干支を計算できませんでした。",
        }

    try:
        year_result = calculate_year_pillar(
            representative_datetime,
            context["risshun_datetime"],
        )
    except Exception:
        return {
            "ok": False,
            "year": year,
            "year_kanchi": "",
            "tenkan": "",
            "chishi": "",
            "tsuhensei": "",
            "theme": "",
            "comment": "",
            "error": "年干支を計算できませんでした。",
        }

    tenkan = year_result.get("tenkan", "")
    chishi = year_result.get("chishi", "")
    tsuhensei = get_tsuhensei(day_tenkan, tenkan)

    return {
        "ok": True,
        "year": year,
        "year_kanchi": year_result.get("year_kanchi", ""),
        "tenkan": tenkan,
        "chishi": chishi,
        "tsuhensei": tsuhensei,
        **interpretation_fields(year, tsuhensei),
        "error": "",
    }
