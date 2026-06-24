from html import escape
from math import hypot

import pandas as pd
import streamlit as st
try:
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as font_manager
except ImportError:
    plt = None
    font_manager = None

from fortune_data import GOGYO_ORDER
from gogyou_logic import (
    format_gogyo_special_flags,
    get_gogyo_chart_order,
    init_gogyo_scores,
)
from utils import format_score_percent

CHART_COLORS = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759"]
GOGYO_RELATION_LAYOUT = [
    {"label": "自我の星", "x": 210, "y": 90, "label_y": 32},
    {"label": "表現の星", "x": 326, "y": 174, "label_y": 124},
    {"label": "魅力の星", "x": 286, "y": 294, "label_y": 362},
    {"label": "行動の星", "x": 134, "y": 294, "label_y": 362},
    {"label": "知性の星", "x": 94, "y": 174, "label_y": 124},
]
GOGYO_NODE_RADIUS = 36
GOGYO_CHART_CENTER = (210, 220)
GOGYO_SEISHO_CURVE_OFFSET = 44
GOGYO_SEISHO_PATH = [0, 1, 2, 3, 4, 0]
GOGYO_SEIKOKU_PATH = [0, 2, 4, 1, 3, 0]
JAPANESE_FONT_CANDIDATES = [
    "Noto Sans CJK JP",
    "Noto Sans JP",
    "Noto Serif CJK JP",
    "IPAexGothic",
    "IPAGothic",
    "TakaoGothic",
    "Yu Gothic",
    "Meiryo",
    "MS Gothic",
    "Hiragino Sans",
]

def to_numeric_scores(score_dict):
    numeric_scores = {}

    for label, score in score_dict.items():
        try:
            numeric_scores[label] = float(score)
        except (TypeError, ValueError):
            numeric_scores[label] = 0

    return numeric_scores


def write_chart_score_caption(score_dict):
    st.caption(
        " / ".join(
            f"{label}: {format_score_percent(score)}"
            for label, score in score_dict.items()
        )
    )


def get_chart_scale(numeric_scores):
    total = sum(value for value in numeric_scores.values() if value > 0)
    if total <= 100:
        return 100
    return total


