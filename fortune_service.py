from __future__ import annotations

from datetime import date, datetime, time as datetime_time

from calendar_logic import calculate_auto_meishiki
from calendar_reference import get_calendar_context_for_birth_year
from daiun_logic import build_daiun_table
from fortune_core_logic import (
    build_juuni_unsei_summary_data,
    build_thinking_chart_data,
    get_juuni_unsei,
    get_kubou,
    get_month_pair_comment,
    get_nikkan_comment,
    get_tsuhensei,
    get_tsuhensei_comment,
)
from gogyou_logic import calculate_gogyo_scores_from_meishiki, get_gogyo_chart_order
from meishiki_model import (
    build_analysis_context,
    build_birth_info,
    build_empty_meishiki,
    build_meishiki_from_manual_input,
    get_pillar_value,
    select_effective_meishiki,
)
from special_chart_logic import (
    SPECIAL_CHART_EMPTY_MESSAGE,
    build_ijou_kanshi_data_from_meishiki,
    build_special_meishiki_rows,
)
from specific_datetime_logic import build_specific_datetime_fortunes
from yearly_flow_logic import build_yearly_monthly_flow
from yearly_overall_logic import build_yearly_overall_fortune


UNKNOWN_BIRTH_TIME_CALCULATION_TIME = datetime_time(12, 0)

