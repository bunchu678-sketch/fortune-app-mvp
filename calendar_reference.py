from __future__ import annotations

from datetime import date, datetime

from sekki_data import (
    get_supported_birth_year_range,
    is_supported_birth_year,
)
from taizan_sekki_correction import (
    get_corrected_risshun_datetime,
    get_corrected_taizan_sekki_entries_around_year,
    get_corrected_taizan_sekki_entries_by_year,
)


__all__ = [
    "get_calendar_context_for_birth_year",
    "get_development_calendar_context",
    "get_development_calendar_warnings",
    "get_supported_birth_year_message",
]


DEVELOPMENT_SEKKI_YEAR = 2020
DEVELOPMENT_RISSHUN_DATETIME = datetime(2020, 2, 4, 18, 3)
DEVELOPMENT_BASE_DATE = date(2020, 2, 4)
# 既存の命式計算で使用している日柱基準干支。
DEVELOPMENT_BASE_DAY_KANCHI = "丁丑"


def get_development_calendar_warnings() -> list:
    """
    正常な鑑定結果へ共通警告は付与しない。

    節入り境界付近の注意は、別の boundary_warnings として返す。
    """
    return []


def get_development_calendar_context() -> dict:
    """
    自動命式計算の開発用カレンダー設定を返す。
    """
    sekki_entries = get_corrected_taizan_sekki_entries_by_year(DEVELOPMENT_SEKKI_YEAR)
    return {
        "ok": True,
        "label": "開発用カレンダー設定",
        "risshun_datetime": get_corrected_risshun_datetime(DEVELOPMENT_SEKKI_YEAR),
        "sekki_entries": sekki_entries,
        "sekki_year": DEVELOPMENT_SEKKI_YEAR,
        "base_date": DEVELOPMENT_BASE_DATE,
        "base_day_kanchi": DEVELOPMENT_BASE_DAY_KANCHI,
        "warnings": get_development_calendar_warnings(),
    }


def get_supported_birth_year_message() -> str:
    start_year, end_year = get_supported_birth_year_range()
    return f"自動命式計算は現在{start_year}年〜{end_year}年の生年月日に対応しています。"


def get_calendar_context_for_birth_year(birth_year: int) -> dict:
    """
    入力生年に応じた自動命式計算用カレンダー設定を返す。

    月柱判定では年初・年末境界に隣接年の節入りが必要になるため、
    birth_year-1, birth_year, birth_year+1 の十二節を結合して渡す。
    """
    year = int(birth_year)
    if not is_supported_birth_year(year):
        return {
            "ok": False,
            "label": "対応範囲外",
            "risshun_datetime": None,
            "sekki_entries": [],
            "sekki_year": year,
            "base_date": DEVELOPMENT_BASE_DATE,
            "base_day_kanchi": DEVELOPMENT_BASE_DAY_KANCHI,
            "warnings": [],
            "errors": [get_supported_birth_year_message()],
        }

    try:
        risshun_datetime = get_corrected_risshun_datetime(year)
        sekki_entries = get_corrected_taizan_sekki_entries_around_year(year)
    except RuntimeError as error:
        return {
            "ok": False,
            "label": f"{year}年生年月日用カレンダー設定",
            "risshun_datetime": None,
            "sekki_entries": [],
            "sekki_year": year,
            "base_date": DEVELOPMENT_BASE_DATE,
            "base_day_kanchi": DEVELOPMENT_BASE_DAY_KANCHI,
            "warnings": get_development_calendar_warnings(),
            "errors": [str(error)],
        }
    errors = []
    if risshun_datetime is None:
        errors.append(f"{year}年の立春データを取得できません。")
    if not sekki_entries:
        errors.append(f"{year}年前後の節入りデータを取得できません。")

    return {
        "ok": not errors,
        "label": f"{year}年生年月日用カレンダー設定",
        "risshun_datetime": risshun_datetime,
        "sekki_entries": sekki_entries,
        "sekki_year": year,
        "base_date": DEVELOPMENT_BASE_DATE,
        "base_day_kanchi": DEVELOPMENT_BASE_DAY_KANCHI,
        "warnings": get_development_calendar_warnings(),
        "errors": errors,
    }