def show_100_percent_stacked_bar_html(score_dict):
    numeric_scores = to_numeric_scores(score_dict)
    scale = get_chart_scale(numeric_scores)
    segments = []

    for index, (label, value) in enumerate(numeric_scores.items()):
        if value <= 0:
            continue

        width = value / scale * 100
        color = CHART_COLORS[index % len(CHART_COLORS)]
        text = f"{value:.0f}%" if width >= 8 else ""
        segments.append(
            "<div "
            f"title=\"{escape(label)} {value:.0f}%\" "
            "style=\""
            f"width:{width:.2f}%;"
            f"background:{color};"
            "display:flex;"
            "align-items:center;"
            "justify-content:center;"
            "color:white;"
            "font-size:12px;"
            "min-height:24px;"
            "\">"
            f"{escape(text)}"
            "</div>"
        )

    st.markdown(
        "<div style=\""
        "width:100%;"
        "height:24px;"
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
    write_chart_score_caption(numeric_scores)


def show_horizontal_bar_html(score_dict):
    numeric_scores = to_numeric_scores(score_dict)
    scale = get_chart_scale(numeric_scores)
    rows = []

    for index, (label, value) in enumerate(numeric_scores.items()):
        width = value / scale * 100 if value > 0 else 0
        color = CHART_COLORS[index % len(CHART_COLORS)]
        rows.append(
            "<div style=\"margin:8px 0;\">"
            "<div style=\"display:flex;justify-content:space-between;gap:12px;\">"
            f"<span>{escape(label)}</span>"
            f"<span>{value:.0f}%</span>"
            "</div>"
            "<div style=\""
            "height:20px;"
            "background:#f6f8fa;"
            "border:1px solid #d0d7de;"
            "border-radius:4px;"
            "overflow:hidden;"
            "\">"
            "<div style=\""
            f"width:{width:.2f}%;"
            f"background:{color};"
            "height:100%;"
            "\"></div>"
            "</div>"
            "</div>"
        )

    st.markdown("".join(rows), unsafe_allow_html=True)


def show_pie_chart_html(score_dict):
    numeric_scores = to_numeric_scores(score_dict)
    total = sum(value for value in numeric_scores.values() if value > 0)

    if total <= 0:
        st.write("集計できるデータがありません。")
        return

    segments = []
    start = 0

    for index, (_label, value) in enumerate(numeric_scores.items()):
        if value <= 0:
            continue

        width = value / total * 100
        end = start + width
        color = CHART_COLORS[index % len(CHART_COLORS)]
        segments.append(f"{color} {start:.2f}% {end:.2f}%")
        start = end

    st.markdown(
        "<div style=\""
        "width:220px;"
        "height:220px;"
        "border-radius:50%;"
        f"background:conic-gradient({', '.join(segments)});"
        "border:1px solid #d0d7de;"
        "margin:8px 0;"
        "\"></div>",
        unsafe_allow_html=True,
    )

    legend_rows = []

    for index, (label, value) in enumerate(numeric_scores.items()):
        if value <= 0:
            continue

        color = CHART_COLORS[index % len(CHART_COLORS)]
        legend_rows.append(
            "<div style=\"display:flex;align-items:center;gap:8px;margin:4px 0;\">"
            f"<span style=\"width:12px;height:12px;background:{color};display:inline-block;\"></span>"
            f"<span>{escape(label)}: {value / total * 100:.0f}%</span>"
            "</div>"
        )

    st.markdown("".join(legend_rows), unsafe_allow_html=True)


def show_pie_chart(title, score_dict):
    st.markdown(f"#### {title}")

    if not score_dict:
        st.write("集計できるデータがありません。")
        return

    numeric_scores = to_numeric_scores(score_dict)
    filtered_scores = {
        label: value
        for label, value in numeric_scores.items()
        if value > 0
    }

    if not filtered_scores:
        st.write("集計できるデータがありません。")
        return

    total = sum(filtered_scores.values())
    labels = list(filtered_scores.keys())
    values = list(filtered_scores.values())
    graph_labels = [str(index + 1) for index in range(len(labels))]

    if plt is None:
        show_pie_chart_html(filtered_scores)
    else:
        fig, ax = plt.subplots(figsize=(4.5, 4.5))
        ax.pie(
            values,
            labels=graph_labels,
            autopct="%1.0f%%",
            startangle=90,
        )
        ax.axis("equal")
        st.pyplot(fig)
        plt.close(fig)

    label_table = pd.DataFrame(
        {
            "番号": graph_labels,
            "分類": labels,
            "割合": [format_score_percent(value / total * 100) for value in values],
        }
    )
    st.table(label_table)


def show_score_bar_chart(title, score_dict):
    st.markdown(f"#### {title}")

    if not score_dict or not any(score_dict.values()):
        st.write("集計できるデータがありません。")
        return

    chart_data = pd.DataFrame(
        {
            "分類": list(score_dict.keys()),
            "割合": list(score_dict.values()),
        }
    ).set_index("分類")

    st.bar_chart(chart_data)


def show_100_percent_stacked_bar(title, score_dict):
    st.markdown(f"#### {title}")

    if not score_dict:
        st.write("集計できるデータがありません。")
        return

    numeric_scores = to_numeric_scores(score_dict)

    if not any(numeric_scores.values()):
        st.write("集計できるデータがありません。")
        write_chart_score_caption(numeric_scores)
        return

    if plt is None:
        show_100_percent_stacked_bar_html(numeric_scores)
        return

    fig, ax = plt.subplots(figsize=(7, 1.2))
    left = 0

    for _label, value in numeric_scores.items():
        if value <= 0:
            continue

        ax.barh([0], [value], left=left)

        if value >= 8:
            ax.text(
                left + value / 2,
                0,
                f"{value:.0f}%",
                ha="center",
                va="center",
                color="white",
                fontsize=9,
            )

        left += value

    ax.set_xlim(0, 100)
    ax.set_yticks([])
    ax.set_xlabel("0-100%")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)

    st.pyplot(fig)
    plt.close(fig)
    write_chart_score_caption(numeric_scores)


def show_horizontal_bar_chart(title, score_dict):
    st.markdown(f"#### {title}")

    if not score_dict:
        st.write("集計できるデータがありません。")
        return

    numeric_scores = to_numeric_scores(score_dict)
    labels = list(numeric_scores.keys())
    values = list(numeric_scores.values())

    if not any(values):
        st.write("集計できるデータがありません。")
        write_chart_score_caption(numeric_scores)
        return

    if plt is None:
        show_horizontal_bar_html(numeric_scores)
        return

    fig, ax = plt.subplots(figsize=(7, 3))
    positions = list(range(len(labels)))
    graph_labels = [str(position + 1) for position in positions]

    ax.barh(graph_labels, values)
    ax.set_xlim(0, 100)
    ax.set_xlabel("0-100%")
    ax.invert_yaxis()

    for position, value in zip(positions, values):
        ax.text(value + 1, position, f"{value:.0f}%", va="center")

    st.pyplot(fig)
    plt.close(fig)

    label_table = pd.DataFrame(
        {
            "番号": graph_labels,
            "分類": labels,
            "割合": [format_score_percent(value) for value in values],
        }
    )
    st.table(label_table)


