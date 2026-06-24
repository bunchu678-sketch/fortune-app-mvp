import pandas as pd
import streamlit as st

from chart_render import show_100_percent_stacked_bar, show_pie_chart
from comments import (
    NIKKAN_COMMENTS,
    TSUHENSEI_COMMENTS,
    MONTH_TSUHENSEI_PAIR_COMMENTS,
    JUUNI_UNSEI_COMMENTS,
    JUUNI_UNSEI_PILLAR_MEANINGS,
)
from fortune_data import (
    KUBOU_MAP,
    JUUNI_UNSEI_TABLE,
    JUUNI_UNSEI_THINKING_TENDENCY,
    JUUNI_UNSEI_PILLAR_WEIGHTS,
    JUUNI_UNSEI_THINKING_PILLAR_MEANINGS,
    TSUHENSEI_TABLE,
)
from utils import format_score_percent

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


def get_tsuhensei(day_tenkan, target_tenkan):
    """
    日干を基準に、対象の天干の通変星を返す。
    未入力の場合は空欄を返す。
    """
    if not day_tenkan or not target_tenkan:
        return ""
    return TSUHENSEI_TABLE.get(day_tenkan, {}).get(target_tenkan, "")


def get_kubou(day_tenkan, day_chishi):
    if not day_tenkan or not day_chishi:
        return ""

    day_kanshi = f"{day_tenkan}{day_chishi}"
    return KUBOU_MAP.get(day_kanshi, "")


def get_juuni_unsei(day_tenkan, chishi):
    """
    日干を基準に、対象の地支の十二運星を返す。
    未入力の場合は空欄を返す。
    """
    if not day_tenkan or not chishi:
        return ""

    return JUUNI_UNSEI_TABLE.get(day_tenkan, {}).get(chishi, "")


def get_tsuhensei_comment(tsuhensei, comment_type):
    if not tsuhensei or tsuhensei == "－":
        return ""
    comment = TSUHENSEI_COMMENTS.get(tsuhensei)
    if not comment:
        return ""
    return comment.get(comment_type, "")


def get_month_pair_comment(center_star, tsuhensei, comment_type):
    if not center_star or not tsuhensei:
        return ""
    if center_star == "－" or tsuhensei == "－":
        return ""
    key = f"{center_star}{tsuhensei}"
    comment = MONTH_TSUHENSEI_PAIR_COMMENTS.get(key)
    if not comment:
        return ""
    return comment.get(comment_type, "")


def get_juuni_unsei_comment(juuni_unsei, comment_type):
    if not juuni_unsei:
        return ""

    comment = JUUNI_UNSEI_COMMENTS.get(juuni_unsei)

    if not comment:
        return ""

    return comment.get(comment_type, "")


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


def normalize_thinking_scores(category_key, scores):
    category_labels = []

    for definition_key, _category_title, definition_labels in THINKING_CATEGORY_DEFINITIONS:
        if definition_key == category_key:
            category_labels = definition_labels
            break

    normalized_scores = {label: scores.get(label, 0) for label in category_labels}

    for label, score in scores.items():
        if label not in normalized_scores:
            normalized_scores[label] = score

    return normalized_scores


def fill_missing_scores(score_dict, labels):
    return {
        label: score_dict.get(label, 0)
        for label in labels
    }


def get_tsuhensei_display_name(tsuhensei):
    if tsuhensei == "－":
        return "－"
    if not tsuhensei:
        return "未入力"
    return tsuhensei


def write_tsuhensei_comment(tsuhensei, comment_type):
    if not tsuhensei or tsuhensei == "－":
        st.write("未入力")
        return
    comment_text = get_tsuhensei_comment(tsuhensei, comment_type)
    if comment_text:
        st.write(comment_text)
    else:
        st.write("この通変星のコメントは未登録です。")


def render_nikkan_public_comment(day_tenkan):
    if day_tenkan:
        nikkan_comment = NIKKAN_COMMENTS.get(day_tenkan)
        if nikkan_comment:
            st.markdown("**性格の傾向：**")
            st.write(nikkan_comment["description"])
            st.markdown(f"**キーワード：** {nikkan_comment['keywords']}")
        else:
            st.write("日干コメントが未登録です。")
    else:
        st.write("日干が未入力です。")


