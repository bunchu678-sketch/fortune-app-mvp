from datetime import datetime, time as datetime_time

from fortune_data import CHISHI_ORDER, TENKAN_ORDER, get_simple_zokkan_by_chishi
from time_adjustment_logic import apply_time_adjustment

PILLAR_KEYS = ["year", "month", "day", "hour"]
PILLAR_DISPLAY_ORDER = ["hour", "day", "month", "year"]
PILLAR_LABELS = {
    "year": "年柱",
    "month": "月柱",
    "day": "日柱",
    "hour": "時柱",
}
KANSHI_TENKAN_ORDER = TENKAN_ORDER
KANSHI_CHISHI_ORDER = CHISHI_ORDER
MEISHIKI_SOURCE_MANUAL = "manual"
MEISHIKI_SOURCE_AUTO = "auto"
AUTO_CALCULATION_STATUS_NOT_IMPLEMENTED = "not_implemented"
AUTO_MEISHIKI_DEVELOPMENT_WARNING = (
    "自動計算命式は開発用です。節入り日時、日柱基準日、蔵干は検証中です。"
)


def build_kanshi(tenkan, chishi):
    if not tenkan or not chishi:
        return ""
    return f"{tenkan}{chishi}"


def build_meishiki_from_manual_input(
    year_tenkan, month_tenkan, day_tenkan, hour_tenkan,
    year_chishi, month_chishi, day_chishi, hour_chishi,
    year_zokkan="", month_zokkan="", day_zokkan="", hour_zokkan="",
):
    return {
        "year": {
            "tenkan": year_tenkan,
            "chishi": year_chishi,
            "zokkan": year_zokkan,
        },
        "month": {
            "tenkan": month_tenkan,
            "chishi": month_chishi,
            "zokkan": month_zokkan,
        },
        "day": {
            "tenkan": day_tenkan,
            "chishi": day_chishi,
            "zokkan": day_zokkan,
        },
        "hour": {
            "tenkan": hour_tenkan,
            "chishi": hour_chishi,
            "zokkan": hour_zokkan,
        },
    }


def build_empty_meishiki():
    return build_meishiki_from_manual_input(
        "", "", "", "",
        "", "", "", "",
        "", "", "", "",
    )


def build_manual_meishiki_record(meishiki):
    return {
        "source": MEISHIKI_SOURCE_MANUAL,
        "meishiki": meishiki,
        "birth_info": None,
        "calculation_status": "manual_input",
    }


def build_auto_meishiki_record(
    birth_info,
    meishiki=None,
    calculation_status=AUTO_CALCULATION_STATUS_NOT_IMPLEMENTED,
):
    return {
        "source": MEISHIKI_SOURCE_AUTO,
        "meishiki": meishiki or build_empty_meishiki(),
        "birth_info": birth_info,
        "calculation_status": calculation_status,
    }


def auto_meishiki_to_manual_format(auto_meishiki: dict) -> dict:
    """
    自動計算された命式を、既存の手入力命式と同じ形式に変換する。
    既存鑑定ロジックに渡しやすくするための関数。
    """
    manual_meishiki = {}

    for pillar_key in PILLAR_KEYS:
        pillar = auto_meishiki.get(pillar_key, {})
        chishi = pillar.get("chishi", "")
        zokkan = pillar.get("zokkan")
        if not zokkan:
            zokkan = get_simple_zokkan_by_chishi(chishi)
        manual_meishiki[pillar_key] = {
            "tenkan": pillar.get("tenkan", ""),
            "chishi": chishi,
            "zokkan": zokkan,
        }

    return manual_meishiki


def validate_meishiki_minimum(meishiki: dict) -> dict:
    """
    meishiki に year/month/day/hour と tenkan/chishi があるか確認する。
    """
    errors = []

    if not isinstance(meishiki, dict):
        return {
            "ok": False,
            "errors": ["meishiki は dict である必要があります。"],
        }

    for pillar_key in PILLAR_KEYS:
        pillar = meishiki.get(pillar_key)
        if not isinstance(pillar, dict):
            errors.append(f"meishiki.{pillar_key} がありません。")
            continue

        for value_key in ("tenkan", "chishi"):
            if value_key not in pillar:
                errors.append(f"meishiki.{pillar_key}.{value_key} がありません。")
            elif pillar.get(value_key) is None:
                errors.append(f"meishiki.{pillar_key}.{value_key} が None です。")

    return {
        "ok": not errors,
        "errors": errors,
    }


