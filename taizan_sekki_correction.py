from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache

from sekki_data import TARGET_SEKKI_TERMS


try:
    from eacal import EACal
except ImportError:  # pragma: no cover - exercised through application setup.
    EACal = None


NORMAL_BOUNDARY_WINDOW = timedelta(minutes=3)
FIXED_JST = timezone(timedelta(hours=9), name="JST")

NORMAL_BOUNDARY_WARNING_CODE = "TAIZAN_SEKKI_BOUNDARY_NEAR"

NORMAL_BOUNDARY_WARNING_MESSAGE = (
    "節入り時刻に非常に近いため、流派資料によって月柱・年柱が変わる可能性があります。"
    "必要に応じて原資料で確認してください。"
)


def round_eacal_datetime_to_minute(value: datetime) -> datetime:
    """EACALの節入り時刻を、秒30以上で繰り上げる分単位へ丸める。"""
    if not isinstance(value, datetime):
        raise TypeError("value must be a datetime.")

    rounded = value.replace(second=0, microsecond=0)
    elapsed_in_minute = timedelta(seconds=value.second, microseconds=value.microsecond)
    if elapsed_in_minute >= timedelta(seconds=30):
        rounded += timedelta(minutes=1)
    return rounded


def convert_eacal_datetime_to_fixed_jst(value: datetime) -> datetime:
    """EACALのaware datetimeを、常時UTC+09:00の固定JSTへ実変換する。"""
    if not isinstance(value, datetime):
        raise TypeError("value must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("EACAL datetime must be timezone-aware.")
    return value.astimezone(FIXED_JST)


def correct_eacal_datetime_for_taizan(value: datetime) -> datetime:
    """固定JSTへ実変換したEACAL時刻を、泰山流の分境界へ丸める。"""
    fixed_jst_datetime = convert_eacal_datetime_to_fixed_jst(value)
    return round_eacal_datetime_to_minute(fixed_jst_datetime)


def _to_legacy_naive_datetime(value: datetime) -> datetime:
    """固定JSTの時計表示を維持し、既存アプリ比較用のnaive datetimeへ変換する。"""
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


@lru_cache(maxsize=None)
def _build_corrected_entries(year: int) -> tuple[dict, ...]:
    """指定年の十二節をEACALから取得し、既存アプリ形式の境界へ整形する。"""
    if EACal is None:
        raise RuntimeError(
            "eacal が利用できません。requirements.txt の固定依存関係をインストールしてください。"
        )

    eacal_terms = {
        term_name: term_datetime
        for term_name, _term_id, term_datetime in EACal(ja=True).get_annual_solar_terms(year)
    }
    entries = []
    for term_name, _longitude, _month, _day, month_branch in TARGET_SEKKI_TERMS:
        original_eacal_datetime = eacal_terms.get(term_name)
        if original_eacal_datetime is None:
            raise RuntimeError(f"{year}年のEACAL節気データに{term_name}がありません。")

        corrected_eacal_datetime = correct_eacal_datetime_for_taizan(original_eacal_datetime)
        corrected_sekki_datetime = _to_legacy_naive_datetime(corrected_eacal_datetime)
        entries.append(
            {
                "year": int(year),
                "name": term_name,
                "datetime": corrected_sekki_datetime,
                "corrected_sekki_datetime": corrected_sekki_datetime,
                "original_eacal_datetime": original_eacal_datetime,
                "corrected_eacal_datetime": corrected_eacal_datetime,
                "month_branch": month_branch,
                "source": "EACAL基準・固定JST変換・泰山流分四捨五入",
                "note": "EACAL aware時刻を固定JSTへ実変換後、秒30以上で分繰り上げし、naive境界へ渡す。",
            }
        )
    return tuple(entries)


def get_corrected_taizan_sekki_entries_by_year(year: int) -> list[dict]:
    """年柱・月柱判定に使う、分四捨五入済みの十二節を返す。"""
    return [entry.copy() for entry in _build_corrected_entries(int(year))]


def get_corrected_taizan_sekki_entries_around_year(year: int) -> list[dict]:
    """年初・年末の月柱判定用に前年・当年・翌年の十二節を返す。"""
    entries = []
    for target_year in (int(year) - 1, int(year), int(year) + 1):
        entries.extend(get_corrected_taizan_sekki_entries_by_year(target_year))
    return sorted(entries, key=lambda entry: entry["datetime"])


def get_corrected_risshun_datetime(year: int) -> datetime | None:
    """分四捨五入済みの立春境界を返す。"""
    for entry in get_corrected_taizan_sekki_entries_by_year(year):
        if entry["name"] == "立春":
            return entry["datetime"]
    return None


def _difference_seconds(target_datetime: datetime, boundary_datetime: datetime) -> float:
    """既存アプリのnaive入力とEACAL aware値を安全に比較する。"""
    if target_datetime.tzinfo is None and boundary_datetime.tzinfo is not None:
        boundary_datetime = _to_legacy_naive_datetime(boundary_datetime)
    elif target_datetime.tzinfo is not None and boundary_datetime.tzinfo is None:
        target_datetime = _to_legacy_naive_datetime(target_datetime)
    return (target_datetime - boundary_datetime).total_seconds()


def get_taizan_sekki_boundary_warnings(
    target_datetime: datetime,
    sekki_entries: list[dict],
) -> list[dict]:
    """固定JST補正後境界の前後3分以内に通常警告を返す。"""
    if not isinstance(target_datetime, datetime):
        raise TypeError("target_datetime must be a datetime.")

    warnings = []
    for entry in sekki_entries or []:
        if not isinstance(entry, dict):
            continue

        corrected_datetime = entry.get("corrected_sekki_datetime") or entry.get("datetime")
        if not isinstance(corrected_datetime, datetime):
            continue

        corrected_difference_seconds = _difference_seconds(target_datetime, corrected_datetime)
        if abs(corrected_difference_seconds) <= NORMAL_BOUNDARY_WINDOW.total_seconds():
            warnings.append(
                {
                    "code": NORMAL_BOUNDARY_WARNING_CODE,
                    "level": "warning",
                    "message": NORMAL_BOUNDARY_WARNING_MESSAGE,
                    "term_name": entry.get("name"),
                    "boundary_datetime": corrected_datetime,
                    "difference_seconds": corrected_difference_seconds,
                    "comparison_basis": "corrected_sekki_datetime",
                }
            )

    return warnings