def render_life_stage_tsuhensei_table(life_stage_tsuhensei_data):
    st.table({
        "年代": [stage_data["stage"] for stage_data in life_stage_tsuhensei_data],
        "外側に見せている自分像": [
            get_tsuhensei_display_name(stage_data["outer"])
            for stage_data in life_stage_tsuhensei_data
        ],
        "本来の自分像": [
            get_tsuhensei_display_name(stage_data["inner"])
            for stage_data in life_stage_tsuhensei_data
        ],
    })


def render_public_tsuhensei_comments(life_stage_tsuhensei_data):
    render_life_stage_tsuhensei_table(life_stage_tsuhensei_data)
    for stage_data in life_stage_tsuhensei_data:
        stage = stage_data["stage"]
        outer = stage_data["outer"]
        inner = stage_data["inner"]
        with st.expander(f"▼ {stage}の傾向"):
            st.markdown(f"**外側に見せている自分像：{get_tsuhensei_display_name(outer)}**")
            if outer != "－":
                write_tsuhensei_comment(outer, "public")

            st.markdown(f"**本来の自分像：{get_tsuhensei_display_name(inner)}**")
            write_tsuhensei_comment(inner, "public")


def render_private_tsuhensei_comments(life_stage_tsuhensei_data):
    render_life_stage_tsuhensei_table(life_stage_tsuhensei_data)
    for stage_data in life_stage_tsuhensei_data:
        stage = stage_data["stage"]
        outer = stage_data["outer"]
        inner = stage_data["inner"]
        with st.expander(f"▼ {stage}の鑑定メモ"):
            if outer == "－":
                st.write(f"内側：{get_tsuhensei_display_name(inner)}")
                st.markdown("**鑑定メモ：**")
                write_tsuhensei_comment(inner, "private")
            else:
                st.write(f"外側：{get_tsuhensei_display_name(outer)}")
                st.write(f"内側：{get_tsuhensei_display_name(inner)}")
                st.markdown("**外側のメモ：**")
                write_tsuhensei_comment(outer, "private")
                st.markdown("**内側のメモ：**")
                write_tsuhensei_comment(inner, "private")


def render_public_month_pair_comment(center_star, tsuhensei):
    with st.expander("月柱の中心星と通変星の組み合わせから読み取れる性格"):
        if not center_star or not tsuhensei or center_star == "－" or tsuhensei == "－":
            st.write("中心星または通変星が未入力のため、月柱の組み合わせコメントは表示できません。")
            return
        month_pair_key = f"{center_star}{tsuhensei}"
        st.write(f"中心星：{center_star}")
        st.write(f"通変星：{tsuhensei}")
        st.write(f"組み合わせ：{month_pair_key}")
        comment_text = get_month_pair_comment(center_star, tsuhensei, "public")
        if comment_text:
            st.write(comment_text)
        else:
            st.write("この組み合わせのコメントは未登録です。")


def render_private_month_pair_comment(center_star, tsuhensei):
    with st.expander("月柱の中心星と通変星の組み合わせメモ"):
        if not center_star or not tsuhensei or center_star == "－" or tsuhensei == "－":
            st.write("中心星または通変星が未入力のため、月柱の組み合わせコメントは表示できません。")
            return
        month_pair_key = f"{center_star}{tsuhensei}"
        st.write(f"中心星：{center_star}")
        st.write(f"通変星：{tsuhensei}")
        st.write(f"組み合わせ：{month_pair_key}")
        st.markdown("**鑑定メモ：**")
        comment_text = get_month_pair_comment(center_star, tsuhensei, "private")
        if comment_text:
            st.write(comment_text)
        else:
            st.write("この組み合わせの自分用メモは未登録です。")


def get_juuni_unsei_display_name(juuni_unsei):
    if not juuni_unsei:
        return "未入力"

    return juuni_unsei


