from __future__ import annotations

from datetime import date, datetime, time as datetime_time

from calendar_logic import calculate_day_pillar, calculate_hour_pillar
from calendar_reference import get_calendar_context_for_birth_year
from personality_logic import get_tsuhensei


SPECIFIC_DATETIME_TSUHENSEI_COMMENTS = {
    "比肩": {
        "keyword": "決断、出発",
        "comment": "新しいことを始めるのに向いているとき。自分で決めて一歩進めることが大切。",
    },
    "劫財": {
        "keyword": "仲間、調整",
        "comment": "人との関わりに向いているとき。一方で、予定外の出費や気疲れに注意。",
    },
    "食神": {
        "keyword": "研鑽、健康管理",
        "comment": "仕事や研鑽に向いているとき。体調も良いが、うっかりミスに注意。",
    },
    "傷官": {
        "keyword": "直観、感性",
        "comment": "感性が鋭くなるとき。違和感や改善点に気づきやすいが、その分イライラに注意。",
    },
    "偏財": {
        "keyword": "出会い、人脈、情報収集",
        "comment": "人との出会いに向いているとき。外に出ることで流れが広がりやすい。",
    },
    "正財": {
        "keyword": "収穫、努力",
        "comment": "努力の成果が出てくるとき。努力した分だけ成果が得られるチャンス到来。",
    },
    "偏官": {
        "keyword": "転換、拡大",
        "comment": "思い切った行動を取りやすいとき。今までできなかったことに挑戦する機会。",
    },
    "正官": {
        "keyword": "責任、名誉",
        "comment": "長期計画を立てるのに向いたとき。冷静に正しい判断ができる。実利より名誉を大切に。",
    },
    "偏印": {
        "keyword": "変化、整理",
        "comment": "気分的にすっきりしないとき。迷いや悩みが出てくるが、慌てずに考えを整理整頓しよう。",
    },
    "印綬": {
        "keyword": "反省、研究",
        "comment": "反省すべき点をきちんと振り返るのに向いたとき。信頼できる人に相談すると、学びの吸収力がアップ。",
    },
}


def normalize_candidate_datetime(candidate):
    if isinstance(candidate, datetime):
        return candidate.replace(second=0, microsecond=0)

    if not isinstance(candidate, dict):
        return None

    target_date = candidate.get("date")
    target_time = candidate.get("time")
    if not isinstance(target_date, date):
        return None
    if not isinstance(target_time, datetime_time):
        target_time = datetime_time(0, 0)

    return datetime.combine(target_date, target_time).replace(second=0, microsecond=0)


def format_specific_datetime_label(target_datetime):
    return (
        f"{target_datetime.year}年{target_datetime.month}月{target_datetime.day}日 "
        f"{target_datetime.hour:02d}:{target_datetime.minute:02d}"
    )


def format_specific_day_label(target_datetime):
    return f"{target_datetime.day}日"


def format_specific_time_label(target_datetime):
    return f"{target_datetime.hour}時{target_datetime.minute}分"


def get_specific_datetime_comment(tsuhensei):
    return SPECIFIC_DATETIME_TSUHENSEI_COMMENTS.get(
        tsuhensei,
        {"keyword": "", "comment": "コメント未設定"},
    )


def build_specific_datetime_part(display_name, kanchi, tenkan, chishi, base_day_tenkan):
    tsuhensei = get_tsuhensei(base_day_tenkan, tenkan)
    comment_data = get_specific_datetime_comment(tsuhensei)

    return {
        "display_name": display_name,
        "kanchi": kanchi,
        "tenkan": tenkan,
        "chishi": chishi,
        "tsuhensei": tsuhensei,
        "keyword": comment_data.get("keyword", ""),
        "comment": comment_data.get("comment", ""),
    }


def build_specific_datetime_fortune(candidate, day_tenkan, label=""):
    target_datetime = normalize_candidate_datetime(candidate)
    if target_datetime is None:
        return {
            "ok": False,
            "label": label,
            "datetime": None,
            "display_datetime": "",
            "day_kanchi": "",
            "tenkan": "",
            "chishi": "",
            "tsuhensei": "",
            "keyword": "",
            "comment": "",
            "parts": [],
            "error": "日時を確認できませんでした。",
        }

    calendar_context = get_calendar_context_for_birth_year(target_datetime.year)
    if not calendar_context.get("ok"):
        return build_specific_datetime_error(
            label,
            target_datetime,
            "日干支を計算できませんでした。",
        )

    try:
        day_result = calculate_day_pillar(
            target_datetime,
            calendar_context["base_date"],
            calendar_context["base_day_kanchi"],
        )
    except Exception:
        return build_specific_datetime_error(
            label,
            target_datetime,
            "日干支を計算できませんでした。",
        )

    try:
        hour_result = calculate_hour_pillar(target_datetime, day_result["tenkan"])
    except Exception:
        return build_specific_datetime_error(
            label,
            target_datetime,
            "時干支を計算できませんでした。",
        )

    tenkan = day_result.get("tenkan", "")
    chishi = day_result.get("chishi", "")
    tsuhensei = get_tsuhensei(day_tenkan, tenkan)
    comment_data = get_specific_datetime_comment(tsuhensei)
    day_part = build_specific_datetime_part(
        format_specific_day_label(target_datetime),
        day_result.get("day_kanchi", ""),
        tenkan,
        chishi,
        day_tenkan,
    )
    hour_part = build_specific_datetime_part(
        format_specific_time_label(target_datetime),
        hour_result.get("hour_kanchi", ""),
        hour_result.get("tenkan", ""),
        hour_result.get("chishi", ""),
        day_tenkan,
    )

    return {
        "ok": True,
        "label": label,
        "datetime": target_datetime,
        "display_datetime": format_specific_datetime_label(target_datetime),
        "day_kanchi": day_result.get("day_kanchi", ""),
        "tenkan": tenkan,
        "chishi": chishi,
        "tsuhensei": tsuhensei,
        "keyword": comment_data.get("keyword", ""),
        "comment": comment_data.get("comment", ""),
        "parts": [day_part, hour_part],
        "error": "",
    }


def build_specific_datetime_error(label, target_datetime, message):
    return {
        "ok": False,
        "label": label,
        "datetime": target_datetime,
        "display_datetime": format_specific_datetime_label(target_datetime),
        "day_kanchi": "",
        "tenkan": "",
        "chishi": "",
        "tsuhensei": "",
        "keyword": "",
        "comment": "",
        "parts": [],
        "error": message,
    }


def build_specific_datetime_fortunes(candidates, day_tenkan):
    rows = []
    errors = []

    for index, candidate in enumerate(candidates or [], start=1):
        row = build_specific_datetime_fortune(
            candidate,
            day_tenkan,
            label=f"候補{index}",
        )
        rows.append(row)
        if row.get("error"):
            errors.append(row["error"])

    return {
        "ok": not errors,
        "rows": rows,
        "errors": errors,
    }
