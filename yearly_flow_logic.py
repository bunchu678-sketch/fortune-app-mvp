from __future__ import annotations

from datetime import date, datetime, time as datetime_time

from calendar_logic import calculate_month_pillar, calculate_year_pillar
from calendar_reference import get_calendar_context_for_birth_year
from fortune_core_logic import get_tsuhensei


CHISHI_SET = {"子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"}
YEARLY_FLOW_TSUHENSEI_COMMENTS = {
    "比肩": {
        "keywords": "自分軸、決断、積極的、再出発",
        "comment": "自分の考えをはっきりさせて動きたい月です。自分で決めて一歩進めることが大切です。新しいことを始めるチャンス。",
    },
    "劫財": {
        "keywords": "仲間、競争、調整、出費管理",
        "comment": "人との関わりが増えやすい月です。予定外の出費や気疲れも出やすくなります。身体に疲れが出やすいので注意。",
    },
    "食神": {
        "keywords": "調整、発信、交流、健康管理",
        "comment": "体調もよく、人間関係も良好な月です。一方で、頑張りすぎて体調を崩しがちです。うっかりミスもでやすい時期。",
    },
    "傷官": {
        "keywords": "直観、感性、紛争、急成長",
        "comment": "感性が鋭くなり、違和感や改善点に気づきやすい月です。言葉は柔らかく伝えることを意識。",
    },
    "偏財": {
        "keywords": "奉仕、出会い、人脈、情報収集",
        "comment": "外へ出ることで流れが広がりやすい月です。出会いたい人をイメージして出かけるとよい。",
    },
    "正財": {
        "keywords": "収穫、資産、努力、管理",
        "comment": "現実的な成果を積み上げるのに向いた月です。努力した分だけ成果が得られるチャンス到来。",
    },
    "偏官": {
        "keywords": "転換、変動、拡大、優先順位",
        "comment": "自然と意識が外へ向かい、思い切った行動を取りやすい月です。今までできなかったことを試すとよい。",
    },
    "正官": {
        "keywords": "責任、信頼、完成、名誉",
        "comment": "冷静に正しい判断ができ、長期計画を立てるのに向いた月です。金運もアップ。名誉を大切にするとよい。",
    },
    "偏印": {
        "keywords": "変化、開発、学び直し、新しい価値観",
        "comment": "迷いや悩みが尽きず、気分的にすっきりしない月です。慌てず、整理整頓をして、自分の力を蓄えてください。",
    },
    "印綬": {
        "keywords": "反省、研究、相談、問題から逃げない",
        "comment": "反省すべき点をきちんと振り返るのに向いた月です。先生や専門家に相談するとよい。学びの吸収力がアップ。",
    },
}


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
    comment_data = YEARLY_FLOW_TSUHENSEI_COMMENTS.get(tsuhensei, {})

    return {
        "月": display_month,
        "年": target_year,
        "月番号": target_month,
        "代表日": representative_datetime.date(),
        "月干支": month_kanchi,
        "天干": tenkan,
        "地支": chishi,
        "通変星": tsuhensei,
        "キーワード": comment_data.get("keywords", ""),
        "コメント": comment_data.get("comment", ""),
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
        "キーワード": "",
        "コメント": "",
        "空亡": False,
        "error": message,
    }
