from datetime import date, datetime

from sekki_data import (
    get_risshun_datetime_by_year,
    get_sekki_entries_around_year,
    get_sekki_entries_by_year,
    get_supported_birth_year_range,
    is_supported_birth_year,
)


DEVELOPMENT_SEKKI_YEAR = 2020
DEVELOPMENT_RISSHUN_DATETIME = datetime(2020, 2, 4, 18, 3)
DEVELOPMENT_BASE_DATE = date(2020, 2, 4)
# 泰山流参照ケース6件で検証した開発用設定。
# まだ正式本番化ではなく、他年・他流派の検証は今後必要。
DEVELOPMENT_BASE_DAY_KANCHI = "丁丑"


def get_development_calendar_warnings() -> list:
    """
    開発用カレンダー設定に関する警告文を返す。
    """
    return [
        "現在の節入り日時データは検証用です。",
        "現在の日柱基準干支は泰山流参照ケース6件で検証した開発用設定です。",
        "他年・他流派の検証は今後必要です。",
        "本番鑑定としてはまだ使用しないでください。",
    ]


def get_development_calendar_context() -> dict:
    """
    自動命式計算の開発・検証用カレンダー設定を返す。

    注意:
    これは本番用の正確な暦設定ではない。
    節入り日時、日柱基準日、日柱基準干支は検証用である。
    将来的には、国立天文台ベースの節入り日時、正確な日柱基準日、
    泰山流万年暦との照合結果に差し替える。
    """
    return {
        "ok": True,
        "label": "開発用・検証用カレンダー設定",
        "risshun_datetime": DEVELOPMENT_RISSHUN_DATETIME,
        "sekki_entries": get_sekki_entries_by_year(DEVELOPMENT_SEKKI_YEAR),
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

    risshun_datetime = get_risshun_datetime_by_year(year)
    sekki_entries = get_sekki_entries_around_year(year)
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