def configure_matplotlib_japanese_font():
    if plt is None:
        return False

    plt.rcParams["axes.unicode_minus"] = False

    if font_manager is None:
        return False

    available_fonts = {
        font.name
        for font in font_manager.fontManager.ttflist
    }
    for font_name in JAPANESE_FONT_CANDIDATES:
        if font_name in available_fonts:
            plt.rcParams["font.family"] = [font_name]
            return True

    return False


def format_gogyo_node_score(value):
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return "0"

    if numeric_value.is_integer():
        return str(int(numeric_value))

    return f"{numeric_value:.1f}".rstrip("0").rstrip(".")


def shorten_arrow(start, end, start_offset=GOGYO_NODE_RADIUS + 8, end_offset=GOGYO_NODE_RADIUS + 8):
    start_x, start_y = start
    end_x, end_y = end
    distance = hypot(end_x - start_x, end_y - start_y)

    if distance == 0:
        return start_x, start_y, end_x, end_y

    unit_x = (end_x - start_x) / distance
    unit_y = (end_y - start_y) / distance

    return (
        start_x + unit_x * start_offset,
        start_y + unit_y * start_offset,
        end_x - unit_x * end_offset,
        end_y - unit_y * end_offset,
    )


def build_gogyo_arrow_paths(nodes, index_path, css_class):
    paths = []

    for start_index, end_index in zip(index_path, index_path[1:]):
        start = nodes[start_index]
        end = nodes[end_index]
        start_x, start_y, end_x, end_y = shorten_arrow(
            (start["x"], start["y"]),
            (end["x"], end["y"]),
        )
        paths.append(
            "<line "
            f"class=\"{css_class}\" "
            f"x1=\"{start_x:.1f}\" y1=\"{start_y:.1f}\" "
            f"x2=\"{end_x:.1f}\" y2=\"{end_y:.1f}\" "
            "/>"
        )

    return "\n".join(paths)


def build_gogyo_curved_arrow_paths(nodes, index_path, css_class):
    paths = []
    center_x, center_y = GOGYO_CHART_CENTER

    for start_index, end_index in zip(index_path, index_path[1:]):
        start = nodes[start_index]
        end = nodes[end_index]
        start_x, start_y, end_x, end_y = shorten_arrow(
            (start["x"], start["y"]),
            (end["x"], end["y"]),
        )
        mid_x = (start_x + end_x) / 2
        mid_y = (start_y + end_y) / 2
        outward_x = mid_x - center_x
        outward_y = mid_y - center_y
        outward_length = hypot(outward_x, outward_y) or 1
        control_x = mid_x + outward_x / outward_length * GOGYO_SEISHO_CURVE_OFFSET
        control_y = mid_y + outward_y / outward_length * GOGYO_SEISHO_CURVE_OFFSET
        paths.append(
            "<path "
            f"class=\"{css_class}\" "
            f"d=\"M {start_x:.1f} {start_y:.1f} Q {control_x:.1f} {control_y:.1f} {end_x:.1f} {end_y:.1f}\" "
            "/>"
        )

    return "\n".join(paths)