def _looks_like_auto_calculation_result(meishiki: dict) -> bool:
    if not isinstance(meishiki, dict):
        return False

    for pillar_key in PILLAR_KEYS:
        pillar = meishiki.get(pillar_key)
        if isinstance(pillar, dict) and (
            "kanchi" in pillar or "detail" in pillar
        ):
            return True

    return False


def is_manual_meishiki_format(meishiki: dict) -> bool:
    """
    year/month/day/hour と tenkan/chishi を持つ既存meishiki形式か判定する。
    """
    if _looks_like_auto_calculation_result(meishiki):
        return False

    return validate_meishiki_minimum(meishiki)["ok"]


def _build_effective_meishiki_result(
    ok: bool,
    input_mode: str,
    source_label: str,
    meishiki=None,
    warnings=None,
    errors=None,
) -> dict:
    return {
        "ok": ok,
        "input_mode": input_mode,
        "source_label": source_label,
        "meishiki": meishiki,
        "warnings": warnings or [],
        "errors": errors or [],
    }


def select_effective_meishiki(
    input_mode: str,
    manual_meishiki: dict = None,
    auto_meishiki: dict = None,
) -> dict:
    """
    手入力命式と自動命式のどちらを有効な meishiki として使うか選択する。

    input_mode は "manual" または "auto" を指定する。
    戻り値は ok/errors を含む dict にし、エラー時も例外で落とさない。
    """
    normalized_mode = input_mode.strip().lower() if isinstance(input_mode, str) else input_mode

    if normalized_mode == MEISHIKI_SOURCE_MANUAL:
        if manual_meishiki is None:
            return _build_effective_meishiki_result(
                ok=False,
                input_mode=normalized_mode,
                source_label="手入力命式",
                errors=["manual_meishiki がありません。"],
            )

        validation = validate_meishiki_minimum(manual_meishiki)
        if not validation["ok"]:
            return _build_effective_meishiki_result(
                ok=False,
                input_mode=normalized_mode,
                source_label="手入力命式",
                errors=validation["errors"],
            )

        return _build_effective_meishiki_result(
            ok=True,
            input_mode=normalized_mode,
            source_label="手入力命式",
            meishiki=manual_meishiki,
        )

    if normalized_mode == MEISHIKI_SOURCE_AUTO:
        if auto_meishiki is None:
            return _build_effective_meishiki_result(
                ok=False,
                input_mode=normalized_mode,
                source_label="自動計算命式（開発用）",
                errors=["auto_meishiki がありません。"],
            )

        if not isinstance(auto_meishiki, dict):
            return _build_effective_meishiki_result(
                ok=False,
                input_mode=normalized_mode,
                source_label="自動計算命式（開発用）",
                warnings=[AUTO_MEISHIKI_DEVELOPMENT_WARNING],
                errors=["auto_meishiki は dict である必要があります。"],
            )

        if auto_meishiki.get("error"):
            return _build_effective_meishiki_result(
                ok=False,
                input_mode=normalized_mode,
                source_label="自動計算命式（開発用）",
                warnings=[AUTO_MEISHIKI_DEVELOPMENT_WARNING],
                errors=[f"auto_meishiki.error: {auto_meishiki['error']}"],
            )

        if is_manual_meishiki_format(auto_meishiki):
            selected_meishiki = auto_meishiki
        elif _looks_like_auto_calculation_result(auto_meishiki):
            try:
                selected_meishiki = auto_meishiki_to_manual_format(auto_meishiki)
            except Exception as exc:
                return _build_effective_meishiki_result(
                    ok=False,
                    input_mode=normalized_mode,
                    source_label="自動計算命式（開発用）",
                    warnings=[AUTO_MEISHIKI_DEVELOPMENT_WARNING],
                    errors=[f"auto_meishiki の変換に失敗しました: {exc}"],
                )
        else:
            return _build_effective_meishiki_result(
                ok=False,
                input_mode=normalized_mode,
                source_label="自動計算命式（開発用）",
                warnings=[AUTO_MEISHIKI_DEVELOPMENT_WARNING],
                errors=["auto_meishiki の形式を判定できません。"],
            )

        validation = validate_meishiki_minimum(selected_meishiki)
        if not validation["ok"]:
            return _build_effective_meishiki_result(
                ok=False,
                input_mode=normalized_mode,
                source_label="自動計算命式（開発用）",
                meishiki=selected_meishiki,
                warnings=[AUTO_MEISHIKI_DEVELOPMENT_WARNING],
                errors=validation["errors"],
            )

        return _build_effective_meishiki_result(
            ok=True,
            input_mode=normalized_mode,
            source_label="自動計算命式（開発用）",
            meishiki=selected_meishiki,
            warnings=[AUTO_MEISHIKI_DEVELOPMENT_WARNING],
        )

    return _build_effective_meishiki_result(
        ok=False,
        input_mode=normalized_mode,
        source_label="",
        errors=["input_mode は 'manual' または 'auto' を指定してください。"],
    )