def get_juuni_unsei_group_display(juuni_unsei):
    if not juuni_unsei:
        return "未入力"

    comment = JUUNI_UNSEI_COMMENTS.get(juuni_unsei)

    if not comment:
        return "未登録"

    return comment.get("group", "未登録")


def get_juuni_unsei_keywords_display(juuni_unsei):
    if not juuni_unsei:
        return "未入力"

    comment = JUUNI_UNSEI_COMMENTS.get(juuni_unsei)

    if not comment:
        return "未登録"

    keywords = comment.get("keywords", [])
    return "・".join(keywords) if keywords else "未登録"


def get_juuni_unsei_theme_display(pillar_key):
    pillar_meaning = JUUNI_UNSEI_PILLAR_MEANINGS.get(pillar_key, {})
    main_theme = pillar_meaning.get("main_theme", "未登録")
    keyword = pillar_meaning.get("keyword", "未登録")
    return f"{main_theme}（{keyword}）"


def get_juuni_unsei_reading_points_display(pillar_key):
    pillar_meaning = JUUNI_UNSEI_PILLAR_MEANINGS.get(pillar_key, {})
    reading_points = pillar_meaning.get("reading_points", [])
    return "・".join(reading_points) if reading_points else "未登録"


def render_juuni_unsei_summary_table(juuni_unsei_display_data):
    st.table({
        "柱": [data["pillar_label"] for data in juuni_unsei_display_data],
        "十二運星": [
            get_juuni_unsei_display_name(data["juuni_unsei"])
            for data in juuni_unsei_display_data
        ],
        "分類": [
            get_juuni_unsei_group_display(data["juuni_unsei"])
            for data in juuni_unsei_display_data
        ],
        "読み解きテーマ": [
            get_juuni_unsei_theme_display(data["pillar_key"])
            for data in juuni_unsei_display_data
        ],
        "読み解きポイント": [
            get_juuni_unsei_reading_points_display(data["pillar_key"])
            for data in juuni_unsei_display_data
        ],
        "比率": [
            JUUNI_UNSEI_PILLAR_MEANINGS.get(data["pillar_key"], {}).get("weight", "未登録")
            for data in juuni_unsei_display_data
        ],
    })


def render_juuni_unsei_detail(data, comment_type):
    pillar_key = data["pillar_key"]
    pillar_label = data["pillar_label"]
    juuni_unsei = data["juuni_unsei"]
    juuni_unsei_display = get_juuni_unsei_display_name(juuni_unsei)
    expander_title = (
        f"{pillar_label}：{juuni_unsei_display} から読み取れる性格"
        if comment_type == "public"
        else f"{pillar_label}：{juuni_unsei_display} の鑑定メモ"
    )

    with st.expander(expander_title):
        st.write(f"{pillar_label}：{juuni_unsei_display}")

        if comment_type != "public":
            st.markdown("**読み解きテーマ：**")
            st.write(get_juuni_unsei_theme_display(pillar_key))

            st.markdown("**読み解きポイント：**")
            st.write(get_juuni_unsei_reading_points_display(pillar_key))

            st.markdown("**分類：**")
            st.write(get_juuni_unsei_group_display(juuni_unsei))

        st.markdown("**キーワード：**")
        st.write(get_juuni_unsei_keywords_display(juuni_unsei))

        if not juuni_unsei:
            st.write("十二運星が未入力です。")
            return

        label = "コメント：" if comment_type == "public" else "自分用メモ："
        st.markdown(f"**{label}**")

        comment_text = get_juuni_unsei_comment(juuni_unsei, comment_type)

        if comment_text:
            st.write(comment_text)
        else:
            st.write("この十二運星のコメントは未登録です。")


def render_public_juuni_unsei_comments(juuni_unsei_display_data):
    for data in juuni_unsei_display_data:
        render_juuni_unsei_detail(data, "public")


def render_private_juuni_unsei_comments(juuni_unsei_display_data):
    render_juuni_unsei_summary_table(juuni_unsei_display_data)

    for data in juuni_unsei_display_data:
        render_juuni_unsei_detail(data, "private")


