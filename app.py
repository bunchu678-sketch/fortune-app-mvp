from __future__ import annotations

import base64
import html
import math
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import date, datetime, time as datetime_time
from pathlib import Path

from calendar_logic import calculate_auto_meishiki
from calendar_reference import (
    get_calendar_context_for_birth_year,
    get_development_calendar_context,
)
from chart_render import render_gogyo_balance, show_gogyo_relationship_chart
from daiun_logic import (
    build_daiun_table,
    get_daiun_tsuhensei_summary,
)
from fortune_data import GOGYO_ORDER
from gogyou_logic import calculate_gogyo_scores_from_meishiki, init_gogyo_scores
from meishiki_validation import (
    format_validation_summary_text,
    run_auto_meishiki_logic_smoke_test,
    run_validation_cases,
    summarize_validation_result,
)
from meishiki_model import (
    auto_meishiki_to_manual_format,
    build_analysis_context,
    build_birth_info,
    build_meishiki_from_manual_input,
    select_effective_meishiki,
)
from personality_logic import (
    BRAIN_TYPE_ORDER,
    GOAL_TYPE_ORDER,
    MERIT_TYPE_ORDER,
    PRINCIPLE_TYPE_ORDER,
    WORK_TYPE_ORDER,
    aggregate_juuni_unsei_thinking_tendency,
    fill_missing_scores,
    get_month_pair_comment,
    get_kubou,
    get_juuni_unsei,
    get_tsuhensei,
    get_tsuhensei_display_name,
    render_juuni_unsei_detail,
    render_juuni_unsei_summary_table,
    render_juuni_unsei_thinking_pillar_table,
    render_juuni_unsei_thinking_score_table,
    render_nikkan_public_comment,
    render_private_month_pair_comment,
    render_private_tsuhensei_comments,
    write_tsuhensei_comment,
)
from special_chart_logic import (
    SPECIAL_CHART_EMPTY_MESSAGE,
    build_ijou_kanshi_data_from_meishiki,
    build_special_meishiki_rows,
    format_ijou_kanshi_type,
)
from specific_datetime_logic import build_specific_datetime_fortunes
from utils import format_score_percent
from yearly_flow_logic import build_yearly_monthly_flow, is_kubou_branch
from yearly_overall_logic import build_yearly_overall_fortune


KUUBOU_HELP_TEXT = "自分を見失いやすいが、素直・反省・感謝を忘れずに慎重に行動すると吉。可能性は無限大に。"
APP_LOGO_PATH = Path(__file__).resolve().parent / "assets" / "logo_white.png"
UNKNOWN_BIRTH_TIME_CALCULATION_TIME = datetime_time(12, 0)


def get_image_data_uri(image_path):
    try:
        image_bytes = image_path.read_bytes()
    except OSError:
        return ""

    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded_image}"