PREFECTURES = [
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

PILLAR_RESULT_ORDER = [
    ("hour", "時柱"),
    ("day", "日柱"),
    ("month", "月柱"),
    ("year", "年柱"),
]


def parse_date(value, default=None):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value.strip():
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    return default


def parse_time(value, default=None):
    if isinstance(value, datetime_time):
        return value
    if isinstance(value, str) and value.strip():
        return datetime.strptime(value.strip(), "%H:%M").time().replace(second=0, microsecond=0)
    return default


def format_japanese_date(value):
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return f"{value.year}年{value.month}月{value.day}日"
    return str(value or "")


def format_birth_time_for_client(value, birth_time_unknown=False):
    if birth_time_unknown or value is None:
        return "出生時刻不明"
    return f"{value.hour}時{value.minute:02d}分生まれ"


def format_adjusted_datetime(value):
    if not isinstance(value, datetime):
        return ""
    return f"{value.year}年{value.month}月{value.day}日 {value.hour:02d}:{value.minute:02d}"


def clear_hour_pillar_for_unknown_birth_time(meishiki):
    if not isinstance(meishiki, dict):
        return meishiki

    updated = {
        pillar_key: dict(pillar_value)
        for pillar_key, pillar_value in meishiki.items()
        if isinstance(pillar_value, dict)
    }
    updated.setdefault("hour", {})
    updated["hour"].update({
        "tenkan": "",
        "chishi": "",
        "zokkan": "",
    })
    return updated


def build_client_basic_info_rows(
    name,
    furigana,
    birth_date_value,
    birth_time_value,
    birth_time_unknown,
    birth_place,
    gender,
    consultation,
    reading_date,
):
    rows = []
    if str(name or "").strip():
        rows.append({"項目": "氏名", "内容": str(name).strip()})
    if str(furigana or "").strip():
        rows.append({"項目": "ふりがな", "内容": str(furigana).strip()})
    rows.append({"項目": "生年月日", "内容": format_japanese_date(birth_date_value)})
    rows.append({
        "項目": "出生時刻",
        "内容": format_birth_time_for_client(birth_time_value, birth_time_unknown),
    })
    if birth_place and birth_place != "未選択":
        rows.append({"項目": "出生地", "内容": birth_place})
    if gender and gender != "未選択":
        rows.append({"項目": "性別", "内容": gender})
    if str(consultation or "").strip():
        rows.append({"項目": "相談内容", "内容": str(consultation).strip()})
    rows.append({"項目": "鑑定日", "内容": format_japanese_date(reading_date)})
    return rows


def build_meishiki_table_data(meishiki, star_data):
    return [
        {
            "項目": "天干",
            "時柱": get_pillar_value(meishiki, "hour", "tenkan"),
            "日柱": get_pillar_value(meishiki, "day", "tenkan"),
            "月柱": get_pillar_value(meishiki, "month", "tenkan"),
            "年柱": get_pillar_value(meishiki, "year", "tenkan"),
        },
        {
            "項目": "地支",
            "時柱": get_pillar_value(meishiki, "hour", "chishi"),
            "日柱": get_pillar_value(meishiki, "day", "chishi"),
            "月柱": get_pillar_value(meishiki, "month", "chishi"),
            "年柱": get_pillar_value(meishiki, "year", "chishi"),
        },
        {
            "項目": "蔵干",
            "時柱": get_pillar_value(meishiki, "hour", "zokkan"),
            "日柱": get_pillar_value(meishiki, "day", "zokkan"),
            "月柱": get_pillar_value(meishiki, "month", "zokkan"),
            "年柱": get_pillar_value(meishiki, "year", "zokkan"),
        },
        {
            "項目": "通変星",
            "時柱": star_data["hour_tsuhensei"],
            "日柱": "－",
            "月柱": star_data["month_tsuhensei"],
            "年柱": star_data["year_tsuhensei"],
        },
        {
            "項目": "蔵干通変星",
            "時柱": star_data["hour_zokkan_tsuhensei"],
            "日柱": star_data["day_zokkan_tsuhensei"],
            "月柱": star_data["month_zokkan_tsuhensei"],
            "年柱": star_data["year_zokkan_tsuhensei"],
        },
        {
            "項目": "十二運星",
            "時柱": star_data["hour_juuni_unsei"] or "未入力",
            "日柱": star_data["day_juuni_unsei"] or "未入力",
            "月柱": star_data["month_juuni_unsei"] or "未入力",
            "年柱": star_data["year_juuni_unsei"] or "未入力",
        },
    ]


def build_life_stage_tsuhensei_data(star_data):
    return [
        {"stage": "0〜4歳", "outer": "－", "inner": star_data["day_zokkan_tsuhensei"]},
        {"stage": "5〜29歳", "outer": star_data["year_tsuhensei"], "inner": star_data["year_zokkan_tsuhensei"]},
        {"stage": "30〜64歳", "outer": star_data["month_tsuhensei"], "inner": star_data["month_zokkan_tsuhensei"]},
        {"stage": "65歳以降", "outer": star_data["hour_tsuhensei"], "inner": star_data["hour_zokkan_tsuhensei"]},
    ]


def build_life_stage_comments(life_stage_data):
    rows = []
    for row in life_stage_data:
        rows.append({
            **row,
            "outer_comment": get_tsuhensei_comment(row.get("outer", ""), "public"),
            "inner_comment": get_tsuhensei_comment(row.get("inner", ""), "public"),
            "outer_private_comment": get_tsuhensei_comment(row.get("outer", ""), "private"),
            "inner_private_comment": get_tsuhensei_comment(row.get("inner", ""), "private"),
        })
    return rows


def build_juuni_unsei_display_data(star_data):
    return [
        {
            "pillar_key": "year",
            "pillar_label": "年柱",
            "personality_heading": "意思決定の時の自分",
            "juuni_unsei": star_data["year_juuni_unsei"],
        },
        {
            "pillar_key": "month",
            "pillar_label": "月柱",
            "personality_heading": "初対面の人と会った時の自分",
            "juuni_unsei": star_data["month_juuni_unsei"],
        },
        {
            "pillar_key": "day",
            "pillar_label": "日柱",
            "personality_heading": "一人の時の自分",
            "juuni_unsei": star_data["day_juuni_unsei"],
        },
        {
            "pillar_key": "hour",
            "pillar_label": "時柱",
            "personality_heading": "どんな老後を過ごしたいか",
            "juuni_unsei": star_data["hour_juuni_unsei"],
        },
    ]


def build_star_data(meishiki):
    day_tenkan = get_pillar_value(meishiki, "day", "tenkan")
    values = {
        "hour_tenkan": get_pillar_value(meishiki, "hour", "tenkan"),
        "day_tenkan": day_tenkan,
        "month_tenkan": get_pillar_value(meishiki, "month", "tenkan"),
        "year_tenkan": get_pillar_value(meishiki, "year", "tenkan"),
        "hour_chishi": get_pillar_value(meishiki, "hour", "chishi"),
        "day_chishi": get_pillar_value(meishiki, "day", "chishi"),
        "month_chishi": get_pillar_value(meishiki, "month", "chishi"),
        "year_chishi": get_pillar_value(meishiki, "year", "chishi"),
        "hour_zokkan": get_pillar_value(meishiki, "hour", "zokkan"),
        "day_zokkan": get_pillar_value(meishiki, "day", "zokkan"),
        "month_zokkan": get_pillar_value(meishiki, "month", "zokkan"),
        "year_zokkan": get_pillar_value(meishiki, "year", "zokkan"),
    }
    values.update({
        "hour_tsuhensei": get_tsuhensei(day_tenkan, values["hour_tenkan"]),
        "month_tsuhensei": get_tsuhensei(day_tenkan, values["month_tenkan"]),
        "year_tsuhensei": get_tsuhensei(day_tenkan, values["year_tenkan"]),
        "hour_zokkan_tsuhensei": get_tsuhensei(day_tenkan, values["hour_zokkan"]),
        "day_zokkan_tsuhensei": get_tsuhensei(day_tenkan, values["day_zokkan"]),
        "month_zokkan_tsuhensei": get_tsuhensei(day_tenkan, values["month_zokkan"]),
        "year_zokkan_tsuhensei": get_tsuhensei(day_tenkan, values["year_zokkan"]),
        "hour_juuni_unsei": get_juuni_unsei(day_tenkan, values["hour_chishi"]),
        "day_juuni_unsei": get_juuni_unsei(day_tenkan, values["day_chishi"]),
        "month_juuni_unsei": get_juuni_unsei(day_tenkan, values["month_chishi"]),
        "year_juuni_unsei": get_juuni_unsei(day_tenkan, values["year_chishi"]),
    })
    return values


def normalize_specific_candidates(payload_candidates):
    candidates = []
    for item in payload_candidates or []:
        target_date = parse_date(item.get("date"))
        target_time = parse_time(item.get("time"), datetime_time(0, 0))
        if target_date is None:
            continue
        candidates.append({"date": target_date, "time": target_time})
    return candidates


def calculate_fortune(payload):
    today = date.today()
    birth_date = parse_date(payload.get("birthDate"), date(1988, 8, 12))
    reading_date = parse_date(payload.get("readingDate"), today)
    birth_time_unknown = bool(payload.get("birthTimeUnknown"))
    birth_time_value = None if birth_time_unknown else parse_time(payload.get("birthTime"), datetime_time(0, 0))
    birth_time_for_calculation = (
        UNKNOWN_BIRTH_TIME_CALCULATION_TIME
        if birth_time_unknown
        else birth_time_value
    )
    birth_place = payload.get("birthPlace") or ""
    birth_place_for_model = "" if birth_place == "未選択" else birth_place
    birth_place_for_calculation = None if birth_time_unknown else (birth_place_for_model or None)
    birth_country = payload.get("birthCountry") or "日本"

    birth_info = build_birth_info(
        birth_date=birth_date,
        birth_time=birth_time_for_calculation,
        birth_place=birth_place_for_calculation,
        birth_country=birth_country,
        time_adjustment_enabled=False,
        time_adjustment_minutes=0,
    )
    birth_info["birth_time_unknown"] = birth_time_unknown
    birth_info["display_birth_place"] = birth_place_for_model

    adjusted_birth_datetime = birth_info.get("adjusted_birth_datetime")
    calculation_birth_date = (
        adjusted_birth_datetime.date()
        if adjusted_birth_datetime is not None
        else birth_date
    )
    calendar_context = get_calendar_context_for_birth_year(calculation_birth_date.year)
    auto_calculation_errors = []
    effective_meishiki = build_empty_meishiki()
    source_label = "自動計算命式"

    if not calendar_context.get("ok"):
        auto_calculation_errors.extend(calendar_context.get("errors", []))
    else:
        try:
            auto_meishiki = calculate_auto_meishiki(
                birth_info,
                risshun_datetime=calendar_context["risshun_datetime"],
                sekki_entries=calendar_context["sekki_entries"],
                base_date=calendar_context["base_date"],
                base_day_kanchi=calendar_context["base_day_kanchi"],
            )
            selected = select_effective_meishiki(
                input_mode="auto",
                manual_meishiki=build_empty_meishiki(),
                auto_meishiki=auto_meishiki,
            )
            source_label = selected.get("source_label", source_label)
            if selected.get("ok"):
                effective_meishiki = selected["meishiki"]
            else:
                auto_calculation_errors.extend(selected.get("errors", []))
        except Exception as exc:
            auto_calculation_errors.append(str(exc))

    if birth_time_unknown:
        effective_meishiki = clear_hour_pillar_for_unknown_birth_time(effective_meishiki)

    if auto_calculation_errors:
        return to_jsonable({
            "ok": False,
            "errors": auto_calculation_errors,
            "input": payload,
            "calendar": {
                "label": calendar_context.get("label", ""),
                "warnings": calendar_context.get("warnings", []),
            },
        })

    star_data = build_star_data(effective_meishiki)
    display_kubou = get_kubou(star_data["day_tenkan"], star_data["day_chishi"])
    analysis_context = build_analysis_context(reading_date)
    gogyo_result = calculate_gogyo_scores_from_meishiki(effective_meishiki, analysis_context)
    ijou_kanshi_data = build_ijou_kanshi_data_from_meishiki(effective_meishiki)
    special_rows = build_special_meishiki_rows(ijou_kanshi_data, gogyo_result)
    month_kanchi = ""
    if star_data["month_tenkan"] and star_data["month_chishi"]:
        month_kanchi = f"{star_data['month_tenkan']}{star_data['month_chishi']}"

    daiun_result = build_daiun_table(
        birth_date=calculation_birth_date,
        birth_year=calculation_birth_date.year if calculation_birth_date else None,
        gender=payload.get("gender", "未選択"),
        year_tenkan=star_data["year_tenkan"],
        month_kanchi=month_kanchi,
        day_tenkan=star_data["day_tenkan"],
        sekki_entries=calendar_context.get("sekki_entries", []),
    )
    yearly_flow_result = build_yearly_monthly_flow(
        reading_date=reading_date,
        day_tenkan=star_data["day_tenkan"],
        kubou=display_kubou,
    )
    yearly_overall_result = build_yearly_overall_fortune(
        reading_date=reading_date,
        day_tenkan=star_data["day_tenkan"],
    )
    specific_datetime_enabled = bool(payload.get("specificDatetimeEnabled"))
    specific_candidates = normalize_specific_candidates(payload.get("specificDatetimeCandidates", []))
    specific_datetime_result = (
        build_specific_datetime_fortunes(specific_candidates, star_data["day_tenkan"])
        if specific_datetime_enabled
        else {"ok": True, "rows": [], "errors": []}
    )

    life_stage_data = build_life_stage_tsuhensei_data(star_data)
    juuni_unsei_display_data = build_juuni_unsei_display_data(star_data)
    juuni_unsei_by_pillar = {
        data["pillar_key"]: data.get("juuni_unsei", "")
        for data in juuni_unsei_display_data
    }
    nikkan_comment = get_nikkan_comment(star_data["day_tenkan"])

    return to_jsonable({
        "ok": True,
        "source_label": source_label,
        "basic_info": build_client_basic_info_rows(
            payload.get("name", ""),
            payload.get("furigana", ""),
            birth_date,
            birth_time_value,
            birth_time_unknown,
            birth_place,
            payload.get("gender", "未選択"),
            payload.get("consultation", ""),
            reading_date,
        ),
        "birth_adjustment": {
            "raw_birth_datetime": format_adjusted_datetime(birth_info.get("raw_birth_datetime")),
            "adjusted_birth_datetime": format_adjusted_datetime(birth_info.get("adjusted_birth_datetime")),
            "time_adjustment_enabled": birth_info.get("time_adjustment_enabled", False),
            "time_adjustment_minutes": birth_info.get("time_adjustment_minutes", 0),
            "birthplace_longitude": birth_info.get("birthplace_longitude"),
            "reason": birth_info.get("time_adjustment_reason", ""),
        },
        "calendar": {
            "label": calendar_context.get("label", ""),
            "warnings": calendar_context.get("warnings", []),
        },
        "meishiki": effective_meishiki,
        "meishiki_table": build_meishiki_table_data(effective_meishiki, star_data),
        "star_data": star_data,
        "kubou": display_kubou,
        "gogyo": {
            **gogyo_result,
            "chart_order": get_gogyo_chart_order(star_data["day_tenkan"]),
        },
        "special_meishiki": {
            "rows": special_rows,
            "empty_message": "" if special_rows else SPECIAL_CHART_EMPTY_MESSAGE,
        },
        "personality": {
            "nikkan": {
                "tenkan": star_data["day_tenkan"],
                "description": nikkan_comment.get("description", ""),
                "keywords": nikkan_comment.get("keywords", ""),
            },
            "life_stage_tsuhensei": build_life_stage_comments(life_stage_data),
            "month_pair": {
                "center_star": star_data["month_zokkan_tsuhensei"],
                "tsuhensei": star_data["month_tsuhensei"],
                "public_comment": get_month_pair_comment(
                    star_data["month_zokkan_tsuhensei"],
                    star_data["month_tsuhensei"],
                    "public",
                ),
                "private_comment": get_month_pair_comment(
                    star_data["month_zokkan_tsuhensei"],
                    star_data["month_tsuhensei"],
                    "private",
                ),
            },
            "juuni_unsei": {
                "rows": build_juuni_unsei_summary_data(juuni_unsei_display_data),
                "thinking": build_thinking_chart_data(juuni_unsei_by_pillar),
            },
        },
        "daiun": daiun_result,
        "yearly_flow": yearly_flow_result,
        "yearly_overall": yearly_overall_result,
        "specific_datetime": specific_datetime_result,
    })


def to_jsonable(value):
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, datetime_time):
        return value.strftime("%H:%M")
    return value
