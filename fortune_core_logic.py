from __future__ import annotations

from comments import (
    JUUNI_UNSEI_COMMENTS,
    JUUNI_UNSEI_PILLAR_MEANINGS,
    MONTH_TSUHENSEI_PAIR_COMMENTS,
    NIKKAN_COMMENTS,
    TSUHENSEI_COMMENTS,
)
from fortune_data import (
    JUUNI_UNSEI_PILLAR_WEIGHTS,
    JUUNI_UNSEI_TABLE,
    JUUNI_UNSEI_THINKING_PILLAR_MEANINGS,
    JUUNI_UNSEI_THINKING_TENDENCY,
    KUBOU_MAP,
    TSUHENSEI_TABLE,
)


THINKING_CATEGORY_DEFINITIONS = [
    ("brain_type", "左脳／右脳", ["左脳", "右脳"]),
    ("merit_type", "メリット型／デメリット型", ["メリット型", "デメリット型"]),
    ("work_type", "仕事4分類", ["現場型攻め", "現場型守り", "管理型ムードメーカー", "管理型アイデアマン"]),
    ("goal_type", "目標への向かい方", ["目標直進型", "目標変化型"]),
    ("principle_type", "原理原則型／応用拡大型", ["原理原則型", "応用拡大型"]),
]

BRAIN_TYPE_ORDER = ["左脳", "右脳"]
MERIT_TYPE_ORDER = ["メリット型", "デメリット型"]
GOAL_TYPE_ORDER = ["目標直進型", "目標変化型"]
PRINCIPLE_TYPE_ORDER = ["原理原則型", "応用拡大型"]
WORK_TYPE_ORDER = [
    "現場型攻め",
    "現場型守り",
    "管理型ムードメーカー",
    "管理型アイデアマン",
]

JUUNI_UNSEI_PERSONALITY_HEADINGS = {
    "year": "意思決定の時の自分",
    "month": "初対面の人と会った時の自分",
    "day": "一人の時の自分",
    "hour": "どんな老後を過ごしたいか",
}

JUUNI_UNSEI_PERSONALITY_WEIGHTS = {
    "year": "15%",
    "month": "30%",
    "day": "50%",
    "hour": "5%",
}


def get_tsuhensei(day_tenkan, target_tenkan):
    if not day_tenkan or not target_tenkan:
        return ""
    return TSUHENSEI_TABLE.get(day_tenkan, {}).get(target_tenkan, "")


def get_kubou(day_tenkan, day_chishi):
    if not day_tenkan or not day_chishi:
        return ""
    return KUBOU_MAP.get(f"{day_tenkan}{day_chishi}", "")


def get_juuni_unsei(day_tenkan, chishi):
    if not day_tenkan or not chishi:
        return ""
    return JUUNI_UNSEI_TABLE.get(day_tenkan, {}).get(chishi, "")


def get_nikkan_comment(day_tenkan):
    return NIKKAN_COMMENTS.get(day_tenkan, {})


def get_tsuhensei_comment(tsuhensei, comment_type):
    if not tsuhensei or tsuhensei == "－":
        return ""
    return TSUHENSEI_COMMENTS.get(tsuhensei, {}).get(comment_type, "")


def get_month_pair_comment(center_star, tsuhensei, comment_type):
    if not center_star or not tsuhensei or center_star == "－" or tsuhensei == "－":
        return ""
    return MONTH_TSUHENSEI_PAIR_COMMENTS.get(
        f"{center_star}{tsuhensei}",
        {},
    ).get(comment_type, "")


def get_juuni_unsei_comment(juuni_unsei, comment_type):
    if not juuni_unsei:
        return ""
    return JUUNI_UNSEI_COMMENTS.get(juuni_unsei, {}).get(comment_type, "")


def get_juuni_unsei_display_name(juuni_unsei):
    return juuni_unsei or "未入力"


def get_juuni_unsei_group_display(juuni_unsei):
    if not juuni_unsei:
        return "未入力"
    return JUUNI_UNSEI_COMMENTS.get(juuni_unsei, {}).get("group", "未登録")


