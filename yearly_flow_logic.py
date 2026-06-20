from __future__ import annotations

from datetime import date, datetime, time as datetime_time

from calendar_logic import calculate_month_pillar, calculate_year_pillar
from calendar_reference import get_calendar_context_for_birth_year
from daiun_logic import DAIUN_TSUHENSEI_COMMENTS
from personality_logic import get_tsuhensei


CHISHI_SET = {"子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"}


def normalize_to_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.today()


def split_kubou_branches(kubou):
    if not isinstance(kubou, str):
        return set()

    return {char for char in kubou if char in CHISHI_SET}


def is_kubou_branch(branch, kubou):
    if not branch:
        return False

    return branch in split_kubou_branches(kubou)


def get_yearly_flow_month_targets(base_year):
    return [(base_year, month) for month in range(2, 13)] + [(base_year + 1, 1)]


def build_yearly_monthly_flow(reading_date, day_tenkan, kubou):
    base_date = normalize_to_date(reading_date)
    base_year = base_date.year
    rows = []
    errors = []

    for target_year, target_month in get_yearly_flow_month_targets(base_year):
        row = build_yearly_monthly_flow_row(
            target_year=target_year,
            target_month=target_month,
            day_tenkan=day_tenkan,
            kubou=kubou,
        )
        rows.append(row)
        if row.get("error"):
            errors.append(row["error"])

    return {
        "ok": not errors,
        "base_year": base_year,
        "rows": rows,
        "errors": errors,
    }


def build_yearly_monthly_flow_row(target_year, target_month, day_tenkan, kubou):
    representative_datetime = datetime.combine(
        date(int(target_year), int(target_month), 15),
        datetime_time(12, 0),
    )
    display_month = f"{target_year}年{target_month}月"

    calendar_context = get_calendar_context_for_birth_year(target_year)
    if not calendar_context.get("ok"):
        return build_error_row(
            display_month,
            target_year,
            target_month,
            representative_datetime,
            "月干支を計算できませんでした。",
        )

    try:
        year_result = calculate_year_pillar(
            representative_datetime,
            calendar_context["risshun_datetime"],
        )
        month_result = calculate_month_pillar(
            representative_datetime,
            year_result["tenkan"],
            calendar_context["sekki_entries"],
        )
    except Exception:
        return build_error_row(
            display_month,
            target_year,
            target_month,
            representative_datetime,
            "月干支を計算できませんでした。",
        )

    if month_result.get("error"):
        return build_error_row(
            display_month,
            target_year,
            target_month,
            representative_datetime,
            "月干支を計算できませんでした。",
        )

    tenkan = month_result.get("tenkan", "")
    chishi = month_result.get("chishi", "")
    month_kanchi = month_result.get("month_kanchi", "")
    tsuhensei = get_tsuhensei(day_tenkan, tenkan)

    return {
        "月": display_month,
        "年": target_year,
        "月番号": target_month,
        "代表日": representative_datetime.date(),
        "月干支": month_kanchi,
        "天干": tenkan,
        "地支": chishi,
        "通変星": tsuhensei,
        "コメント": DAIUN_TSUHENSEI_COMMENTS.get(tsuhensei, ""),
        "空亡": is_kubou_branch(chishi, kubou),
        "error": "",
    }


def build_error_row(display_month, target_year, target_month, representative_datetime, message):
    return {
        "月": display_month,
        "年": target_year,
        "月番号": target_month,
        "代表日": representative_datetime.date(),
        "月干支": "",
        "天干": "",
        "地支": "",
        "通変星": "",
        "コメント": "",
        "空亡": False,
        "error": message,
    }
