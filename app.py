from __future__ import annotations

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import date, datetime, time as datetime_time

from calendar_logic import calculate_auto_meishiki
from calendar_reference import (
    get_calendar_context_for_birth_year,
    get_development_calendar_context,
)
from chart_render import render_gogyo_balance
from gogyou_logic import calculate_gogyo_scores_from_meishiki
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
    aggregate_juuni_unsei_thinking_tendency,
    get_kubou,
    get_juuni_unsei,
    get_tsuhensei,
    render_juuni_unsei_detail,
    render_juuni_unsei_summary_table,
    render_juuni_unsei_thinking_charts,
    render_juuni_unsei_thinking_pillar_table,
    render_juuni_unsei_thinking_score_table,
    render_nikkan_public_comment,
    render_private_month_pair_comment,
    render_private_tsuhensei_comments,
    render_public_month_pair_comment,
    render_public_tsuhensei_comments,
)
from special_chart_logic import (
    SPECIAL_CHART_EMPTY_MESSAGE,
    build_ijou_kanshi_data_from_meishiki,
    build_special_meishiki_rows,
)


def render_special_meishiki(ijou_kanshi_data, gogyo_result):
    rows = build_special_meishiki_rows(ijou_kanshi_data, gogyo_result)

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


def render_juuni_unsei_comments_for_mobile(juuni_unsei_display_data, comment_type):
    summary_title = (
        "十二運星から読み取れる性格の詳細表"
        if comment_type == "public"
        else "十二運星から読み取れる性格メモの詳細表"
    )
    with st.expander(summary_title, expanded=False):
        render_juuni_unsei_summary_table(juuni_unsei_display_data)

    for data in juuni_unsei_display_data:
        render_juuni_unsei_detail(data, comment_type)


def render_juuni_unsei_thinking_tendency_for_mobile(
    pillar_juuni_unsei_data,
    is_private=False,
):
    if is_private:
        st.markdown("#### 十二運星から読み取れる考え方の傾向メモ")

    with st.expander("四柱ごとの分類表", expanded=False):
        render_juuni_unsei_thinking_pillar_table(pillar_juuni_unsei_data)

    aggregated_scores = aggregate_juuni_unsei_thinking_tendency(
        pillar_juuni_unsei_data
    )

    with st.expander("集計結果", expanded=False):
        render_juuni_unsei_thinking_score_table(aggregated_scores)

    render_juuni_unsei_thinking_charts(aggregated_scores)


def format_datetime_for_display(value):
    if not value:
        return "未設定"
    return value.strftime("%Y-%m-%d %H:%M")


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
st.title("四柱推命 鑑定補助アプリ")
st.caption("開発中の鑑定補助アプリです")
st.write("生年月日などの基本情報から、鑑定の参考情報を表示します。")
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
    birth_time_display = f"{birth_hour}:{birth_minute}"
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
birth_info = build_birth_info(
    birth_date=birth_date,
    birth_time=birth_time_for_model,
    birth_place=birth_place_for_model,
    birth_country=birth_country_for_model,
    time_adjustment_enabled=False,
    time_adjustment_minutes=0,
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

calendar_context = get_calendar_context_for_birth_year(birth_date.year)
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
    st.table(pd.DataFrame(basic_info_rows))
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
    st.subheader("空亡")
    st.write(f"空亡：{display_kubou if display_kubou else '未入力'}")
    st.subheader("五行のバランス")
    render_gogyo_balance(gogyo_result, effective_day_tenkan)
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
            "pillar_key": "hour",
            "pillar_label": "時柱",
            "juuni_unsei": hour_juuni_unsei,
        },
        {
            "pillar_key": "day",
            "pillar_label": "日柱",
            "juuni_unsei": day_juuni_unsei,
        },
        {
            "pillar_key": "month",
            "pillar_label": "月柱",
            "juuni_unsei": month_juuni_unsei,
        },
        {
            "pillar_key": "year",
            "pillar_label": "年柱",
            "juuni_unsei": year_juuni_unsei,
        },
    ]
    pillar_juuni_unsei_data = {
        "hour": hour_juuni_unsei,
        "day": day_juuni_unsei,
        "month": month_juuni_unsei,
        "year": year_juuni_unsei,
    }
    comment_sections = [
        "特殊な命式",
        "日干から読み取れる性格",
        "通変星・蔵干通変星から読み取れる性格",
        "十二運星から読み取れる性格",
        "総合的に読み取れる性格",
        "十二運星から読み取れる考え方の傾向",
        "大運と接木運",
        "今年の運勢の流れ",
        "特定日時での運勢",
        "今年一年の総合運勢",
    ]
    for section_title in comment_sections:
        st.subheader(section_title)
        if section_title == "特殊な命式":
            render_special_meishiki(ijou_kanshi_data, gogyo_result)
        elif section_title == "日干から読み取れる性格":
            render_nikkan_public_comment(effective_day_tenkan)
        elif section_title == "通変星・蔵干通変星から読み取れる性格":
            render_public_tsuhensei_comments(life_stage_tsuhensei_data)
            render_public_month_pair_comment(month_zokkan_tsuhensei, month_tsuhensei)
        elif section_title == "十二運星から読み取れる性格":
            render_juuni_unsei_comments_for_mobile(
                juuni_unsei_display_data,
                "public",
            )
        elif section_title == "十二運星から読み取れる考え方の傾向":
            render_juuni_unsei_thinking_tendency_for_mobile(pillar_juuni_unsei_data)
        else:
            pass
    with st.expander("鑑定者用メモ", expanded=False):
        st.subheader("基本情報")
        st.table(pd.DataFrame(basic_info_rows))

        st.subheader("命式表")
        st.table(meishiki_data)

        st.subheader("空亡")
        st.write(f"空亡：{display_kubou if display_kubou else '未入力'}")

        st.subheader("五行のバランス")
        render_gogyo_balance(gogyo_result, effective_day_tenkan)

        for section_title in comment_sections:
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
            elif section_title == "十二運星から読み取れる考え方の傾向":
                render_juuni_unsei_thinking_tendency_for_mobile(
                    pillar_juuni_unsei_data,
                    is_private=True,
                )
            else:
                pass
