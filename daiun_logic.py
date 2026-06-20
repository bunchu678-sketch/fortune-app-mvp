from __future__ import annotations

from datetime import date, datetime

from calendar_logic import shift_kanchi, split_kanchi
from fortune_data import JUUNI_UNSEI_TABLE, TSUHENSEI_TABLE


YANG_TENKAN = {"甲", "丙", "戊", "庚", "壬"}
YIN_TENKAN = {"乙", "丁", "己", "辛", "癸"}
MALE_LABELS = {"男", "男性"}
FEMALE_LABELS = {"女", "女性"}


def normalize_to_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def is_yang_tenkan(tenkan):
    return tenkan in YANG_TENKAN


def normalize_gender(gender):
    if not isinstance(gender, str):
        return ""

    normalized = gender.strip()
    if normalized in MALE_LABELS:
        return "male"
    if normalized in FEMALE_LABELS:
        return "female"
    return ""


def determine_daiun_direction(year_tenkan, gender):
    gender_key = normalize_gender(gender)
    if year_tenkan not in YANG_TENKAN and year_tenkan not in YIN_TENKAN:
        return {
            "ok": False,
            "direction": "",
            "label": "",
            "message": "年干を確認できませんでした。",
        }
    if not gender_key:
        return {
            "ok": False,
            "direction": "",
            "label": "",
            "message": "性別を選択すると大運を表示できます。",
        }

    year_is_yang = is_yang_tenkan(year_tenkan)
    is_forward = (
        (year_is_yang and gender_key == "male")
        or (not year_is_yang and gender_key == "female")
    )
    return {
        "ok": True,
        "direction": "forward" if is_forward else "reverse",
        "label": "順行" if is_forward else "逆行",
        "step": 1 if is_forward else -1,
        "message": "",
    }


def find_previous_and_next_sekki(birth_date, sekki_entries):
    target_date = normalize_to_date(birth_date)
    if target_date is None:
        return {
            "previous": None,
            "next": None,
        }

    previous_entry = None
    next_entry = None
    sorted_entries = sorted(
        (entry for entry in sekki_entries or [] if entry.get("datetime")),
        key=lambda entry: entry["datetime"],
    )

    for entry in sorted_entries:
        entry_date = normalize_to_date(entry.get("datetime"))
        if entry_date is None:
            continue
        if entry_date <= target_date:
            previous_entry = entry
        if entry_date >= target_date and next_entry is None:
            next_entry = entry

    return {
        "previous": previous_entry,
        "next": next_entry,
    }


def calculate_kigun_age_by_days(birth_date, target_sekki_date):
    birth = normalize_to_date(birth_date)
    target = normalize_to_date(target_sekki_date)
    if birth is None or target is None:
        return None

    day_diff = abs((target - birth).days)
    if day_diff <= 3:
        return 1

    return max(1, int(day_diff / 3 + 0.5))


def format_age(age_int):
    if age_int is None:
        return ""
    return f"{int(age_int)}歳"


def _get_tsuhensei(day_tenkan, target_tenkan):
    try:
        from personality_logic import get_tsuhensei

        return get_tsuhensei(day_tenkan, target_tenkan)
    except Exception:
        return TSUHENSEI_TABLE.get(day_tenkan, {}).get(target_tenkan, "")


def _get_juuni_unsei(day_tenkan, chishi):
    try:
        from personality_logic import get_juuni_unsei

        return get_juuni_unsei(day_tenkan, chishi)
    except Exception:
        return JUUNI_UNSEI_TABLE.get(day_tenkan, {}).get(chishi, "")


def _build_empty_result(message):
    return {
        "ok": False,
        "direction": "",
        "direction_label": "",
        "kigun_age": None,
        "rows": [],
        "message": message,
    }


def build_daiun_table(
    birth_date,
    birth_year,
    gender,
    year_tenkan,
    month_kanchi,
    day_tenkan,
    sekki_entries,
    count=10,
):
    direction = determine_daiun_direction(year_tenkan, gender)
    if not direction["ok"]:
        return _build_empty_result(direction["message"])

    if not birth_date or not birth_year:
        return _build_empty_result("生年月日を確認できませんでした。")
    if not month_kanchi or len(month_kanchi) != 2:
        return _build_empty_result("月柱を確認できませんでした。")
    if not day_tenkan:
        return _build_empty_result("日干を確認できませんでした。")

    sekki_pair = find_previous_and_next_sekki(birth_date, sekki_entries)
    target_entry = (
        sekki_pair["next"]
        if direction["direction"] == "forward"
        else sekki_pair["previous"]
    )
    if not target_entry:
        return _build_empty_result("大運を表示するための暦情報を確認できませんでした。")

    kigun_age = calculate_kigun_age_by_days(
        birth_date,
        target_entry.get("datetime"),
    )
    if kigun_age is None:
        return _build_empty_result("起運年齢を計算できませんでした。")

    rows = []
    step = direction["step"]
    for index in range(1, int(count) + 1):
        offset = step * index
        daiun_kanchi = shift_kanchi(month_kanchi, offset)
        tenkan, chishi = split_kanchi(daiun_kanchi)
        start_age = kigun_age + (index - 1) * 10
        end_age = start_age + 9
        rows.append({
            "大運": f"第{index}大運",
            "開始年齢": format_age(start_age),
            "終了年齢": format_age(end_age),
            "目安開始年": int(birth_year) + start_age,
            "目安終了年": int(birth_year) + end_age,
            "大運干支": daiun_kanchi,
            "天干": tenkan,
            "地支": chishi,
            "通変星": _get_tsuhensei(day_tenkan, tenkan),
            "十二運星": _get_juuni_unsei(day_tenkan, chishi),
            "コメント": "",
        })

    return {
        "ok": True,
        "direction": direction["direction"],
        "direction_label": direction["label"],
        "kigun_age": kigun_age,
        "rows": rows,
        "message": "",
    }