def normalize_birth_time(birth_time):
    if birth_time is None:
        return None

    if isinstance(birth_time, datetime_time):
        return birth_time

    if isinstance(birth_time, str):
        hour_text, minute_text = birth_time.split(":", 1)
        return datetime_time(int(hour_text), int(minute_text))

    if isinstance(birth_time, (tuple, list)) and len(birth_time) >= 2:
        return datetime_time(int(birth_time[0]), int(birth_time[1]))

    raise TypeError("birth_time must be time, 'HH:MM', tuple/list, or None.")


def build_raw_birth_datetime(birth_date, birth_time):
    if birth_date is None:
        return None

    if isinstance(birth_date, datetime):
        if birth_time is None:
            return birth_date.replace(second=0, microsecond=0)
        birth_date = birth_date.date()

    normalized_birth_time = normalize_birth_time(birth_time)
    if normalized_birth_time is None:
        return None

    return datetime.combine(birth_date, normalized_birth_time).replace(
        second=0,
        microsecond=0,
    )


def build_birth_info(
    birth_date,
    birth_time,
    birth_place=None,
    birth_country="日本",
    time_adjustment_enabled=False,
    time_adjustment_minutes=0,
):
    raw_birth_datetime = build_raw_birth_datetime(birth_date, birth_time)
    adjustment_minutes = int(time_adjustment_minutes or 0)
    applied_adjustment_minutes = (
        adjustment_minutes if time_adjustment_enabled else 0
    )
    adjusted_birth_datetime = apply_time_adjustment(
        raw_birth_datetime,
        applied_adjustment_minutes,
    )

    return {
        "raw_birth_datetime": raw_birth_datetime,
        "birth_place": birth_place or "",
        "birth_country": birth_country if birth_country is not None else "日本",
        "time_adjustment_enabled": bool(time_adjustment_enabled),
        "time_adjustment_minutes": applied_adjustment_minutes,
        "adjusted_birth_datetime": adjusted_birth_datetime,
    }


def get_pillar_value(meishiki, pillar_key, value_key, default=""):
    return meishiki.get(pillar_key, {}).get(value_key, default)


def get_formula_chishi(meishiki):
    return [
        get_pillar_value(meishiki, pillar_key, "chishi")
        for pillar_key in PILLAR_KEYS
        if get_pillar_value(meishiki, pillar_key, "chishi")
    ]


def get_kantei_year_kanshi(target_date):
    if not target_date:
        return "", ""

    year = target_date.year
    cycle_index = (year - 1984) % 60
    return (
        KANSHI_TENKAN_ORDER[cycle_index % 10],
        KANSHI_CHISHI_ORDER[cycle_index % 12],
    )


def build_analysis_context(target_date):
    target_year_tenkan, target_year_chishi = get_kantei_year_kanshi(target_date)
    return {
        "target_year": target_date.year if target_date else "",
        "target_year_tenkan": target_year_tenkan,
        "target_year_chishi": target_year_chishi,
    }