def build_gogyo_relationship_svg(scores, day_tenkan):
    chart_order = get_gogyo_chart_order(day_tenkan)
    nodes = []

    for layout, element in zip(GOGYO_RELATION_LAYOUT, chart_order):
        nodes.append({
            "label": layout["label"],
            "element": element,
            "score": format_gogyo_node_score(scores.get(element, 0)),
            "x": layout["x"],
            "y": layout["y"],
            "label_y": layout["label_y"],
        })

    node_markup = []
    for node in nodes:
        node_markup.append(
            "<g>"
            f"<text class=\"gogyo-role\" x=\"{node['x']}\" y=\"{node['label_y']}\">"
            f"{escape(node['label'])}"
            "</text>"
            f"<circle class=\"gogyo-node\" cx=\"{node['x']}\" cy=\"{node['y']}\" r=\"{GOGYO_NODE_RADIUS}\" />"
            f"<text class=\"gogyo-value\" x=\"{node['x']}\" y=\"{node['y'] + 6}\">"
            f"{escape(node['element'])} {escape(node['score'])}"
            "</text>"
            "</g>"
        )

    seisho_paths = build_gogyo_curved_arrow_paths(nodes, GOGYO_SEISHO_PATH, "gogyo-seisho")
    seikoku_paths = build_gogyo_arrow_paths(nodes, GOGYO_SEIKOKU_PATH, "gogyo-seikoku")

    return (
        "<svg class=\"gogyo-relationship-svg\" viewBox=\"0 0 420 430\" "
        "role=\"img\" aria-label=\"五行バランス図\" xmlns=\"http://www.w3.org/2000/svg\">"
        "<defs>"
        "<marker id=\"gogyo-seisho-arrow\" viewBox=\"0 0 10 10\" refX=\"8\" refY=\"5\" "
        "markerWidth=\"7\" markerHeight=\"7\" orient=\"auto-start-reverse\">"
        "<path d=\"M 0 0 L 10 5 L 0 10 z\" fill=\"#8b949e\" />"
        "</marker>"
        "<marker id=\"gogyo-seikoku-arrow\" viewBox=\"0 0 10 10\" refX=\"8\" refY=\"5\" "
        "markerWidth=\"7\" markerHeight=\"7\" orient=\"auto-start-reverse\">"
        "<path d=\"M 0 0 L 10 5 L 0 10 z\" fill=\"#d97706\" />"
        "</marker>"
        "<style>"
        ".gogyo-relationship-svg{width:100%;max-width:480px;height:auto;display:block;margin:0 auto;}"
        ".gogyo-seisho{stroke:#8b949e;stroke-width:2.5;fill:none;marker-end:url(#gogyo-seisho-arrow);}"
        ".gogyo-seikoku{stroke:#d97706;stroke-width:2.4;fill:none;marker-end:url(#gogyo-seikoku-arrow);}"
        ".gogyo-node{fill:#ffffff;stroke:#24292f;stroke-width:2.2;}"
        ".gogyo-role{font-size:15px;font-weight:700;fill:#24292f;text-anchor:middle;dominant-baseline:middle;}"
        ".gogyo-value{font-size:20px;font-weight:700;fill:#111827;text-anchor:middle;dominant-baseline:middle;}"
        ".gogyo-legend{font-size:13px;font-weight:700;fill:#57606a;text-anchor:start;dominant-baseline:middle;}"
        "</style>"
        "</defs>"
        "<rect x=\"8\" y=\"8\" width=\"404\" height=\"414\" rx=\"8\" fill=\"#ffffff\" stroke=\"#d0d7de\" />"
        f"{seisho_paths}"
        f"{seikoku_paths}"
        f"{''.join(node_markup)}"
        "<line x1=\"120\" y1=\"402\" x2=\"152\" y2=\"402\" class=\"gogyo-seisho\" />"
        "<text x=\"162\" y=\"402\" class=\"gogyo-legend\">相生</text>"
        "<line x1=\"232\" y1=\"402\" x2=\"264\" y2=\"402\" class=\"gogyo-seikoku\" />"
        "<text x=\"274\" y=\"402\" class=\"gogyo-legend\">相剋</text>"
        "</svg>"
    )


def show_gogyo_relationship_chart(scores, day_tenkan):
    st.markdown(
        build_gogyo_relationship_svg(scores, day_tenkan),
        unsafe_allow_html=True,
    )


def render_gogyo_balance(gogyo_result, day_tenkan):
    scores = gogyo_result.get("scores", init_gogyo_scores())
    ordered_scores = {element: scores.get(element, 0) for element in GOGYO_ORDER}
    kantei_year = gogyo_result.get("kantei_year", {})
    kantei_year_tenkan = kantei_year.get("tenkan", "")
    kantei_year_chishi = kantei_year.get("chishi", "")

    if kantei_year_tenkan and kantei_year_chishi:
        st.caption(f"鑑定年の干支（作用判定用）：{kantei_year_tenkan}{kantei_year_chishi}")

    score_table = pd.DataFrame(
        {
            "五行": list(ordered_scores.keys()),
            "点数": list(ordered_scores.values()),
        }
    )
    st.table(score_table)
    show_gogyo_relationship_chart(ordered_scores, day_tenkan)

    with st.expander("五行点数の内訳"):
        special_flags = gogyo_result.get("special_flags", {})
        st.markdown("#### 特殊判定結果")
        st.table(pd.DataFrame(format_gogyo_special_flags(special_flags)))

        st.markdown("#### 加点内訳")
        details = gogyo_result.get("details", [])

        if details:
            st.table(pd.DataFrame(details))
        else:
            st.write("内訳データはありません。")
