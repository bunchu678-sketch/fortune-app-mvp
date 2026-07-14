from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache

from sekki_data import TARGET_SEKKI_TERMS


try:
    from eacal import EACal
except ImportError:  # pragma: no cover - exercised through application setup.
    EACal = None


NORMAL_BOUNDARY_WINDOW = timedelta(minutes=3)
TIME_SYSTEM_CANDIDATE_WINDOW = timedelta(minutes=90)
TIME_SYSTEM_CANDIDATE_YEAR = 1950
TIME_SYSTEM_CANDIDATE_TERMS = frozenset({"芒種", "小暑", "立秋", "白露"})

NORMAL_BOUNDARY_WARNING_CODE = "TAIZAN_SEKKI_BOUNDARY_NEAR"
TIME_SYSTEM_CANDIDATE_WARNING_CODE = "TAIZAN_SEKKI_TIME_SYSTEM_CANDIDATE"

NORMAL_BOUNDARY_WARNING_MESSAGE = (
    "節入り時刻に非常に近いため、流派資料によって月柱・年柱が変わる可能性があります。"
    "必要に応じて原資料で確認してください。"
)
TIME_SYSTEM_CANDIDATE_WARNING_MESSAGE = (
    "この時期の節入りは、夏時間・時刻制度差分の影響候補が確認されています。"
    "境界付近の場合、泰山流資料での個別確認が必要です。"
)


def round_eacal_datetime_to_minute(value: datetime) -> datetime:
    """EACALの節入り時刻を、秒30以上で繰り上げる分単位へ丸める。"""
    if not isinstance(value, datetime):
        raise TypeError("value must be a datetime.")

    rounded = value.replace(second=0, microsecond=0)
    if value.second >= 30:
        rounded += timedelta(minutes=1)
    return rounded


def _legacy_local_datetime(value: datetime) -> datetime:
    """既存アプリのnaiveな日本ローカル時刻比較用にtimezone情報だけを外す。"""
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

        corrected_eacal_datetime = round_eacal_datetime_to_minute(original_eacal_datetime)
        corrected_sekki_datetime = _legacy_local_datetime(corrected_eacal_datetime)
        entries.append(
            {
                "year": int(year),
                "name": term_name,
                "datetime": corrected_sekki_datetime,
                "corrected_sekki_datetime": corrected_sekki_datetime,
                "original_eacal_datetime": original_eacal_datetime,
                "corrected_eacal_datetime": corrected_eacal_datetime,
                "month_branch": month_branch,
                "source": "EACAL基準・泰山流分四捨五入",
                "note": "EACAL時刻を秒30以上で分繰り上げ。既存のnaiveローカル時刻判定へ渡す。",
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
        boundary_datetime = _legacy_local_datetime(boundary_datetime)
    elif target_datetime.tzinfo is not None and boundary_datetime.tzinfo is None:
        target_datetime = _legacy_local_datetime(target_datetime)
    return (target_datetime - boundary_datetime).total_seconds()


def get_taizan_sekki_boundary_warnings(
    target_datetime: datetime,
    sekki_entries: list[dict],
) -> list[dict]:
    """補正後境界の近接警告と1950年の制度差分候補警告を返す。"""
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

        if (
            entry.get("year") != TIME_SYSTEM_CANDIDATE_YEAR
            or entry.get("name") not in TIME_SYSTEM_CANDIDATE_TERMS
        ):
            continue

        original_datetime = entry.get("original_eacal_datetime")
        original_difference_seconds = (
            _difference_seconds(target_datetime, original_datetime)
            if isinstance(original_datetime, datetime)
            else None
        )
        within_original_window = (
            original_difference_seconds is not None
            and abs(original_difference_seconds) <= TIME_SYSTEM_CANDIDATE_WINDOW.total_seconds()
        )
        within_corrected_window = (
            abs(corrected_difference_seconds) <= TIME_SYSTEM_CANDIDATE_WINDOW.total_seconds()
        )
        if within_original_window or within_corrected_window:
            warnings.append(
                {
                    "code": TIME_SYSTEM_CANDIDATE_WARNING_CODE,
                    "level": "warning",
                    "message": TIME_SYSTEM_CANDIDATE_WARNING_MESSAGE,
                    "term_name": entry.get("name"),
                    "boundary_datetime": corrected_datetime,
                    "original_eacal_datetime": original_datetime,
                    "difference_seconds": corrected_difference_seconds,
                    "original_difference_seconds": original_difference_seconds,
                    "comparison_basis": "original_eacal_datetime_or_corrected_sekki_datetime",
                }
            )

    return warnings