def inject_app_styles():
    st.markdown(
        """
        <style>
        :root {
            --fortune-ink: #f4efe6;
            --fortune-muted: #c1bbb1;
            --fortune-line: rgba(234, 229, 218, 0.17);
            --fortune-panel: rgba(30, 33, 32, 0.92);
            --fortune-panel-strong: #222625;
            --fortune-accent: #aeb8ae;
            --fortune-accent-soft: rgba(174, 184, 174, 0.14);
            --fortune-button: #ece9e1;
            --fortune-button-hover: #f5f2ea;
            --fortune-button-text: #171a18;
            --fortune-green: #2f423b;
            --fortune-bg: #191c1b;
        }

        .stApp {
            background:
                linear-gradient(180deg, #161918 0%, #1b1e1d 52%, #20231f 100%);
            color: var(--fortune-ink);
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        [data-testid="stAppViewContainer"] > .main .block-container {
            max-width: 720px;
            padding: 1rem 0.95rem 3rem;
        }

        @media (min-width: 768px) {
            [data-testid="stAppViewContainer"] > .main .block-container {
                padding-top: 1.45rem;
            }
        }

        .fortune-brand-hero {
            min-height: 8rem;
            padding: 1.1rem 0.1rem 1.2rem;
            margin: 0 0 1.1rem;
            border-bottom: 1px solid var(--fortune-line);
        }

        .fortune-brand-title-row {
            display: flex;
            align-items: flex-start;
            justify-content: flex-start;
            gap: 1rem;
        }

        .fortune-brand-logo {
            width: clamp(78px, 22vw, 96px);
            height: clamp(78px, 22vw, 96px);
            margin-top: 2.32rem;
            flex: 0 0 auto;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0.86;
        }

        .fortune-brand-logo img {
            width: 100%;
            height: 100%;
            object-fit: contain;
            display: block;
        }

        .fortune-brand-title {
            margin: 0;
            color: var(--fortune-ink);
            font-family: "Hiragino Maru Gothic ProN", "Yu Gothic UI", "BIZ UDPGothic", "Meiryo", "Yu Gothic", sans-serif;
            font-size: 2.15rem;
            line-height: 1.08;
            font-weight: 650;
        }

        .fortune-brand-title span {
            display: block;
        }

        .fortune-brand-rule {
            width: 3.8rem;
            height: 1px;
            margin-top: 1.1rem;
            background: var(--fortune-accent);
            opacity: 0.8;
        }

        h1, h2, h3 {
            color: var(--fortune-ink);
            letter-spacing: 0;
        }

        h2 {
            padding-top: 0.65rem;
            font-size: 1.17rem;
            border-bottom: 1px solid var(--fortune-line);
            padding-bottom: 0.5rem;
        }

        h3 {
            font-size: 1.08rem;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stDateInput"] input,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        div[data-testid="stTextArea"] textarea {
            border-radius: 8px;
            border-color: rgba(228, 214, 188, 0.18);
            background: var(--fortune-panel-strong);
            color: var(--fortune-ink);
            box-shadow: none;
        }

        div[data-testid="stTextInput"] label,
        div[data-testid="stDateInput"] label,
        div[data-testid="stSelectbox"] label,
        div[data-testid="stTextArea"] label,
        div[data-testid="stCheckbox"] label {
            color: var(--fortune-muted);
        }

        div[data-baseweb="select"] span {
            color: var(--fortune-ink);
        }

        div[data-testid="stTextArea"] textarea {
            min-height: 104px;
        }

        div[data-testid="stButton"] button {
            width: 100%;
            border-radius: 8px;
            border: 1px solid rgba(244, 239, 230, 0.36);
            background: var(--fortune-button);
            color: var(--fortune-button-text);
            font-weight: 700;
            min-height: 2.7rem;
            box-shadow: none;
        }

        div[data-testid="stButton"] button:hover {
            border-color: rgba(244, 239, 230, 0.7);
            background: var(--fortune-button-hover);
            color: #101312;
        }

        div[data-testid="stExpander"] {
            border: 1px solid var(--fortune-line);
            border-radius: 8px;
            background: var(--fortune-panel);
            overflow: hidden;
            box-shadow: none;
        }

        div[data-testid="stExpander"] details summary,
        div[data-testid="stExpander"] p {
            color: var(--fortune-ink);
        }

        div[data-testid="stTable"],
        div[data-testid="stDataFrame"] {
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid var(--fortune-line);
            box-shadow: none;
        }

        div[data-testid="stTable"] table {
            background: var(--fortune-panel);
            color: var(--fortune-ink);
        }

        div[data-testid="stTable"] th,
        div[data-testid="stTable"] td {
            background: transparent;
            color: var(--fortune-ink);
            border-color: var(--fortune-line);
        }

        .stMarkdown p,
        div[data-testid="stCaptionContainer"] {
            color: var(--fortune-muted);
        }

        .stMarkdown strong {
            color: var(--fortune-ink);
        }

        .inline-help-heading h3 {
            font-size: 1.12rem;
        }

        @media (max-width: 520px) {
            [data-testid="stAppViewContainer"] > .main .block-container {
                padding-left: 0.72rem;
                padding-right: 0.72rem;
            }

            .fortune-brand-hero {
                min-height: 7.65rem;
                padding: 0.95rem 0 1rem;
                margin-bottom: 0.95rem;
            }

            .fortune-brand-title-row {
                gap: 0.72rem;
            }

            .fortune-brand-logo {
                width: 78px;
                height: 78px;
                margin-top: 2.03rem;
            }

            .fortune-brand-title {
                font-size: 1.88rem;
            }

            h2 {
                font-size: 1.16rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_app_header():
    logo_uri = get_image_data_uri(APP_LOGO_PATH)
    logo_html = (
        f'<img src="{logo_uri}" alt="占いロゴ">'
        if logo_uri
        else '<span style="color:#f4efe6;font-weight:700;">四</span>'
    )

    st.markdown(
        f"""
        <div class="fortune-brand-hero">
            <div>
                <div class="fortune-brand-title-row">
                    <h1 class="fortune-brand-title"><span>四柱推命</span><span>鑑定アプリ</span></h1>
                    <div class="fortune-brand-logo">{logo_html}</div>
                </div>
                <div class="fortune-brand-rule"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_inline_help_heading(title, help_text):
    title_html = html.escape(str(title))
    help_html = html.escape(str(help_text))

    st.markdown(
        f"""
        <style>
        .inline-help-heading {{
            position: relative;
            display: flex;
            align-items: center;
            gap: 0.4rem;
            flex-wrap: nowrap;
            margin: 1.25rem 0 0.35rem;
        }}
        .inline-help-heading h3 {{
            margin: 0;
            padding: 0;
            font-size: 1.5rem;
            line-height: 1.3;
            font-weight: 600;
        }}
        .inline-help-heading details {{
            display: inline-block;
        }}
        .inline-help-heading summary {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.1rem;
            height: 1.1rem;
            border: 1px solid rgba(107, 114, 128, 0.55);
            border-radius: 999px;
            background: rgba(243, 244, 246, 0.85);
            color: rgba(75, 85, 99, 0.86);
            cursor: pointer;
            font-size: 0.72rem;
            font-weight: 600;
            line-height: 1;
            list-style: none;
            user-select: none;
        }}
        .inline-help-heading summary::-webkit-details-marker {{
            display: none;
        }}
        .inline-help-heading details[open] summary {{
            background: rgba(229, 231, 235, 0.95);
            color: rgba(55, 65, 81, 0.95);
        }}
        .inline-help-body {{
            position: absolute;
            z-index: 20;
            left: 0;
            top: calc(100% + 0.3rem);
            width: min(28rem, calc(100vw - 2rem));
            padding: 0.55rem 0.65rem;
            border: 1px solid rgba(209, 213, 219, 0.9);
            border-radius: 0.45rem;
            background: rgba(249, 250, 251, 0.98);
            color: rgba(55, 65, 81, 0.95);
            box-shadow: 0 8px 18px rgba(17, 24, 39, 0.08);
            font-size: 0.9rem;
            line-height: 1.65;
        }}
        </style>
        <div class="inline-help-heading">
            <h3>{title_html}</h3>
            <details>
                <summary aria-label="{title_html}の説明">?</summary>
                <div class="inline-help-body">{help_html}</div>
            </details>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_japanese_date(value):
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return f"{value.year}年{value.month}月{value.day}日"
    return str(value or "")


def format_birth_time_for_client(value):
    if value is None:
        return "出生時刻不明"
    return f"{value.hour}時{value.minute:02d}分生まれ"


def get_birth_time_for_calculation(birth_time_unknown, birth_time_value):
    if birth_time_unknown:
        return UNKNOWN_BIRTH_TIME_CALCULATION_TIME
    return birth_time_value


def clear_hour_pillar_for_unknown_birth_time(meishiki):
    if not isinstance(meishiki, dict):
        return meishiki

    cleared_meishiki = {
        pillar_key: dict(pillar) if isinstance(pillar, dict) else pillar
        for pillar_key, pillar in meishiki.items()
    }
    cleared_meishiki["hour"] = {
        "tenkan": "",
        "chishi": "",
        "zokkan": "",
    }
    return cleared_meishiki


def calculate_full_age(birth_date_value, reference_date_value):
    if not isinstance(birth_date_value, date) or not isinstance(reference_date_value, date):
        return None

    age = reference_date_value.year - birth_date_value.year
    if (reference_date_value.month, reference_date_value.day) < (
        birth_date_value.month,
        birth_date_value.day,
    ):
        age -= 1

    if age < 0:
        return None
    return age


def build_client_basic_info_rows(
    name_text,
    furigana_text,
    birth_date_value,
    birth_time_value,
    birth_place_text,
    gender_text,
    consultation_text,
    reading_date_value,
):
    rows = []
    if name_text.strip():
        rows.append({"項目": "氏名", "内容": name_text})
    if furigana_text.strip():
        rows.append({"項目": "ふりがな", "内容": furigana_text})

    rows.append({"項目": "生年月日", "内容": format_japanese_date(birth_date_value)})
    rows.append({"項目": "出生時刻", "内容": format_birth_time_for_client(birth_time_value)})

    age = calculate_full_age(birth_date_value, reading_date_value)
    if age is not None:
        rows.append({"項目": "年齢", "内容": f"{age}歳"})

    if birth_place_text and birth_place_text != "未選択":
        rows.append({"項目": "出生地", "内容": birth_place_text})
    if gender_text and gender_text != "未選択":
        rows.append({"項目": "性別", "内容": gender_text})
    if consultation_text.strip():
        rows.append({"項目": "相談内容", "内容": consultation_text})
    rows.append({"項目": "鑑定日", "内容": format_japanese_date(reading_date_value)})

    return rows


def render_public_gogyo_balance(gogyo_result, day_tenkan):
    if not isinstance(gogyo_result, dict):
        gogyo_result = {}

    scores = gogyo_result.get("scores", init_gogyo_scores())
    ordered_scores = {element: scores.get(element, 0) for element in GOGYO_ORDER}
    kantei_year = gogyo_result.get("kantei_year", {})
    kantei_year_tenkan = kantei_year.get("tenkan", "")
    kantei_year_chishi = kantei_year.get("chishi", "")

    if kantei_year_tenkan and kantei_year_chishi:
        st.caption(f"鑑定年の干支（作用判定用）：{kantei_year_tenkan}{kantei_year_chishi}")

    show_gogyo_relationship_chart(ordered_scores, day_tenkan)


def format_month_pair_effect_title(zokkan_tsuhensei, tsuhensei):
    return f"{tsuhensei}から{zokkan_tsuhensei}へ与える効果"


def render_public_month_pair_effect_for_audience(zokkan_tsuhensei, tsuhensei):
    if (
        not zokkan_tsuhensei
        or not tsuhensei
        or zokkan_tsuhensei == "－"
        or tsuhensei == "－"
    ):
        return

    comment_text = get_month_pair_comment(zokkan_tsuhensei, tsuhensei, "public")
    if not comment_text:
        return

    st.markdown(f"**{format_month_pair_effect_title(zokkan_tsuhensei, tsuhensei)}**")
    st.write(f"蔵干通変星：{zokkan_tsuhensei}")
    st.write(f"通変星：{tsuhensei}")
    st.write(comment_text)


def render_public_tsuhensei_comments_for_audience(
    life_stage_tsuhensei_data,
    month_zokkan_tsuhensei,
    month_tsuhensei,
):
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

            if stage == "30〜64歳":
                render_public_month_pair_effect_for_audience(
                    month_zokkan_tsuhensei,
                    month_tsuhensei,
                )



def format_day_ijou_kanshi_result(ijou_kanshi_data):
    for data in ijou_kanshi_data or []:
        if data.get("pillar_label") != "日柱":
            continue

        ijou_type = data.get("ijou_type", "")
        tenkan = data.get("tenkan", "")
        chishi = data.get("chishi", "")
        if not ijou_type or not tenkan or not chishi:
            return ""

        return f"{tenkan}{chishi}：{format_ijou_kanshi_type(ijou_type)}"

    return ""


def build_special_meishiki_display_rows(rows, ijou_kanshi_data):
    display_rows = []
    day_ijou_text = format_day_ijou_kanshi_result(ijou_kanshi_data)

    for row in rows:
        if row.get("判定") == "異常干支":
            if day_ijou_text:
                display_rows.append({"判定": row.get("判定", ""), "結果": day_ijou_text})
            continue

        display_rows.append(row)

    return display_rows


def render_special_meishiki(ijou_kanshi_data, gogyo_result):
    rows = build_special_meishiki_rows(ijou_kanshi_data, gogyo_result)
    rows = build_special_meishiki_display_rows(rows, ijou_kanshi_data)

    if not rows:
        st.write(SPECIAL_CHART_EMPTY_MESSAGE)
        return

    st.table(pd.DataFrame(rows))


def inject_mobile_input_styles():
    st.markdown(
        """
        <style>
        div[data-testid="stDateInput"] input {
            caret-color: transparent;
        }
        div[data-testid="stSelectbox"] input {
            caret-color: transparent;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_date_input_keyboard_guard():
    components.html(
        """
        <script>
        (function () {
            const targetLabels = ["生年月日", "鑑定日"];

            function guardDateInputs() {
                try {
                    const doc = window.parent.document;
            targetLabels.forEach((label) => {
                const inputs = doc.querySelectorAll(
                    `input[aria-label="${label}"]`
                );
                inputs.forEach((input) => {
                            input.setAttribute("readonly", "readonly");
                            input.setAttribute("inputmode", "none");
                    input.style.caretColor = "transparent";
                });
            });

            const selectInputs = doc.querySelectorAll(
                'div[data-testid="stSelectbox"] input'
            );
            selectInputs.forEach((input) => {
                input.setAttribute("inputmode", "none");
                input.setAttribute("autocomplete", "off");
                input.style.caretColor = "transparent";
            });
        } catch (error) {
            return;
        }
            }

            guardDateInputs();
            setTimeout(guardDateInputs, 300);
            setTimeout(guardDateInputs, 1000);

            try {
                const observer = new MutationObserver(guardDateInputs);
                observer.observe(window.parent.document.body, {
                    childList: true,
                    subtree: true,
                });
            } catch (error) {
                return;
            }
        })();
        </script>
        """,
        height=0,
    )


def get_juuni_unsei_by_pillar(juuni_unsei_display_data):
    return {
        data.get("pillar_key", ""): data.get("juuni_unsei", "")
        for data in juuni_unsei_display_data
    }


def render_juuni_unsei_comments_for_mobile(juuni_unsei_display_data, comment_type):
    if comment_type != "public":
        with st.expander("十二運星から読み取れる性格メモの詳細表", expanded=False):
            render_juuni_unsei_summary_table(juuni_unsei_display_data)

    for data in juuni_unsei_display_data:
        render_juuni_unsei_detail(data, comment_type)

    render_juuni_unsei_thinking_tendency_for_mobile(
        get_juuni_unsei_by_pillar(juuni_unsei_display_data),
        is_private=(comment_type != "public"),
    )


THINKING_BAR_COLORS = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759"]


def to_numeric_thinking_scores(score_dict):
    numeric_scores = {}

    for label, score in score_dict.items():
        try:
            numeric_scores[label] = float(score)
        except (TypeError, ValueError):
            numeric_scores[label] = 0

    return numeric_scores


def render_thinking_score_legend(numeric_scores):
    legend_rows = []

    for index, (label, value) in enumerate(numeric_scores.items()):
        color = THINKING_BAR_COLORS[index % len(THINKING_BAR_COLORS)]
        legend_rows.append(
            "<span style=\"display:inline-flex;align-items:center;gap:6px;color:#24292f;\">"
            f"<span style=\"width:10px;height:10px;background:{color};display:inline-block;border-radius:2px;\"></span>"
            f"{html.escape(label)} {html.escape(format_score_percent(value))}"
            "</span>"
        )

    st.markdown(
        "<div style=\"display:flex;flex-wrap:wrap;gap:8px 14px;margin:6px 0 2px;font-size:12px;\">"
        + "".join(legend_rows)
        + "</div>",
        unsafe_allow_html=True,
    )


def render_thinking_stacked_bar(title, score_dict):
    st.markdown(f"#### {title}")

    if not score_dict:
        st.write("集計できるデータがありません。")
        return

    numeric_scores = to_numeric_thinking_scores(score_dict)
    positive_total = sum(value for value in numeric_scores.values() if value > 0)

    if positive_total <= 0:
        st.write("集計できるデータがありません。")
        render_thinking_score_legend(numeric_scores)
        return

    scale = 100 if positive_total <= 100 else positive_total
    segments = []

    for index, (label, value) in enumerate(numeric_scores.items()):
        if value <= 0:
            continue

        width = value / scale * 100
        color = THINKING_BAR_COLORS[index % len(THINKING_BAR_COLORS)]
        label_text = f"{label} {format_score_percent(value)}"
        segment_text = format_score_percent(value)

        segments.append(
            "<div "
            f"title=\"{html.escape(label_text)}\" "
            "style=\""
            f"width:{width:.2f}%;"
            f"background:{color};"
            "display:flex;"
            "align-items:center;"
            "justify-content:center;"
            "color:white;"
            "font-size:12px;"
            "font-weight:700;"
            "line-height:1.2;"
            "min-height:30px;"
            "padding:0 4px;"
            "box-sizing:border-box;"
            "white-space:nowrap;"
            "overflow:hidden;"
            "text-overflow:ellipsis;"
            "\">"
            f"{html.escape(segment_text)}"
            "</div>"
        )

    st.markdown(
        "<div style=\""
        "width:100%;"
        "height:30px;"
        "display:flex;"
        "overflow:hidden;"
        "border:1px solid #d0d7de;"
        "background:#f6f8fa;"
        "border-radius:4px;"
        "\">"
        + "".join(segments)
        + "</div>",
        unsafe_allow_html=True,
    )

    render_thinking_score_legend(numeric_scores)


def calculate_svg_pie_point(center_x, center_y, radius, angle):
    angle_radians = math.radians(angle)
    return (
        center_x + radius * math.cos(angle_radians),
        center_y + radius * math.sin(angle_radians),
    )


def build_svg_pie_slice_path(center_x, center_y, radius, start_angle, end_angle):
    start_x, start_y = calculate_svg_pie_point(
        center_x,
        center_y,
        radius,
        start_angle,
    )
    end_x, end_y = calculate_svg_pie_point(
        center_x,
        center_y,
        radius,
        end_angle,
    )
    large_arc = 1 if end_angle - start_angle > 180 else 0

    return (
        f"M {center_x:.2f} {center_y:.2f} "
        f"L {start_x:.2f} {start_y:.2f} "
        f"A {radius:.2f} {radius:.2f} 0 {large_arc} 1 {end_x:.2f} {end_y:.2f} "
        "Z"
    )


def build_work_type_pie_svg(numeric_scores):
    filtered_scores = {
        label: value
        for label, value in numeric_scores.items()
        if value > 0
    }
    total = sum(filtered_scores.values())
    center_x = 150
    center_y = 126
    radius = 96
    start_angle = -90
    slices = []
    percent_labels = []

    for index, (label, value) in enumerate(filtered_scores.items()):
        percent = value / total * 100
        end_angle = start_angle + (percent / 100 * 360)
        middle_angle = (start_angle + end_angle) / 2
        color = THINKING_BAR_COLORS[index % len(THINKING_BAR_COLORS)]
        label_text = f"{label} {format_score_percent(percent)}"
        percent_text = format_score_percent(percent)

        slices.append(
            "<path "
            f"d=\"{build_svg_pie_slice_path(center_x, center_y, radius, start_angle, end_angle)}\" "
            f"fill=\"{color}\" "
            "stroke=\"#ffffff\" "
            "stroke-width=\"2\" "
            f"><title>{html.escape(label_text)}</title></path>"
        )

        label_x, label_y = calculate_svg_pie_point(
            center_x,
            center_y,
            radius * 0.60,
            middle_angle,
        )
        percent_labels.append(
            {
                "text": percent_text,
                "x": label_x,
                "y": label_y,
            }
        )

        start_angle = end_angle

    percent_label_svg = "".join(
        "<text "
        f"x=\"{label['x']:.2f}\" "
        f"y=\"{label['y']:.2f}\" "
        "text-anchor=\"middle\" "
        "dominant-baseline=\"middle\" "
        "fill=\"#ffffff\" "
        "font-size=\"12\" "
        "font-weight=\"700\" "
        "paint-order=\"stroke\" "
        "stroke=\"rgba(0,0,0,0.25)\" "
        "stroke-width=\"2\" "
        "stroke-linejoin=\"round\""
        ">"
        f"{html.escape(label['text'])}"
        "</text>"
        for label in percent_labels
    )

    return (
        "<svg "
        "viewBox=\"0 0 300 252\" "
        "width=\"100%\" "
        "role=\"img\" "
        "aria-label=\"仕事4分類の円グラフ\" "
        "style=\"max-width:420px;display:block;margin:0 auto;\""
        ">"
        "<rect x=\"0\" y=\"0\" width=\"300\" height=\"252\" fill=\"transparent\" />"
        + "".join(slices)
        + percent_label_svg
        + "</svg>"
    )


def render_work_type_pie_legend(filtered_scores):
    total = sum(filtered_scores.values())
    legend_rows = []

    for index, (label, value) in enumerate(filtered_scores.items()):
        color = THINKING_BAR_COLORS[index % len(THINKING_BAR_COLORS)]
        percent = format_score_percent(value / total * 100)
        legend_rows.append(
            "<span style=\"display:inline-flex;align-items:center;gap:6px;color:#24292f;\">"
            f"<span style=\"width:10px;height:10px;background:{color};display:inline-block;border-radius:2px;\"></span>"
            f"{index + 1}. {html.escape(label)} {html.escape(percent)}"
            "</span>"
        )

    st.markdown(
        "<div style=\"display:flex;flex-wrap:wrap;gap:8px 14px;margin:4px 0 8px;font-size:12px;\">"
        + "".join(legend_rows)
        + "</div>",
        unsafe_allow_html=True,
    )


def render_work_type_pie_chart_for_mobile(title, score_dict):
    st.markdown(f"#### {title}")

    if not score_dict:
        st.write("集計できるデータがありません。")
        return

    numeric_scores = to_numeric_thinking_scores(score_dict)
    filtered_scores = {
        label: value
        for label, value in numeric_scores.items()
        if value > 0
    }

    if not filtered_scores:
        st.write("集計できるデータがありません。")
        return

    total = sum(filtered_scores.values())
    st.markdown(
        build_work_type_pie_svg(numeric_scores),
        unsafe_allow_html=True,
    )
    render_work_type_pie_legend(filtered_scores)
    label_table = pd.DataFrame(
        {
            "番号": [str(index + 1) for index in range(len(filtered_scores))],
            "分類": list(filtered_scores.keys()),
            "割合": [
                format_score_percent(value / total * 100)
                for value in filtered_scores.values()
            ],
        }
    )
    st.table(label_table)


def render_juuni_unsei_thinking_charts_for_mobile(aggregated_scores):
    with st.expander("考え方の傾向（グラフ）"):
        brain_type_scores = fill_missing_scores(
            aggregated_scores.get("brain_type", {}),
            BRAIN_TYPE_ORDER,
        )
        merit_type_scores = fill_missing_scores(
            aggregated_scores.get("merit_type", {}),
            MERIT_TYPE_ORDER,
        )
        goal_type_scores = fill_missing_scores(
            aggregated_scores.get("goal_type", {}),
            GOAL_TYPE_ORDER,
        )
        principle_type_scores = fill_missing_scores(
            aggregated_scores.get("principle_type", {}),
            PRINCIPLE_TYPE_ORDER,
        )
        work_type_scores = fill_missing_scores(
            aggregated_scores.get("work_type", {}),
            WORK_TYPE_ORDER,
        )

        render_thinking_stacked_bar("左脳／右脳", brain_type_scores)
        render_thinking_stacked_bar("メリット型／デメリット型", merit_type_scores)
        render_thinking_stacked_bar("目標への向かい方", goal_type_scores)
        render_thinking_stacked_bar("原理原則型／応用拡大型", principle_type_scores)
        render_work_type_pie_chart_for_mobile("仕事4分類", work_type_scores)


def render_juuni_unsei_thinking_tendency_for_mobile(
    pillar_juuni_unsei_data,
    is_private=False,
):
    if is_private:
        st.markdown("#### 考え方の傾向メモ")

    aggregated_scores = aggregate_juuni_unsei_thinking_tendency(
        pillar_juuni_unsei_data
    )

    if is_private:
        with st.expander("四柱ごとの分類表", expanded=False):
            render_juuni_unsei_thinking_pillar_table(pillar_juuni_unsei_data)

        with st.expander("集計結果", expanded=False):
            render_juuni_unsei_thinking_score_table(aggregated_scores)

    render_juuni_unsei_thinking_charts_for_mobile(aggregated_scores)


def format_kubou_marked_text(text, should_mark):
    escaped_text = html.escape(str(text or ""))
    if not should_mark:
        return escaped_text

    return (
        '<span style="color: #d32f2f; font-weight: 700;">'
        f"{escaped_text}"
        "</span>"
    )


def render_kubou_note():
    st.caption("※赤文字は空亡であることを示します。")


def render_daiun_table(daiun_result, kubou=""):
    rows = daiun_result.get("rows", []) if isinstance(daiun_result, dict) else []
    if rows:
        direction_label = daiun_result.get("direction_label", "")
        kigun_age = daiun_result.get("kigun_age")
        if direction_label and kigun_age:
            st.caption(f"{direction_label} / 起運 {format_age(kigun_age)}")
        render_kubou_note()
        for index, row in enumerate(rows):
            daiun_label = row.get("大運", "")
            start_age = row.get("開始年齢", "")
            end_age = row.get("終了年齢", "")
            kanchi = f"{row.get('天干', '')}{row.get('地支', '')}"
            kanchi_html = format_kubou_marked_text(
                kanchi,
                is_kubou_branch(row.get("地支", ""), kubou),
            )
            tsuhensei = row.get("通変星", "")
            summary = get_daiun_tsuhensei_summary(tsuhensei)
            period = row.get("周期") or summary.get("period") or "—"
            keywords = row.get("キーワード") or summary.get("keywords") or "—"

            with st.container():
                st.markdown(f"**{daiun_label}　{start_age}〜{end_age}**")
                st.markdown(
                    f"{kanchi_html}｜{html.escape(str(tsuhensei or ''))}",
                    unsafe_allow_html=True,
                )
                st.markdown(f"周期：{html.escape(str(period))}")
                st.markdown(f"キーワード：{html.escape(str(keywords))}")
            if index < len(rows) - 1:
                render_daiun_transition_separator(row)
        return

    message = (
        daiun_result.get("message")
        if isinstance(daiun_result, dict)
        else ""
    )
    if message:
        st.caption(message)


def format_daiun_expander_label(row):
    daiun_label = str(row.get("大運", "") or "")
    kanchi = f"{row.get('天干', '')}{row.get('地支', '')}"
    age_range = f"{row.get('開始年齢', '')}〜{row.get('終了年齢', '')}"

    label_parts = []
    if daiun_label:
        label_parts.append(daiun_label)
    if kanchi:
        label_parts.append(kanchi)
    if age_range != "〜":
        label_parts.append(age_range)

    if not label_parts:
        return "大運"
    if len(label_parts) == 1:
        return label_parts[0]

    return f"{label_parts[0]}：{' '.join(label_parts[1:])}"


def render_daiun_row_content(row, kubou):
    daiun_label = row.get("大運", "")
    start_age = row.get("開始年齢", "")
    end_age = row.get("終了年齢", "")
    kanchi = f"{row.get('天干', '')}{row.get('地支', '')}"
    kanchi_html = format_kubou_marked_text(
        kanchi,
        is_kubou_branch(row.get("地支", ""), kubou),
    )
    tsuhensei = row.get("通変星", "")
    summary = get_daiun_tsuhensei_summary(tsuhensei)
    period = row.get("周期") or summary.get("period") or "—"
    keywords = row.get("キーワード") or summary.get("keywords") or "—"

    st.markdown(f"**{daiun_label}　{start_age}〜{end_age}**")
    st.markdown(
        f"{kanchi_html}｜{html.escape(str(tsuhensei or ''))}",
        unsafe_allow_html=True,
    )
    st.markdown(f"周期：{html.escape(str(period))}")
    st.markdown(f"キーワード：{html.escape(str(keywords))}")


def render_client_daiun_table(daiun_result, kubou=""):
    rows = daiun_result.get("rows", []) if isinstance(daiun_result, dict) else []
    if rows:
        direction_label = daiun_result.get("direction_label", "")
        kigun_age = daiun_result.get("kigun_age")
        if direction_label and kigun_age:
            st.caption(f"{direction_label} / 起運 {format_age(kigun_age)}")
        render_kubou_note()
        for index, row in enumerate(rows):
            with st.expander(format_daiun_expander_label(row), expanded=False):
                render_daiun_row_content(row, kubou)
            if index < len(rows) - 1:
                render_daiun_transition_separator(row)
        return

    message = (
        daiun_result.get("message")
        if isinstance(daiun_result, dict)
        else ""
    )
    if message:
        st.caption(message)


def render_yearly_monthly_flow(yearly_flow_result):
    rows = (
        yearly_flow_result.get("rows", [])
        if isinstance(yearly_flow_result, dict)
        else []
    )
    if not rows:
        return

    render_kubou_note()
    for index, row in enumerate(rows):
        month_label = row.get("月", "")
        month_kanchi = row.get("月干支", "")
        tsuhensei = row.get("通変星", "")
        keyword = row.get("キーワード", "")
        comment = row.get("コメント", "")
        error = row.get("error", "")

        with st.container():
            st.markdown(f"**{html.escape(str(month_label or ''))}**")
            if error:
                st.caption(error)
            else:
                kanchi_html = format_kubou_marked_text(
                    month_kanchi,
                    row.get("空亡", False),
                )
                st.markdown(
                    f"{kanchi_html}｜{html.escape(str(tsuhensei or ''))}",
                    unsafe_allow_html=True,
                )
                if keyword:
                    st.markdown(f"キーワード：{html.escape(str(keyword))}")
                if comment:
                    st.markdown(f"コメント：{html.escape(str(comment))}")
        if index < len(rows) - 1:
            st.markdown(
                '<div style="border-top: 1px dashed rgba(49, 51, 63, 0.25); margin: 1rem 0;"></div>',
                unsafe_allow_html=True,
            )


def format_yearly_month_expander_label(row):
    month_label = str(row.get("月", "") or "")
    month_kanchi = str(row.get("月干支", "") or "")
    tsuhensei = str(row.get("通変星", "") or "")

    if month_kanchi and tsuhensei:
        detail = f"{month_kanchi}｜{tsuhensei}"
    else:
        detail = month_kanchi or tsuhensei

    if month_label and detail:
        return f"{month_label}：{detail}"
    return month_label or detail or "月別運勢"


def render_yearly_month_row_content(row):
    month_label = row.get("月", "")
    month_kanchi = row.get("月干支", "")
    tsuhensei = row.get("通変星", "")
    keyword = row.get("キーワード", "")
    comment = row.get("コメント", "")
    error = row.get("error", "")

    st.markdown(f"**{html.escape(str(month_label or ''))}**")
    if error:
        st.caption(error)
        return

    kanchi_html = format_kubou_marked_text(
        month_kanchi,
        row.get("空亡", False),
    )
    st.markdown(
        f"{kanchi_html}｜{html.escape(str(tsuhensei or ''))}",
        unsafe_allow_html=True,
    )
    if keyword:
        st.markdown(f"キーワード：{html.escape(str(keyword))}")
    if comment:
        st.markdown(f"コメント：{html.escape(str(comment))}")


def render_client_yearly_monthly_flow(yearly_flow_result):
    rows = (
        yearly_flow_result.get("rows", [])
        if isinstance(yearly_flow_result, dict)
        else []
    )
    if not rows:
        return

    render_kubou_note()
    for row in rows:
        with st.expander(format_yearly_month_expander_label(row), expanded=False):
            render_yearly_month_row_content(row)


def render_yearly_overall_fortune(yearly_overall_result):
    if not isinstance(yearly_overall_result, dict):
        return

    if yearly_overall_result.get("error"):
        st.caption(yearly_overall_result["error"])
        return

    year = yearly_overall_result.get("year", "")
    year_kanchi = yearly_overall_result.get("year_kanchi", "")
    tsuhensei = yearly_overall_result.get("tsuhensei", "")
    theme = yearly_overall_result.get("theme", "")
    comment = yearly_overall_result.get("comment", "")

    with st.container():
        st.markdown(f"**{year}年　{year_kanchi}｜{tsuhensei}**")
        st.markdown(f"テーマ：{theme}")
        if comment:
            st.markdown(comment.replace("\n", "  \n"))


def format_specific_candidate_heading(row):
    label = html.escape(str(row.get("label") or ""))
    target_datetime = row.get("datetime")
    if not isinstance(target_datetime, datetime):
        return label

    return (
        f"{label}："
        f"{target_datetime.month}月{target_datetime.day}日　"
        f"{target_datetime.hour}時{target_datetime.minute:02d}分"
    )


def format_specific_part_heading(part, part_index):
    if part_index == 0:
        display_name = "日の運勢"
    elif part_index == 1:
        display_name = "時間の運勢"
    else:
        display_name = part.get("display_name", "")

    kanchi = part.get("kanchi", "")
    tsuhensei = part.get("tsuhensei", "")
    return (
        f"**{html.escape(str(display_name or ''))}　"
        f"{html.escape(str(kanchi or ''))}｜"
        f"{html.escape(str(tsuhensei or ''))}**"
    )


def render_specific_datetime_fortunes(specific_datetime_result, is_enabled):
    if not is_enabled:
        return

    rows = (
        specific_datetime_result.get("rows", [])
        if isinstance(specific_datetime_result, dict)
        else []
    )
    if not rows:
        return

    st.caption(
        "※入力日時の日・時刻をもとにした簡易的な鑑定補助です。"
        "具体的な判断は相談内容と合わせて確認してください。"
    )
    for index, row in enumerate(rows):
        error = row.get("error", "")
        parts = row.get("parts", [])

        with st.container():
            candidate_heading = format_specific_candidate_heading(row)
            if candidate_heading:
                st.markdown(f"**{candidate_heading}**")
            if error:
                st.caption(error)
            else:
                for part_index, part in enumerate(parts):
                    keyword = part.get("keyword", "")
                    comment = part.get("comment", "")

                    st.markdown(format_specific_part_heading(part, part_index))
                    if keyword:
                        st.markdown(f"キーワード：{html.escape(str(keyword))}")
                    if comment:
                        st.write(comment)
                    if part_index < len(parts) - 1:
                        st.markdown("")

        if index < len(rows) - 1:
            st.markdown(
                '<div style="border-top: 1px dashed rgba(49, 51, 63, 0.25); margin: 1rem 0;"></div>',
                unsafe_allow_html=True,
            )


def render_daiun_transition_separator(row):
    if row.get("次の大運との間が接木運"):
        age_text = row.get("接木運_表示年齢", "")
        current_branch = row.get("地支", "")
        next_branch = row.get("接木運_次地支", "")
        st.warning(f"接木運　{age_text}　{current_branch} → {next_branch}")
        return

    st.markdown(
        '<div style="border-top: 1px dashed rgba(49, 51, 63, 0.35); margin: 1rem 0;"></div>',
        unsafe_allow_html=True,
    )


def format_datetime_for_display(value):
    if not value:
        return "未設定"
    return value.strftime("%Y-%m-%d %H:%M")


def format_time_adjustment_minutes_for_display(minutes):
    try:
        rounded_minutes = int(round(float(minutes or 0)))
    except (TypeError, ValueError):
        rounded_minutes = 0

    sign = "+" if rounded_minutes >= 0 else ""
    return f"{sign}{rounded_minutes}分"


def format_adjusted_birth_datetime_for_display(value):
    if not value:
        return ""
    return value.strftime("%Y/%m/%d %H:%M頃")


def render_birthplace_time_adjustment_note(birth_info):
    if not isinstance(birth_info, dict):
        return
    if not birth_info.get("time_adjustment_enabled"):
        return

    birth_place = birth_info.get("birth_place", "")
    longitude = birth_info.get("birthplace_longitude")
    adjustment_minutes = birth_info.get("time_adjustment_minutes", 0)
    adjusted_birth_datetime = birth_info.get("adjusted_birth_datetime")

    if longitude is None or not adjusted_birth_datetime:
        return

    st.caption(f"出生地補正：{birth_place}（経度{float(longitude):.2f}度）")
    st.caption(
        f"補正値：{format_time_adjustment_minutes_for_display(adjustment_minutes)}"
    )
    st.caption(
        "補正後出生日時："
        f"{format_adjusted_birth_datetime_for_display(adjusted_birth_datetime)}"
    )


def format_age(age_int):
    return f"{int(age_int)}歳"


def format_development_calendar_caption(calendar_context):
    return (
        "使用する暦設定: "
        f"{calendar_context['label']} / "
        f"立春={format_datetime_for_display(calendar_context['risshun_datetime'])} / "
        f"節入り={calendar_context['sekki_year']}年検証用サンプル / "
        f"日柱基準={calendar_context['base_date']} "
        f"{calendar_context['base_day_kanchi']}"
    )


def render_auto_meishiki_validation_development_panel():
    with st.expander("自動命式計算 検証結果（開発用）"):
        calendar_context = get_development_calendar_context()
        st.warning(
            "これは開発確認用の表示です。\n"
            "現在の節入り日時データと日柱基準日は検証用であり、"
            "本番の命式計算としてはまだ使用しません。\n"
            "既存の手入力命式や鑑定結果には接続していません。"
        )
        st.caption(format_development_calendar_caption(calendar_context))

        if st.button("自動命式の検証を実行"):
            try:
                validation_result = run_validation_cases(
                    calendar_context["risshun_datetime"],
                    calendar_context["sekki_entries"],
                    calendar_context["base_date"],
                    calendar_context["base_day_kanchi"],
                )
                summary = summarize_validation_result(validation_result)
                summary_text = format_validation_summary_text(summary)
                st.code(summary_text)
            except Exception as exc:
                st.error("自動命式計算の検証中にエラーが発生しました。")
                st.code(str(exc))


def format_auto_pillar_for_display(auto_meishiki, pillar_key):
    pillar = auto_meishiki.get(pillar_key, {})
    kanchi = pillar.get("kanchi", "")
    tenkan = pillar.get("tenkan", "")
    chishi = pillar.get("chishi", "")

    if not kanchi:
        return "計算できませんでした"

    return f"{kanchi}（{tenkan} / {chishi}）"


def render_auto_meishiki_input_test_development_panel():
    with st.expander("自動命式計算 入力テスト（開発用）"):
        calendar_context = get_development_calendar_context()
        st.warning(
            "これは開発確認用の自動命式計算テストです。\n"
            "現在の節入り日時データと日柱基準日は検証用であり、"
            "本番の命式計算としてはまだ使用しません。\n"
            "ここで計算した結果は、既存の手入力命式や鑑定結果には反映されません。"
        )
        st.caption(format_development_calendar_caption(calendar_context))

        auto_birth_date = st.date_input(
            "生年月日",
            value=date(2020, 2, 4),
            min_value=date(1900, 1, 1),
            max_value=date(2050, 12, 31),
            key="auto_meishiki_test_birth_date",
        )
        auto_birth_time = st.time_input(
            "出生時刻",
            value=datetime_time(6, 3),
            key="auto_meishiki_test_birth_time",
        )
        auto_birth_place = st.text_input(
            "出生地",
            value="日本",
            key="auto_meishiki_test_birth_place",
        )
        auto_birth_country = st.text_input(
            "出生国",
            value="日本",
            key="auto_meishiki_test_birth_country",
        )

        if st.button(
            "自動命式を計算する（開発用）",
            key="auto_meishiki_test_calculate_button",
        ):
            try:
                input_birth_datetime = datetime.combine(
                    auto_birth_date,
                    auto_birth_time,
                ).replace(second=0, microsecond=0)
                test_birth_info = {
                    "raw_birth_datetime": input_birth_datetime,
                    "birth_place": auto_birth_place,
                    "birth_country": auto_birth_country,
                    "time_adjustment_enabled": False,
                    "time_adjustment_minutes": 0,
                    "adjusted_birth_datetime": input_birth_datetime,
                }

                auto_meishiki = calculate_auto_meishiki(
                    test_birth_info,
                    risshun_datetime=calendar_context["risshun_datetime"],
                    sekki_entries=calendar_context["sekki_entries"],
                    base_date=calendar_context["base_date"],
                    base_day_kanchi=calendar_context["base_day_kanchi"],
                )

                if auto_meishiki.get("error"):
                    st.error("自動命式計算でエラーが発生しました。")
                    st.code(auto_meishiki["error"])
                    return

                st.write(
                    f"計算日時: "
                    f"{format_datetime_for_display(auto_meishiki.get('calculation_datetime'))}"
                )
                st.write(
                    f"年柱: {format_auto_pillar_for_display(auto_meishiki, 'year')}"
                )
                st.write(
                    f"月柱: {format_auto_pillar_for_display(auto_meishiki, 'month')}"
                )
                st.write(
                    f"日柱: {format_auto_pillar_for_display(auto_meishiki, 'day')}"
                )
                st.write(
                    f"時柱: {format_auto_pillar_for_display(auto_meishiki, 'hour')}"
                )

                notes = auto_meishiki.get("notes") or []
                if notes:
                    st.write("注意:")
                    for note in notes:
                        st.write(f"- {note}")
            except Exception as exc:
                st.error("自動命式計算でエラーが発生しました。")
                st.code(str(exc))


def format_manual_pillar_for_display(manual_meishiki, pillar_key):
    pillar_labels = {
        "year": "年柱",
        "month": "月柱",
        "day": "日柱",
        "hour": "時柱",
    }
    pillar = manual_meishiki.get(pillar_key, {})
    label = pillar_labels.get(pillar_key, pillar_key)
    tenkan = pillar.get("tenkan", "")
    chishi = pillar.get("chishi", "")
    zokkan = pillar.get("zokkan", "")

    return f"{label}: {tenkan} / {chishi} / 蔵干={zokkan}"


SMOKE_TEST_PILLAR_ORDER = ("year", "month", "day", "hour")
SMOKE_TEST_PILLAR_LABELS = {
    "year": "年柱",
    "month": "月柱",
    "day": "日柱",
    "hour": "時柱",
}
SMOKE_TEST_GOGYO_ORDER = ("木", "火", "土", "金", "水")
SMOKE_TEST_SKIPPED_LABELS = {
    "getsurei": "月令判定",
}


def get_smoke_check_data(checks, check_name, default=None):
    if not isinstance(checks, dict):
        return default
    check = checks.get(check_name, {})
    if not isinstance(check, dict):
        return default
    return check.get("data", default)


def format_smoke_value(value, missing_text="未取得"):
    if value is None or value == "":
        return missing_text
    return value


def render_smoke_pillar_values(title, values, missing_text="未取得", day_missing_text=None):
    st.write(f"{title}:")
    if not isinstance(values, dict):
        st.write("- 表示できません")
        return

    for pillar_key in SMOKE_TEST_PILLAR_ORDER:
        label = SMOKE_TEST_PILLAR_LABELS[pillar_key]
        pillar_missing_text = (
            day_missing_text
            if pillar_key == "day" and day_missing_text is not None
            else missing_text
        )
        st.write(f"{label}: {format_smoke_value(values.get(pillar_key), pillar_missing_text)}")


def render_smoke_gogyou_scores(checks):
    gogyou_data = get_smoke_check_data(checks, "gogyou", {})
    scores = gogyou_data.get("scores", {}) if isinstance(gogyou_data, dict) else {}
    st.write("五行点数:")
    if not isinstance(scores, dict) or not scores:
        st.write("- 表示できません")
        return

    for gogyo_key in SMOKE_TEST_GOGYO_ORDER:
        st.write(f"{gogyo_key}: {format_smoke_value(scores.get(gogyo_key))}")


def render_smoke_special_rows(checks):
    special_chart_data = get_smoke_check_data(checks, "special_chart", {})
    special_rows = (
        special_chart_data.get("special_rows", [])
        if isinstance(special_chart_data, dict)
        else []
    )
    if not special_rows:
        st.write("特殊な命式: なし")
        return

    st.write("特殊な命式:")
    for row in special_rows:
        if not isinstance(row, dict):
            st.write(f"- {row}")
            continue

        judgment = row.get("判定", "未取得")
        detail = row.get("結果", "未取得")
        st.write(f"- {judgment}: {detail}")


def render_smoke_getsurei(checks):
    getsurei_data = get_smoke_check_data(checks, "getsurei", {})
    st.write("月令判定:")

    if not isinstance(getsurei_data, dict):
        st.write("判定できません")
        st.write("理由:")
        st.write("- 月令判定結果を取得できません。")
        return

    if getsurei_data.get("ok") is not True:
        st.write("判定できません")
        errors = getsurei_data.get("errors") or ["理由を取得できません。"]
        st.write("理由:")
        for error in errors:
            st.write(f"- {error}")
        return

    st.write(getsurei_data.get("label", "未取得"))
    st.write(
        "日干: "
        f"{format_smoke_value(getsurei_data.get('day_tenkan'))}"
        f"（{format_smoke_value(getsurei_data.get('day_gogyo'))}）"
    )
    st.write(
        "月支: "
        f"{format_smoke_value(getsurei_data.get('month_chishi'))}"
        f"（{format_smoke_value(getsurei_data.get('month_gogyo'))}）"
    )


def render_smoke_skipped_checks(checks):
    if not isinstance(checks, dict):
        checks = {}

    skipped_checks = {
        check_name: check
        for check_name, check in checks.items()
        if isinstance(check, dict) and check.get("skipped")
    }

    st.write("未確認・未接続の項目:")
    if not skipped_checks:
        st.write("- なし")
        return

    for check_name, check in skipped_checks.items():
        label = SMOKE_TEST_SKIPPED_LABELS.get(check_name, check_name)
        reason = check.get("reason", "スキップしました。")
        st.write(f"- {label}: {reason}")


def render_smoke_warnings(warnings):
    st.write("警告:")
    if not warnings:
        st.write("- なし")
        return

    for warning in warnings:
        st.write(f"- {warning}")


def get_manual_pillar_value(manual_meishiki, pillar_key, value_key):
    pillar = manual_meishiki.get(pillar_key, {})
    if not isinstance(pillar, dict):
        return ""
    return pillar.get(value_key, "")


def build_auto_meishiki_preview_table(manual_meishiki, checks):
    tsuhen = get_smoke_check_data(checks, "tsuhen", {})
    zokkan_tsuhen = get_smoke_check_data(checks, "zokkan_tsuhen", {})
    juuni_unsei = get_smoke_check_data(checks, "juuni_unsei", {})

    if not isinstance(tsuhen, dict):
        tsuhen = {}
    if not isinstance(zokkan_tsuhen, dict):
        zokkan_tsuhen = {}
    if not isinstance(juuni_unsei, dict):
        juuni_unsei = {}

    return {
        "項目": [
            "天干",
            "地支",
            "蔵干",
            "通変星",
            "蔵干通変星",
            "十二運星",
        ],
        "時柱": [
            format_smoke_value(get_manual_pillar_value(manual_meishiki, "hour", "tenkan")),
            format_smoke_value(get_manual_pillar_value(manual_meishiki, "hour", "chishi")),
            format_smoke_value(get_manual_pillar_value(manual_meishiki, "hour", "zokkan")),
            format_smoke_value(tsuhen.get("hour")),
            format_smoke_value(zokkan_tsuhen.get("hour")),
            format_smoke_value(juuni_unsei.get("hour")),
        ],
        "日柱": [
            format_smoke_value(get_manual_pillar_value(manual_meishiki, "day", "tenkan")),
            format_smoke_value(get_manual_pillar_value(manual_meishiki, "day", "chishi")),
            format_smoke_value(get_manual_pillar_value(manual_meishiki, "day", "zokkan")),
            "表示対象外",
            format_smoke_value(zokkan_tsuhen.get("day")),
            format_smoke_value(juuni_unsei.get("day")),
        ],
        "月柱": [
            format_smoke_value(get_manual_pillar_value(manual_meishiki, "month", "tenkan")),
            format_smoke_value(get_manual_pillar_value(manual_meishiki, "month", "chishi")),
            format_smoke_value(get_manual_pillar_value(manual_meishiki, "month", "zokkan")),
            format_smoke_value(tsuhen.get("month")),
            format_smoke_value(zokkan_tsuhen.get("month")),
            format_smoke_value(juuni_unsei.get("month")),
        ],
        "年柱": [
            format_smoke_value(get_manual_pillar_value(manual_meishiki, "year", "tenkan")),
            format_smoke_value(get_manual_pillar_value(manual_meishiki, "year", "chishi")),
            format_smoke_value(get_manual_pillar_value(manual_meishiki, "year", "zokkan")),
            format_smoke_value(tsuhen.get("year")),
            format_smoke_value(zokkan_tsuhen.get("year")),
            format_smoke_value(juuni_unsei.get("year")),
        ],
    }


MEISHIKI_COMPARISON_VALUE_KEYS = (
    ("tenkan", "天干"),
    ("chishi", "地支"),
    ("zokkan", "蔵干"),
)


def build_meishiki_comparison_rows(manual_meishiki, auto_manual_meishiki) -> tuple[list, dict]:
    """
    手入力meishikiと自動計算meishikiを比較し、表示用の行データを返す。
    """
    if not isinstance(manual_meishiki, dict):
        manual_meishiki = {}
    if not isinstance(auto_manual_meishiki, dict):
        auto_manual_meishiki = {}

    rows = []
    summary = {
        "一致": 0,
        "不一致": 0,
        "未入力または未取得": 0,
    }

    for pillar_key in SMOKE_TEST_PILLAR_ORDER:
        pillar_label = SMOKE_TEST_PILLAR_LABELS[pillar_key]
        for value_key, value_label in MEISHIKI_COMPARISON_VALUE_KEYS:
            manual_value = get_manual_pillar_value(
                manual_meishiki,
                pillar_key,
                value_key,
            )
            auto_value = get_manual_pillar_value(
                auto_manual_meishiki,
                pillar_key,
                value_key,
            )

            if not manual_value or not auto_value:
                judgement = "未入力または未取得"
            elif manual_value == auto_value:
                judgement = "一致"
            else:
                judgement = "不一致"

            summary[judgement] += 1
            rows.append(
                {
                    "柱": pillar_label,
                    "項目": value_label,
                    "手入力": manual_value or "未入力",
                    "自動計算": auto_value or "未取得",
                    "判定": judgement,
                }
            )

    return rows, summary


def render_meishiki_comparison_summary(summary):
    matched_count = summary.get("一致", 0)
    unmatched_count = summary.get("不一致", 0)
    missing_count = summary.get("未入力または未取得", 0)

    st.write("比較結果:")
    st.write(f"一致: {matched_count}件")
    st.write(f"不一致: {unmatched_count}件")
    st.write(f"未入力または未取得: {missing_count}件")

    if unmatched_count == 0 and missing_count == 0:
        st.success("すべて一致しています。")
    elif unmatched_count > 0:
        st.warning(
            "不一致があります。手入力内容、自動計算条件、節入り日時、日柱基準日を確認してください。"
        )
    else:
        st.warning("未入力または未取得の項目があります。手入力内容を確認してください。")


def render_auto_meishiki_table_preview_development_panel():
    with st.expander("自動命式 命式表プレビュー（開発用）"):
        calendar_context = get_development_calendar_context()
        st.warning(
            "これは開発確認用の自動命式表プレビューです。\n"
            "自動計算結果を既存meishiki形式に変換し、命式表の形で確認します。\n"
            "現在の節入り日時データ、日柱基準日、蔵干は検証用です。\n"
            "ここで表示した命式は、既存の手入力命式や鑑定結果には反映されません。"
        )
        st.caption(format_development_calendar_caption(calendar_context))

        preview_birth_date = st.date_input(
            "生年月日",
            value=date(2020, 2, 4),
            min_value=date(1900, 1, 1),
            max_value=date(2050, 12, 31),
            key="auto_meishiki_preview_birth_date",
        )
        preview_birth_time = st.time_input(
            "出生時刻",
            value=datetime_time(6, 3),
            key="auto_meishiki_preview_birth_time",
        )
        preview_birth_place = st.text_input(
            "出生地",
            value="日本",
            key="auto_meishiki_preview_birth_place",
        )
        preview_birth_country = st.text_input(
            "出生国",
            value="日本",
            key="auto_meishiki_preview_birth_country",
        )

        if st.button(
            "自動命式表をプレビューする（開発用）",
            key="auto_meishiki_table_preview_button",
        ):
            try:
                preview_birth_datetime = datetime.combine(
                    preview_birth_date,
                    preview_birth_time,
                ).replace(second=0, microsecond=0)
                preview_birth_info = {
                    "raw_birth_datetime": preview_birth_datetime,
                    "birth_place": preview_birth_place,
                    "birth_country": preview_birth_country,
                    "time_adjustment_enabled": False,
                    "time_adjustment_minutes": 0,
                    "adjusted_birth_datetime": preview_birth_datetime,
                }

                auto_meishiki = calculate_auto_meishiki(
                    preview_birth_info,
                    risshun_datetime=calendar_context["risshun_datetime"],
                    sekki_entries=calendar_context["sekki_entries"],
                    base_date=calendar_context["base_date"],
                    base_day_kanchi=calendar_context["base_day_kanchi"],
                )

                if auto_meishiki.get("error"):
                    st.error("自動命式計算でエラーが発生しました。")
                    st.code(auto_meishiki["error"])
                    return

                preview_meishiki = auto_meishiki_to_manual_format(auto_meishiki)
                smoke_result = run_auto_meishiki_logic_smoke_test(auto_meishiki)
                checks = smoke_result.get("checks", {})

                st.write("自動計算結果を既存meishiki形式へ変換したプレビューです。")
                st.write("既存の手入力命式表や鑑定結果には反映していません。")
                st.write(
                    f"計算日時: "
                    f"{format_datetime_for_display(auto_meishiki.get('calculation_datetime'))}"
                )

                st.write("命式表プレビュー:")
                st.table(build_auto_meishiki_preview_table(preview_meishiki, checks))

                st.write("柱ごとの確認:")
                for pillar_key in ("year", "month", "day", "hour"):
                    st.write(format_manual_pillar_for_display(preview_meishiki, pillar_key))

                st.write(f"空亡: {format_smoke_value(get_smoke_check_data(checks, 'kuubou'))}")
                render_smoke_pillar_values(
                    "通変星",
                    get_smoke_check_data(checks, "tsuhen", {}),
                    day_missing_text="表示対象外",
                )
                render_smoke_pillar_values(
                    "蔵干通変星",
                    get_smoke_check_data(checks, "zokkan_tsuhen", {}),
                )
                render_smoke_pillar_values(
                    "十二運星",
                    get_smoke_check_data(checks, "juuni_unsei", {}),
                )
                render_smoke_getsurei(checks)
            except Exception as exc:
                st.error("自動命式表プレビュー中にエラーが発生しました。")
                st.code(str(exc))


def render_auto_meishiki_reading_preview_development_panel():
    with st.expander("自動命式 鑑定結果プレビュー（開発用）"):
        calendar_context = get_development_calendar_context()
        st.warning(
            "これは開発確認用の鑑定結果プレビューです。\n"
            "自動計算された命式を既存meishiki形式に変換し、"
            "既存ロジックでどのような鑑定結果になるかを確認します。\n"
            "現在の節入り日時データ、日柱基準日、蔵干は検証用です。\n"
            "ここで表示した内容は、既存の手入力命式や通常の鑑定結果には反映されません。"
        )
        st.caption(format_development_calendar_caption(calendar_context))
        for warning in calendar_context.get("warnings", []):
            st.warning(warning)

        preview_birth_date = st.date_input(
            "生年月日",
            value=date(2020, 2, 4),
            min_value=date(1900, 1, 1),
            max_value=date(2050, 12, 31),
            key="auto_meishiki_reading_preview_birth_date",
        )
        preview_birth_time = st.time_input(
            "出生時刻",
            value=datetime_time(6, 3),
            key="auto_meishiki_reading_preview_birth_time",
        )
        preview_birth_place = st.text_input(
            "出生地",
            value="日本",
            key="auto_meishiki_reading_preview_birth_place",
        )
        preview_birth_country = st.text_input(
            "出生国",
            value="日本",
            key="auto_meishiki_reading_preview_birth_country",
        )

        if st.button(
            "自動命式の鑑定結果をプレビューする（開発用）",
            key="auto_meishiki_reading_preview_button",
        ):
            try:
                preview_birth_datetime = datetime.combine(
                    preview_birth_date,
                    preview_birth_time,
                ).replace(second=0, microsecond=0)
                preview_birth_info = {
                    "raw_birth_datetime": preview_birth_datetime,
                    "birth_place": preview_birth_place,
                    "birth_country": preview_birth_country,
                    "time_adjustment_enabled": False,
                    "time_adjustment_minutes": 0,
                    "adjusted_birth_datetime": preview_birth_datetime,
                }

                auto_meishiki = calculate_auto_meishiki(
                    preview_birth_info,
                    risshun_datetime=calendar_context["risshun_datetime"],
                    sekki_entries=calendar_context["sekki_entries"],
                    base_date=calendar_context["base_date"],
                    base_day_kanchi=calendar_context["base_day_kanchi"],
                )

                if auto_meishiki.get("error"):
                    st.error("自動命式計算でエラーが発生しました。")
                    st.code(auto_meishiki["error"])
                    return

                preview_meishiki = auto_meishiki_to_manual_format(auto_meishiki)
                smoke_result = run_auto_meishiki_logic_smoke_test(auto_meishiki)
                checks = smoke_result.get("checks", {})
                preview_meishiki = smoke_result.get("manual_meishiki") or preview_meishiki

                st.write("自動命式:")
                for pillar_key in ("hour", "day", "month", "year"):
                    st.write(format_manual_pillar_for_display(preview_meishiki, pillar_key))

                st.write("命式表:")
                st.table(build_auto_meishiki_preview_table(preview_meishiki, checks))

                st.write("空亡:")
                st.write(format_smoke_value(get_smoke_check_data(checks, "kuubou")))
                render_smoke_pillar_values(
                    "通変星",
                    get_smoke_check_data(checks, "tsuhen", {}),
                    day_missing_text="表示対象外",
                )
                render_smoke_pillar_values(
                    "蔵干通変星",
                    get_smoke_check_data(checks, "zokkan_tsuhen", {}),
                )
                render_smoke_pillar_values(
                    "十二運星",
                    get_smoke_check_data(checks, "juuni_unsei", {}),
                )
                render_smoke_gogyou_scores(checks)
                render_smoke_getsurei(checks)
                render_smoke_special_rows(checks)

                errors = smoke_result.get("errors") or []
                if errors:
                    st.error("既存ロジックの一部で取得できない項目があります。")
                    st.code("\n".join(errors))

                warnings = smoke_result.get("warnings") or []
                if warnings:
                    render_smoke_warnings(warnings)

                st.write(
                    "このプレビューは開発確認用です。"
                    "既存の手入力命式や通常の鑑定結果には反映していません。"
                )
            except Exception as exc:
                st.error("自動命式の鑑定結果プレビュー中にエラーが発生しました。")
                st.code(str(exc))


def render_manual_auto_meishiki_comparison_development_panel(current_manual_meishiki):
    with st.expander("手入力命式・自動命式 比較（開発用）"):
        calendar_context = get_development_calendar_context()
        st.warning(
            "これは開発確認用の比較表示です。\n"
            "現在の手入力命式と、自動計算された命式を比較します。\n"
            "自動命式の節入り日時データ、日柱基準日、蔵干は検証用です。\n"
            "比較結果は既存の命式表や鑑定結果には反映されません。"
        )
        st.caption(format_development_calendar_caption(calendar_context))

        compare_birth_date = st.date_input(
            "生年月日",
            value=date(2020, 2, 4),
            min_value=date(1900, 1, 1),
            max_value=date(2050, 12, 31),
            key="manual_auto_compare_birth_date",
        )
        compare_birth_time = st.time_input(
            "出生時刻",
            value=datetime_time(6, 3),
            key="manual_auto_compare_birth_time",
        )
        compare_birth_place = st.text_input(
            "出生地",
            value="日本",
            key="manual_auto_compare_birth_place",
        )
        compare_birth_country = st.text_input(
            "出生国",
            value="日本",
            key="manual_auto_compare_birth_country",
        )

        if st.button(
            "手入力命式と自動命式を比較する（開発用）",
            key="manual_auto_meishiki_compare_button",
        ):
            if not isinstance(current_manual_meishiki, dict):
                st.error("手入力命式がまだ取得できません。")
                st.write("先に手入力命式を入力・表示してください。")
                return

            try:
                compare_birth_datetime = datetime.combine(
                    compare_birth_date,
                    compare_birth_time,
                ).replace(second=0, microsecond=0)
                compare_birth_info = {
                    "raw_birth_datetime": compare_birth_datetime,
                    "birth_place": compare_birth_place,
                    "birth_country": compare_birth_country,
                    "time_adjustment_enabled": False,
                    "time_adjustment_minutes": 0,
                    "adjusted_birth_datetime": compare_birth_datetime,
                }

                auto_meishiki = calculate_auto_meishiki(
                    compare_birth_info,
                    risshun_datetime=calendar_context["risshun_datetime"],
                    sekki_entries=calendar_context["sekki_entries"],
                    base_date=calendar_context["base_date"],
                    base_day_kanchi=calendar_context["base_day_kanchi"],
                )

                if auto_meishiki.get("error"):
                    st.error("自動命式計算でエラーが発生しました。")
                    st.code(auto_meishiki["error"])
                    return

                auto_manual_meishiki = auto_meishiki_to_manual_format(auto_meishiki)
                rows, summary = build_meishiki_comparison_rows(
                    current_manual_meishiki,
                    auto_manual_meishiki,
                )

                render_meishiki_comparison_summary(summary)
                st.write("比較表:")
                st.table(pd.DataFrame(rows))
                st.write("自動計算側の命式:")
                for pillar_key in SMOKE_TEST_PILLAR_ORDER:
                    st.write(format_manual_pillar_for_display(auto_manual_meishiki, pillar_key))
                st.write("この比較結果は、既存の手入力命式表や鑑定結果には反映していません。")
            except Exception as exc:
                st.error("手入力命式と自動命式の比較中にエラーが発生しました。")
                st.code(str(exc))


def render_auto_meishiki_logic_smoke_test_development_panel():
    with st.expander("自動命式 既存ロジック通過テスト（開発用）"):
        calendar_context = get_development_calendar_context()
        st.warning(
            "これは開発確認用の表示です。\n"
            "自動計算された命式を既存の手入力meishiki形式へ変換し、"
            "既存ロジックに通せるかを確認します。\n"
            "現在の蔵干は開発用の簡易蔵干です。\n"
            "本番では先生の流派に合わせて調整が必要です。\n"
            "ここでの結果は、既存の命式表や鑑定結果には反映されません。"
        )
        st.caption(
            "使用する仮データ: "
            f"生年月日={format_datetime_for_display(calendar_context['risshun_datetime'])} / "
            f"{format_development_calendar_caption(calendar_context)}"
        )

        if st.button(
            "既存ロジック通過テストを実行（開発用）",
            key="auto_meishiki_logic_smoke_test_button",
        ):
            try:
                test_birth_datetime = calendar_context["risshun_datetime"]
                test_birth_info = {
                    "raw_birth_datetime": test_birth_datetime,
                    "birth_place": "日本",
                    "birth_country": "日本",
                    "time_adjustment_enabled": False,
                    "time_adjustment_minutes": 0,
                    "adjusted_birth_datetime": test_birth_datetime,
                }

                auto_meishiki = calculate_auto_meishiki(
                    test_birth_info,
                    risshun_datetime=calendar_context["risshun_datetime"],
                    sekki_entries=calendar_context["sekki_entries"],
                    base_date=calendar_context["base_date"],
                    base_day_kanchi=calendar_context["base_day_kanchi"],
                )

                if auto_meishiki.get("error"):
                    st.error("自動命式計算でエラーが発生しました。")
                    st.code(auto_meishiki["error"])
                    return

                result = run_auto_meishiki_logic_smoke_test(auto_meishiki)
                checks = result.get("checks", {})
                manual_format_check = checks.get("manual_format", {})
                manual_meishiki = result.get("manual_meishiki") or {}

                st.write(
                    "この表示は、自動計算した命式を既存ロジックに通した開発用チェックです。"
                )
                st.write(
                    "ここに表示されている項目は、内部計算として成功したものです。"
                )
                st.write(
                    "ただし、まだ既存の命式表や鑑定結果には反映していません。"
                )
                st.write(
                    "既存画面に反映するには、別途接続作業が必要です。"
                )

                if result.get("ok"):
                    st.success("全体結果: OK")
                else:
                    st.error("全体結果: NG")

                st.write(
                    "manual_format: "
                    f"{'OK' if manual_format_check.get('ok') else 'NG'}"
                )

                st.write("変換後meishiki:")
                for pillar_key in ("year", "month", "day", "hour"):
                    st.write(
                        format_manual_pillar_for_display(
                            manual_meishiki,
                            pillar_key,
                        )
                    )

                st.write(f"空亡: {format_smoke_value(get_smoke_check_data(checks, 'kuubou'))}")
                render_smoke_pillar_values(
                    "通変星",
                    get_smoke_check_data(checks, "tsuhen", {}),
                    day_missing_text="表示対象外",
                )
                render_smoke_pillar_values(
                    "蔵干通変星",
                    get_smoke_check_data(checks, "zokkan_tsuhen", {}),
                )
                render_smoke_pillar_values(
                    "十二運星",
                    get_smoke_check_data(checks, "juuni_unsei", {}),
                )
                render_smoke_gogyou_scores(checks)
                render_smoke_special_rows(checks)
                render_smoke_getsurei(checks)
                render_smoke_skipped_checks(checks)

                errors = result.get("errors") or []
                if errors:
                    st.error("errors があります。")
                    st.code("\n".join(errors))

                warnings = result.get("warnings") or []
                render_smoke_warnings(warnings)

                st.write("注意:")
                st.write("- 現在の蔵干は開発用の簡易蔵干です。")
                st.write("- 本番では先生の流派に合わせて調整が必要です。")
                st.write("詳細データ（開発者向けJSON）")
                st.write(
                    "このJSONは補足です。通常は上の日本語表示だけ確認すればよいです。"
                )
                st.json(result)
            except Exception as exc:
                st.error("既存ロジック通過テスト中にエラーが発生しました。")
                st.code(str(exc))

# =========================
# 画面設定

# =========================
st.set_page_config(
    page_title="四柱推命 鑑定補助アプリ",
    page_icon="🔮",
    layout="wide",
)
inject_app_styles()
render_app_header()
inject_mobile_input_styles()

SHOW_DEVELOPMENT_PANELS = False
SHOW_MANUAL_MEISHIKI_INPUT = False

# =========================
# 基本情報

# =========================
st.header("基本情報")
name = st.text_input("氏名")
furigana = st.text_input("ふりがな")
birth_date = st.date_input(
    "生年月日",
    value=date(1988, 8, 12),
    min_value=date(1900, 1, 1),
    max_value=date(2050, 12, 31),
)
st.write("出生時刻")
hour_options = [f"{hour:02d}" for hour in range(24)]
minute_options = [f"{minute:02d}" for minute in range(60)]
birth_time_unknown = st.checkbox("不明")
if birth_time_unknown:
    birth_time_display = "不明"
else:
    birth_hour = st.selectbox("時", hour_options, key="birth_hour")
    birth_minute = st.selectbox("分", minute_options, key="birth_minute")
    birth_time_display = f"{int(birth_hour)}時{int(birth_minute):02d}分生まれ"
prefectures = [
    "未選択",
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県",
    "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県",
    "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県",
    "沖縄県",
]
birth_place_type = st.selectbox("出生地", prefectures)
birth_place_display = birth_place_type
birth_place_for_model = None if birth_place_display == "未選択" else birth_place_display
birth_country_for_model = "日本"
birth_time_for_model = None
if not birth_time_unknown:
    birth_time_for_model = datetime_time(int(birth_hour), int(birth_minute))
birth_time_for_calculation = get_birth_time_for_calculation(
    birth_time_unknown,
    birth_time_for_model,
)
birth_place_for_calculation = None if birth_time_unknown else birth_place_for_model
birth_info = build_birth_info(
    birth_date=birth_date,
    birth_time=birth_time_for_calculation,
    birth_place=birth_place_for_calculation,
    birth_country=birth_country_for_model,
    time_adjustment_enabled=False,
    time_adjustment_minutes=0,
)
birth_info["birth_time_unknown"] = bool(birth_time_unknown)
birth_info["display_birth_place"] = birth_place_for_model or ""
adjusted_birth_datetime = birth_info.get("adjusted_birth_datetime")
calculation_birth_date = (
    adjusted_birth_datetime.date()
    if adjusted_birth_datetime is not None
    else birth_date
)
gender = st.selectbox(
    "性別",
    ["未選択", "男性", "女性", "その他・回答しない"]
)
consultation = st.text_area("相談内容")
reading_date = st.date_input(
    "鑑定日",
    value=date.today(),
    min_value=date(1900, 1, 1),
    max_value=date(2050, 12, 31),
)
specific_datetime_enabled = st.checkbox("特定の日時について占う")
specific_datetime_candidates = []
if specific_datetime_enabled:
    specific_datetime_count = st.selectbox(
        "候補数",
        [1, 2, 3],
        key="specific_datetime_count",
    )
    default_candidate_hours = [14, 10, 9]
    for candidate_index in range(int(specific_datetime_count)):
        candidate_number = candidate_index + 1
        st.markdown(f"**候補{candidate_number}**")
        candidate_date = st.date_input(
            f"候補{candidate_number} 日付",
            value=reading_date,
            min_value=date(1900, 1, 1),
            max_value=date(2050, 12, 31),
            key=f"specific_candidate_date_{candidate_number}",
        )
        candidate_hour_col, candidate_minute_col = st.columns(2)
        with candidate_hour_col:
            candidate_hour = st.selectbox(
                f"候補{candidate_number} 時",
                hour_options,
                index=default_candidate_hours[candidate_index],
                key=f"specific_candidate_hour_{candidate_number}",
            )
        with candidate_minute_col:
            candidate_minute = st.selectbox(
                f"候補{candidate_number} 分",
                minute_options,
                index=0,
                key=f"specific_candidate_minute_{candidate_number}",
            )
        specific_datetime_candidates.append(
            {
                "date": candidate_date,
                "time": datetime_time(int(candidate_hour), int(candidate_minute)),
            }
        )
inject_date_input_keyboard_guard()

if SHOW_DEVELOPMENT_PANELS:
    render_auto_meishiki_reading_preview_development_panel()

# =========================
# 四柱入力

# =========================
tenkan_options = ["", "甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
chishi_options = ["", "子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
# 蔵干も最初は手入力にする
zokkan_options = ["", "甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]

if SHOW_MANUAL_MEISHIKI_INPUT:
    st.header("四柱入力")
    # 左から「時柱・日柱・月柱・年柱」
    col_hour, col_day, col_month, col_year = st.columns(4)
    with col_hour:
        st.subheader("時柱")
        hour_tenkan = st.selectbox("時干", tenkan_options, key="hour_tenkan")
        hour_chishi = st.selectbox("時支", chishi_options, key="hour_chishi")
        hour_zokkan = st.selectbox("時柱の蔵干", zokkan_options, key="hour_zokkan")
    with col_day:
        st.subheader("日柱")
        day_tenkan = st.selectbox("日干", tenkan_options, key="day_tenkan")
        day_chishi = st.selectbox("日支", chishi_options, key="day_chishi")
        day_zokkan = st.selectbox("日柱の蔵干", zokkan_options, key="day_zokkan")
    with col_month:
        st.subheader("月柱")
        month_tenkan = st.selectbox("月干", tenkan_options, key="month_tenkan")
        month_chishi = st.selectbox("月支", chishi_options, key="month_chishi")
        month_zokkan = st.selectbox("月柱の蔵干", zokkan_options, key="month_zokkan")
    with col_year:
        st.subheader("年柱")
        year_tenkan = st.selectbox("年干", tenkan_options, key="year_tenkan")
        year_chishi = st.selectbox("年支", chishi_options, key="year_chishi")
        year_zokkan = st.selectbox("年柱の蔵干", zokkan_options, key="year_zokkan")
else:
    hour_tenkan = ""
    day_tenkan = ""
    month_tenkan = ""
    year_tenkan = ""
    hour_chishi = ""
    day_chishi = ""
    month_chishi = ""
    year_chishi = ""
    hour_zokkan = ""
    day_zokkan = ""
    month_zokkan = ""
    year_zokkan = ""

# =========================
# 通変星・蔵干通変星計算

# =========================
meishiki = build_meishiki_from_manual_input(
    year_tenkan,
    month_tenkan,
    day_tenkan,
    hour_tenkan,
    year_chishi,
    month_chishi,
    day_chishi,
    hour_chishi,
    year_zokkan,
    month_zokkan,
    day_zokkan,
    hour_zokkan,
)

effective_meishiki_result = select_effective_meishiki(
    input_mode="manual",
    manual_meishiki=meishiki,
)
effective_meishiki = effective_meishiki_result.get("meishiki") or meishiki
effective_meishiki_source_label = "自動計算命式"

calendar_context = get_calendar_context_for_birth_year(calculation_birth_date.year)
auto_calculation_errors = []
if not calendar_context.get("ok"):
    auto_calculation_errors.extend(calendar_context.get("errors", []))
else:
    try:
        auto_effective_meishiki = calculate_auto_meishiki(
            birth_info,
            risshun_datetime=calendar_context["risshun_datetime"],
            sekki_entries=calendar_context["sekki_entries"],
            base_date=calendar_context["base_date"],
            base_day_kanchi=calendar_context["base_day_kanchi"],
        )
        effective_meishiki_result = select_effective_meishiki(
            input_mode="auto",
            manual_meishiki=meishiki,
            auto_meishiki=auto_effective_meishiki,
        )

        if effective_meishiki_result.get("ok"):
            effective_meishiki = effective_meishiki_result["meishiki"]
        else:
            auto_calculation_errors.extend(effective_meishiki_result.get("errors", []))
    except Exception as exc:
        auto_calculation_errors.append(str(exc))

if birth_time_unknown:
    effective_meishiki = clear_hour_pillar_for_unknown_birth_time(effective_meishiki)

effective_hour_tenkan = get_manual_pillar_value(effective_meishiki, "hour", "tenkan")
effective_day_tenkan = get_manual_pillar_value(effective_meishiki, "day", "tenkan")
effective_month_tenkan = get_manual_pillar_value(effective_meishiki, "month", "tenkan")
effective_year_tenkan = get_manual_pillar_value(effective_meishiki, "year", "tenkan")
effective_hour_chishi = get_manual_pillar_value(effective_meishiki, "hour", "chishi")
effective_day_chishi = get_manual_pillar_value(effective_meishiki, "day", "chishi")
effective_month_chishi = get_manual_pillar_value(effective_meishiki, "month", "chishi")
effective_year_chishi = get_manual_pillar_value(effective_meishiki, "year", "chishi")
effective_hour_zokkan = get_manual_pillar_value(effective_meishiki, "hour", "zokkan")
effective_day_zokkan = get_manual_pillar_value(effective_meishiki, "day", "zokkan")
effective_month_zokkan = get_manual_pillar_value(effective_meishiki, "month", "zokkan")
effective_year_zokkan = get_manual_pillar_value(effective_meishiki, "year", "zokkan")

hour_tsuhensei = get_tsuhensei(effective_day_tenkan, effective_hour_tenkan)
month_tsuhensei = get_tsuhensei(effective_day_tenkan, effective_month_tenkan)
year_tsuhensei = get_tsuhensei(effective_day_tenkan, effective_year_tenkan)
hour_zokkan_tsuhensei = get_tsuhensei(effective_day_tenkan, effective_hour_zokkan)
day_zokkan_tsuhensei = get_tsuhensei(effective_day_tenkan, effective_day_zokkan)
month_zokkan_tsuhensei = get_tsuhensei(effective_day_tenkan, effective_month_zokkan)
year_zokkan_tsuhensei = get_tsuhensei(effective_day_tenkan, effective_year_zokkan)
# 十二運星計算
hour_juuni_unsei = get_juuni_unsei(effective_day_tenkan, effective_hour_chishi)
day_juuni_unsei = get_juuni_unsei(effective_day_tenkan, effective_day_chishi)
month_juuni_unsei = get_juuni_unsei(effective_day_tenkan, effective_month_chishi)
year_juuni_unsei = get_juuni_unsei(effective_day_tenkan, effective_year_chishi)

# 空亡計算
display_kubou = get_kubou(effective_day_tenkan, effective_day_chishi)

# 五行バランス計算
analysis_context = build_analysis_context(reading_date)
kantei_year_tenkan = analysis_context["target_year_tenkan"]
kantei_year_chishi = analysis_context["target_year_chishi"]
gogyo_result = calculate_gogyo_scores_from_meishiki(
    effective_meishiki,
    analysis_context,
)

# 異常干支判定（後で表示に使うため、内部的に計算しておく）
ijou_kanshi_data = build_ijou_kanshi_data_from_meishiki(effective_meishiki)
effective_month_kanchi = ""
if effective_month_tenkan and effective_month_chishi:
    effective_month_kanchi = f"{effective_month_tenkan}{effective_month_chishi}"

daiun_result = build_daiun_table(
    birth_date=calculation_birth_date,
    birth_year=calculation_birth_date.year if calculation_birth_date else None,
    gender=gender,
    year_tenkan=effective_year_tenkan,
    month_kanchi=effective_month_kanchi,
    day_tenkan=effective_day_tenkan,
    sekki_entries=calendar_context.get("sekki_entries", []),
)
yearly_flow_result = build_yearly_monthly_flow(
    reading_date=reading_date,
    day_tenkan=effective_day_tenkan,
    kubou=display_kubou,
)
yearly_overall_result = build_yearly_overall_fortune(
    reading_date=reading_date,
    day_tenkan=effective_day_tenkan,
)
specific_datetime_result = (
    build_specific_datetime_fortunes(
        specific_datetime_candidates,
        effective_day_tenkan,
    )
    if specific_datetime_enabled
    else {"ok": True, "rows": [], "errors": []}
)
specific_datetime_rows = (
    specific_datetime_result.get("rows", [])
    if isinstance(specific_datetime_result, dict)
    else []
)
show_specific_datetime_section = bool(
    specific_datetime_enabled
    and specific_datetime_candidates
    and specific_datetime_rows
)

# =========================
# 鑑定結果

# =========================
if st.button("鑑定結果を表示する"):
    st.header("鑑定結果")
    if auto_calculation_errors:
        st.error("命式を自動計算できませんでした。")
        for error in auto_calculation_errors:
            st.write(f"- {error}")
        st.stop()
    st.subheader("基本情報")
    basic_info_rows = []
    if name.strip():
        basic_info_rows.append({"項目": "氏名", "内容": name})
    if furigana.strip():
        basic_info_rows.append({"項目": "ふりがな", "内容": furigana})
    basic_info_rows.append({"項目": "生年月日", "内容": birth_date})
    basic_info_rows.append({"項目": "出生時刻", "内容": birth_time_display})
    if birth_place_display and birth_place_display != "未選択":
        basic_info_rows.append({"項目": "出生地", "内容": birth_place_display})
    if gender and gender != "未選択":
        basic_info_rows.append({"項目": "性別", "内容": gender})
    if consultation.strip():
        basic_info_rows.append({"項目": "相談内容", "内容": consultation})
    basic_info_rows.append({"項目": "鑑定日", "内容": reading_date})
    client_basic_info_rows = build_client_basic_info_rows(
        name,
        furigana,
        birth_date,
        birth_time_for_model,
        birth_place_display,
        gender,
        consultation,
        reading_date,
    )
    st.table(pd.DataFrame(client_basic_info_rows))
    st.subheader("命式表")
    meishiki_data = {
        "項目": [
            "天干",
            "地支",
            "蔵干",
            "通変星",
            "蔵干通変星",
            "十二運星",
        ],
        "時柱": [
            effective_hour_tenkan,
            effective_hour_chishi,
            effective_hour_zokkan,
            hour_tsuhensei,
            hour_zokkan_tsuhensei,
            hour_juuni_unsei if hour_juuni_unsei else "未入力",
        ],
        "日柱": [
            effective_day_tenkan,
            effective_day_chishi,
            effective_day_zokkan,
            "－",
            day_zokkan_tsuhensei,
            day_juuni_unsei if day_juuni_unsei else "未入力",
        ],
        "月柱": [
            effective_month_tenkan,
            effective_month_chishi,
            effective_month_zokkan,
            month_tsuhensei,
            month_zokkan_tsuhensei,
            month_juuni_unsei if month_juuni_unsei else "未入力",
        ],
        "年柱": [
            effective_year_tenkan,
            effective_year_chishi,
            effective_year_zokkan,
            year_tsuhensei,
            year_zokkan_tsuhensei,
            year_juuni_unsei if year_juuni_unsei else "未入力",
        ],
    }
    st.table(meishiki_data)
    render_inline_help_heading("空亡", KUUBOU_HELP_TEXT)
    st.write(f"空亡：{display_kubou if display_kubou else '未入力'}")
    st.subheader("五行のバランス")
    render_public_gogyo_balance(gogyo_result, effective_day_tenkan)
    life_stage_tsuhensei_data = [
        {
            "stage": "0〜4歳",
            "outer": "－",
            "inner": day_zokkan_tsuhensei,
        },
        {
            "stage": "5〜29歳",
            "outer": year_tsuhensei,
            "inner": year_zokkan_tsuhensei,
        },
        {
            "stage": "30〜64歳",
            "outer": month_tsuhensei,
            "inner": month_zokkan_tsuhensei,
        },
        {
            "stage": "65歳以降",
            "outer": hour_tsuhensei,
            "inner": hour_zokkan_tsuhensei,
        },
    ]
    juuni_unsei_display_data = [
        {
            "pillar_key": "year",
            "pillar_label": "年柱",
            "personality_heading": "意思決定の時の自分",
            "juuni_unsei": year_juuni_unsei,
        },
        {
            "pillar_key": "month",
            "pillar_label": "月柱",
            "personality_heading": "初対面の人と会った時の自分",
            "juuni_unsei": month_juuni_unsei,
        },
        {
            "pillar_key": "day",
            "pillar_label": "日柱",
            "personality_heading": "一人の時の自分",
            "juuni_unsei": day_juuni_unsei,
        },
        {
            "pillar_key": "hour",
            "pillar_label": "時柱",
            "personality_heading": "どんな老後を過ごしたいか",
            "juuni_unsei": hour_juuni_unsei,
        },
    ]
    public_comment_sections = [
        "特殊な命式",
        "日干から読み取れる性格",
        "通変星・蔵干通変星から読み取れる性格",
        "十二運星から読み取れる性格",
        "大運と接木運",
        "今年の運勢の流れ",
    ]
    if show_specific_datetime_section:
        public_comment_sections.append("特定日時での運勢")
    public_comment_sections.append("今年一年の総合運勢")

    private_comment_sections = [
        "特殊な命式",
        "日干から読み取れる性格",
        "通変星・蔵干通変星から読み取れる性格",
        "十二運星から読み取れる性格",
        "総合的に読み取れる性格",
        "大運と接木運",
        "今年の運勢の流れ",
    ]
    if show_specific_datetime_section:
        private_comment_sections.append("特定日時での運勢")
    private_comment_sections.append("今年一年の総合運勢")

    for section_title in public_comment_sections:
        st.subheader(section_title)
        if section_title == "特殊な命式":
            render_special_meishiki(ijou_kanshi_data, gogyo_result)
        elif section_title == "日干から読み取れる性格":
            render_nikkan_public_comment(effective_day_tenkan)
        elif section_title == "通変星・蔵干通変星から読み取れる性格":
            render_public_tsuhensei_comments_for_audience(
                life_stage_tsuhensei_data,
                month_zokkan_tsuhensei,
                month_tsuhensei,
            )
        elif section_title == "十二運星から読み取れる性格":
            render_juuni_unsei_comments_for_mobile(
                juuni_unsei_display_data,
                "public",
            )
        elif section_title == "大運と接木運":
            render_client_daiun_table(daiun_result, display_kubou)
        elif section_title == "今年の運勢の流れ":
            render_client_yearly_monthly_flow(yearly_flow_result)
        elif section_title == "特定日時での運勢":
            render_specific_datetime_fortunes(
                specific_datetime_result,
                specific_datetime_enabled,
            )
        elif section_title == "今年一年の総合運勢":
            render_yearly_overall_fortune(yearly_overall_result)
        else:
            pass
    with st.expander("鑑定者用メモ", expanded=False):
        st.subheader("基本情報")
        st.table(pd.DataFrame(basic_info_rows))
        render_birthplace_time_adjustment_note(birth_info)

        st.subheader("命式表")
        st.table(meishiki_data)

        st.subheader("空亡")
        st.write(f"空亡：{display_kubou if display_kubou else '未入力'}")

        st.subheader("五行のバランス")
        render_gogyo_balance(gogyo_result, effective_day_tenkan)

        for section_title in private_comment_sections:
            st.subheader(section_title)
            if section_title == "特殊な命式":
                render_special_meishiki(ijou_kanshi_data, gogyo_result)
            elif section_title == "日干から読み取れる性格":
                pass
            elif section_title == "通変星・蔵干通変星から読み取れる性格":
                render_private_tsuhensei_comments(life_stage_tsuhensei_data)
                render_private_month_pair_comment(
                    month_zokkan_tsuhensei,
                    month_tsuhensei,
                )
            elif section_title == "十二運星から読み取れる性格":
                render_juuni_unsei_comments_for_mobile(
                    juuni_unsei_display_data,
                    "private",
                )
            elif section_title == "大運と接木運":
                render_daiun_table(daiun_result, display_kubou)
            elif section_title == "今年の運勢の流れ":
                render_yearly_monthly_flow(yearly_flow_result)
            elif section_title == "特定日時での運勢":
                render_specific_datetime_fortunes(
                    specific_datetime_result,
                    specific_datetime_enabled,
                )
            elif section_title == "今年一年の総合運勢":
                render_yearly_overall_fortune(yearly_overall_result)
            else:
                pass
