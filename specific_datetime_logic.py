from __future__ import annotations

from datetime import date, datetime, time as datetime_time

from calendar_logic import calculate_day_pillar
from calendar_reference import get_calendar_context_for_birth_year
from personality_logic import get_tsuhensei


SPECIFIC_DATETIME_KEYWORDS = {
    "比肩": "自分で決めて動く日。開始・決断・独立的な行動に向く。独断になりすぎないよう注意。",
    "劫財": "人との連携や交渉が鍵になる日。仲間づくり、調整、巻き込みに向く。浪費や勢い任せに注意。",
    "食神": "楽しさ、発信、交流に向く日。会食、PR、紹介、体験づくりに良い。気の緩みやうっかりに注意。",
    "傷官": "感性や表現が鋭くなる日。企画、文章、改善提案に向く。言葉が強くなりすぎないよう注意。",
    "偏財": "出会い、営業、情報収集に向く日。人脈づくりや外向きの行動に良い。広げすぎには注意。",
    "正財": "堅実に形を作る日。契約、整理、金銭管理、積み上げに向く。慎重になりすぎて動きが遅れないよう注意。",
    "偏官": "動きと突破の日。挑戦、移動、決断、環境を変える行動に向く。焦りや強引さに注意。",
    "正官": "信頼、責任、正式な場に向く日。面談、契約、申請、約束事に良い。形式や礼儀を大切に。",
    "偏印": "発想、見直し、方向転換の日。企画、学び直し、整理、違う視点を得る行動に向く。迷いすぎに注意。",
    "印綬": "学び、準備、相談に向く日。先生・専門家への相談、情報整理、計画作成に良い。受け身になりすぎないよう注意。",
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

    tenkan = day_result.get("tenkan", "")
    chishi = day_result.get("chishi", "")
    tsuhensei = get_tsuhensei(day_tenkan, tenkan)

    return {
        "ok": True,
        "label": label,
        "datetime": target_datetime,
        "display_datetime": format_specific_datetime_label(target_datetime),
        "day_kanchi": day_result.get("day_kanchi", ""),
        "tenkan": tenkan,
        "chishi": chishi,
        "tsuhensei": tsuhensei,
        "keyword": SPECIFIC_DATETIME_KEYWORDS.get(tsuhensei, ""),
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