def get_juuni_unsei_thinking_value(juuni_unsei, category_key):
    if not juuni_unsei:
        return "未入力"

    tendency = get_juuni_unsei_thinking_tendency(juuni_unsei)

    if not tendency:
        return "未登録"

    return tendency.get(category_key, "未登録")


def render_juuni_unsei_thinking_pillar_table(pillar_juuni_unsei_data):
    table_rows = []

    for pillar_key in ["hour", "day", "month", "year"]:
        pillar_meaning = JUUNI_UNSEI_THINKING_PILLAR_MEANINGS.get(pillar_key, {})
        juuni_unsei = pillar_juuni_unsei_data.get(pillar_key, "")
        weight = JUUNI_UNSEI_PILLAR_WEIGHTS.get(
            pillar_key,
            pillar_meaning.get("weight", 0),
        )

        table_rows.append({
            "柱": pillar_meaning.get("label", pillar_key),
            "役割": pillar_meaning.get("title", "未登録"),
            "十二運星": juuni_unsei if juuni_unsei else "未入力",
            "左脳／右脳": get_juuni_unsei_thinking_value(juuni_unsei, "brain_type"),
            "メリット／デメリット": get_juuni_unsei_thinking_value(juuni_unsei, "merit_type"),
            "仕事4分類": get_juuni_unsei_thinking_value(juuni_unsei, "work_type"),
            "目標への向かい方": get_juuni_unsei_thinking_value(juuni_unsei, "goal_type"),
            "考え方": get_juuni_unsei_thinking_value(juuni_unsei, "principle_type"),
            "比率": format_score_percent(weight),
        })

    st.table(pd.DataFrame(table_rows))


def render_juuni_unsei_thinking_score_table(aggregated_scores):
    table_rows = []

    for category_key, category_title, _category_labels in THINKING_CATEGORY_DEFINITIONS:
        score_dict = normalize_thinking_scores(
            category_key,
            aggregated_scores.get(category_key, {}),
        )

        for label, score in score_dict.items():
            table_rows.append({
                "集計項目": category_title,
                "分類": label,
                "割合": format_score_percent(score),
            })

    st.table(pd.DataFrame(table_rows))


def render_juuni_unsei_thinking_charts(aggregated_scores):
    with st.expander("考え方の傾向グラフ"):
        brain_type_scores = fill_missing_scores(
            aggregated_scores["brain_type"],
            BRAIN_TYPE_ORDER,
        )
        merit_type_scores = fill_missing_scores(
            aggregated_scores["merit_type"],
            MERIT_TYPE_ORDER,
        )
        goal_type_scores = fill_missing_scores(
            aggregated_scores["goal_type"],
            GOAL_TYPE_ORDER,
        )
        principle_type_scores = fill_missing_scores(
            aggregated_scores["principle_type"],
            PRINCIPLE_TYPE_ORDER,
        )
        work_type_scores = fill_missing_scores(
            aggregated_scores["work_type"],
            WORK_TYPE_ORDER,
        )

        show_100_percent_stacked_bar("左脳／右脳", brain_type_scores)
        show_100_percent_stacked_bar("メリット型／デメリット型", merit_type_scores)
        show_100_percent_stacked_bar("目標への向かい方", goal_type_scores)
        show_100_percent_stacked_bar("原理原則型／応用拡大型", principle_type_scores)
        show_pie_chart("仕事4分類", work_type_scores)


def render_juuni_unsei_thinking_tendency(pillar_juuni_unsei_data, is_private=False):
    if is_private:
        st.markdown("#### 十二運星から読み取れる考え方の傾向メモ")

    st.markdown("#### 四柱ごとの分類表")
    render_juuni_unsei_thinking_pillar_table(pillar_juuni_unsei_data)

    aggregated_scores = aggregate_juuni_unsei_thinking_tendency(pillar_juuni_unsei_data)

    st.markdown("#### 集計結果")
    render_juuni_unsei_thinking_score_table(aggregated_scores)
    render_juuni_unsei_thinking_charts(aggregated_scores)