def get_juuni_unsei_keywords_display(juuni_unsei):
    if not juuni_unsei:
        return "未入力"
    keywords = JUUNI_UNSEI_COMMENTS.get(juuni_unsei, {}).get("keywords", [])
    return "・".join(keywords) if keywords else "未登録"


def get_juuni_unsei_theme_display(pillar_key):
    pillar_meaning = JUUNI_UNSEI_PILLAR_MEANINGS.get(pillar_key, {})
    main_theme = pillar_meaning.get("main_theme", "未登録")
    keyword = pillar_meaning.get("keyword", "未登録")
    return f"{main_theme}（{keyword}）"


def get_juuni_unsei_reading_points_display(pillar_key):
    points = JUUNI_UNSEI_PILLAR_MEANINGS.get(pillar_key, {}).get("reading_points", [])
    return "・".join(points) if points else "未登録"


def get_juuni_unsei_thinking_tendency(juuni_unsei):
    if not juuni_unsei:
        return {}
    return JUUNI_UNSEI_THINKING_TENDENCY.get(juuni_unsei, {})


def aggregate_juuni_unsei_thinking_tendency(pillar_juuni_unsei_data):
    categories = {
        category_key: {}
        for category_key, _category_title, _category_labels in THINKING_CATEGORY_DEFINITIONS
    }

    for pillar_key, juuni_unsei in pillar_juuni_unsei_data.items():
        weight = JUUNI_UNSEI_PILLAR_WEIGHTS.get(pillar_key, 0)
        tendency = get_juuni_unsei_thinking_tendency(juuni_unsei)
        if not tendency:
            continue

        for category_key in categories.keys():
            label = tendency.get(category_key)
            if not label:
                continue
            categories[category_key][label] = categories[category_key].get(label, 0) + weight

    return categories


def fill_missing_scores(score_dict, labels):
    return {label: score_dict.get(label, 0) for label in labels}


def build_juuni_unsei_summary_data(juuni_unsei_display_data):
    rows = []
    for data in juuni_unsei_display_data:
        pillar_key = data["pillar_key"]
        juuni_unsei = data.get("juuni_unsei", "")
        rows.append({
            "pillar_key": pillar_key,
            "pillar_label": data.get("pillar_label", ""),
            "personality_heading": data.get(
                "personality_heading",
                JUUNI_UNSEI_PERSONALITY_HEADINGS.get(pillar_key, ""),
            ),
            "personality_weight": JUUNI_UNSEI_PERSONALITY_WEIGHTS.get(pillar_key, ""),
            "juuni_unsei": get_juuni_unsei_display_name(juuni_unsei),
            "group": get_juuni_unsei_group_display(juuni_unsei),
            "theme": get_juuni_unsei_theme_display(pillar_key),
            "reading_points": get_juuni_unsei_reading_points_display(pillar_key),
            "keywords": get_juuni_unsei_keywords_display(juuni_unsei),
            "public_comment": get_juuni_unsei_comment(juuni_unsei, "public"),
            "private_comment": get_juuni_unsei_comment(juuni_unsei, "private"),
        })
    return rows


def build_thinking_chart_data(juuni_unsei_by_pillar):
    aggregated_scores = aggregate_juuni_unsei_thinking_tendency(juuni_unsei_by_pillar)
    return {
        "brain_type": fill_missing_scores(
            aggregated_scores.get("brain_type", {}),
            BRAIN_TYPE_ORDER,
        ),
        "merit_type": fill_missing_scores(
            aggregated_scores.get("merit_type", {}),
            MERIT_TYPE_ORDER,
        ),
        "work_type": fill_missing_scores(
            aggregated_scores.get("work_type", {}),
            WORK_TYPE_ORDER,
        ),
        "goal_type": fill_missing_scores(
            aggregated_scores.get("goal_type", {}),
            GOAL_TYPE_ORDER,
        ),
        "principle_type": fill_missing_scores(
            aggregated_scores.get("principle_type", {}),
            PRINCIPLE_TYPE_ORDER,
        ),
        "pillar_meanings": JUUNI_UNSEI_THINKING_PILLAR_MEANINGS,
    }
