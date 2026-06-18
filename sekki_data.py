from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import radians, sin


# 節入り日時は、現時点では日本標準時 JST の naive datetime として扱う。
# このファイルの2020年データは検証用仮データであり、
# 正確な国立天文台ベースの実データとしては扱わない。
# 将来、出典確認済みの国立天文台ベースデータへ差し替える。
# 2020年の補完データは、月支が年間を通して正しく進むか確認するための
# 暫定対応である。正式な国立天文台データ、または泰山流で採用する
# 節入り時刻は未確定であり、境界時刻付近の本番判定にはまだ使わない。
EXPLICIT_SEKKI_ENTRIES_BY_YEAR = {
    2020: [
        {
            "name": "小寒",
            "datetime": datetime(2020, 1, 6, 0, 0),
            "month_branch": "丑",
            "source": "検証用仮データ",
            "note": "将来、国立天文台ベースの正確な時刻に差し替える",
        },
        {
            "name": "立春",
            "datetime": datetime(2020, 2, 4, 18, 3),
            "month_branch": "寅",
            "source": "検証用仮データ",
            "note": "2020年立春は泰山流万年暦・国立天文台暦要項の確認により18:03として検証。境界時刻付近は引き続き検証用。",
        },
        {
            "name": "啓蟄",
            "datetime": datetime(2020, 3, 5, 0, 0),
            "month_branch": "卯",
            "source": "検証用仮データ",
            "note": "将来、国立天文台ベースの正確な時刻に差し替える",
        },
        {
            "name": "清明",
            "datetime": datetime(2020, 4, 4, 0, 0),
            "month_branch": "辰",
            "source": "検証用仮データ",
            "note": "月支が年間を通して正しく進むかを確認するための暫定補完。境界時刻付近の本番判定には使用しない。",
        },
        {
            "name": "立夏",
            "datetime": datetime(2020, 5, 5, 0, 0),
            "month_branch": "巳",
            "source": "検証用仮データ",
            "note": "月支が年間を通して正しく進むかを確認するための暫定補完。境界時刻付近の本番判定には使用しない。",
        },
        {
            "name": "芒種",
            "datetime": datetime(2020, 6, 5, 0, 0),
            "month_branch": "午",
            "source": "検証用仮データ",
            "note": "月支が年間を通して正しく進むかを確認するための暫定補完。境界時刻付近の本番判定には使用しない。",
        },
        {
            "name": "小暑",
            "datetime": datetime(2020, 7, 6, 0, 0),
            "month_branch": "未",
            "source": "検証用仮データ",
            "note": "将来、国立天文台ベースの正確な時刻に差し替える",
        },
        {
            "name": "立秋",
            "datetime": datetime(2020, 8, 7, 9, 6),
            "month_branch": "申",
            "source": "検証用仮データ",
            "note": "テスト用。実データとして確定扱いしない",
        },
        {
            "name": "白露",
            "datetime": datetime(2020, 9, 7, 0, 0),
            "month_branch": "酉",
            "source": "検証用仮データ",
            "note": "将来、国立天文台ベースの正確な時刻に差し替える",
        },
        {
            "name": "寒露",
            "datetime": datetime(2020, 10, 8, 0, 0),
            "month_branch": "戌",
            "source": "検証用仮データ",
            "note": "月支が年間を通して正しく進むかを確認するための暫定補完。境界時刻付近の本番判定には使用しない。",
        },
        {
            "name": "立冬",
            "datetime": datetime(2020, 11, 7, 0, 0),
            "month_branch": "亥",
            "source": "検証用仮データ",
            "note": "月支が年間を通して正しく進むかを確認するための暫定補完。境界時刻付近の本番判定には使用しない。",
        },
        {
            "name": "大雪",
            "datetime": datetime(2020, 12, 7, 0, 0),
            "month_branch": "子",
            "source": "検証用仮データ",
            "note": "月支が年間を通して正しく進むかを確認するための暫定補完。境界時刻付近の本番判定には使用しない。",
        },
    ],
    # 2021年データは、泰山流検証用の開発データである。
    # 小寒と立春は泰山流万年暦画像の確認値を維持する。
    # それ以外の節入り時刻は、通常日付の月支切り替え確認用として
    # 暫定的に00:00を置いている。境界時刻検証には使用しない。
    2021: [
        {
            "name": "小寒",
            "datetime": datetime(2021, 1, 5, 6, 14),
            "month_branch": "丑",
            "source": "泰山流万年暦画像確認値・検証用",
            "note": "2021年立春前の丑月判定用。泰山流万年暦画像の確認値を使用。",
        },
        {
            "name": "立春",
            "datetime": datetime(2021, 2, 3, 23, 58),
            "month_branch": "寅",
            "source": "泰山流万年暦画像確認値・検証用",
            "note": "2021年立春境界判定用。泰山流万年暦画像の確認値を使用。",
        },
        {
            "name": "啓蟄",
            "datetime": datetime(2021, 3, 5, 0, 0),
            "month_branch": "卯",
            "source": "検証用仮データ",
            "note": "通常日付の月支切り替え確認用の暫定時刻。境界時刻検証には使用しない。",
        },
        {
            "name": "清明",
            "datetime": datetime(2021, 4, 4, 0, 0),
            "month_branch": "辰",
            "source": "検証用仮データ",
            "note": "通常日付の月支切り替え確認用の暫定時刻。境界時刻検証には使用しない。",
        },
        {
            "name": "立夏",
            "datetime": datetime(2021, 5, 5, 0, 0),
            "month_branch": "巳",
            "source": "検証用仮データ",
            "note": "通常日付の月支切り替え確認用の暫定時刻。境界時刻検証には使用しない。",
        },
        {
            "name": "芒種",
            "datetime": datetime(2021, 6, 5, 0, 0),
            "month_branch": "午",
            "source": "検証用仮データ",
            "note": "通常日付の月支切り替え確認用の暫定時刻。境界時刻検証には使用しない。",
        },
        {
            "name": "小暑",
            "datetime": datetime(2021, 7, 7, 0, 0),
            "month_branch": "未",
            "source": "検証用仮データ",
            "note": "通常日付の月支切り替え確認用の暫定時刻。境界時刻検証には使用しない。",
        },
        {
            "name": "立秋",
            "datetime": datetime(2021, 8, 7, 0, 0),
            "month_branch": "申",
            "source": "検証用仮データ",
            "note": "通常日付の月支切り替え確認用の暫定時刻。境界時刻検証には使用しない。",
        },
        {
            "name": "白露",
            "datetime": datetime(2021, 9, 7, 0, 0),
            "month_branch": "酉",
            "source": "検証用仮データ",
            "note": "通常日付の月支切り替え確認用の暫定時刻。境界時刻検証には使用しない。",
        },
        {
            "name": "寒露",
            "datetime": datetime(2021, 10, 8, 0, 0),
            "month_branch": "戌",
            "source": "検証用仮データ",
            "note": "通常日付の月支切り替え確認用の暫定時刻。境界時刻検証には使用しない。",
        },
        {
            "name": "立冬",
            "datetime": datetime(2021, 11, 7, 0, 0),
            "month_branch": "亥",
            "source": "検証用仮データ",
            "note": "通常日付の月支切り替え確認用の暫定時刻。境界時刻検証には使用しない。",
        },
        {
            "name": "大雪",
            "datetime": datetime(2021, 12, 7, 0, 0),
            "month_branch": "子",
            "source": "検証用仮データ",
            "note": "通常日付の月支切り替え確認用の暫定時刻。境界時刻検証には使用しない。",
        },
    ],
    # 2022年データは、国立天文台「令和4年(2022) 暦要項」の
    # 二十四節気表をもとにした開発用・検証用データである。
    # 泰山流万年暦画像による個別確認は今後の課題である。
    2022: [
        {
            "name": "小寒",
            "datetime": datetime(2022, 1, 5, 18, 14),
            "month_branch": "丑",
            "source": "国立天文台 令和4年(2022) 暦要項",
            "note": "2022年立春前の丑月判定用。国立天文台暦要項の確認値を使用。",
        },
        {
            "name": "立春",
            "datetime": datetime(2022, 2, 4, 5, 51),
            "month_branch": "寅",
            "source": "国立天文台 令和4年(2022) 暦要項",
            "note": "2022年立春境界判定用。国立天文台暦要項の確認値を使用。",
        },
        {
            "name": "啓蟄",
            "datetime": datetime(2022, 3, 5, 23, 44),
            "month_branch": "卯",
            "source": "国立天文台 令和4年(2022) 暦要項",
            "note": "2022年の月支切り替え確認用。国立天文台暦要項の確認値を使用。",
        },
        {
            "name": "清明",
            "datetime": datetime(2022, 4, 5, 4, 20),
            "month_branch": "辰",
            "source": "国立天文台 令和4年(2022) 暦要項",
            "note": "2022年の月支切り替え確認用。国立天文台暦要項の確認値を使用。",
        },
        {
            "name": "立夏",
            "datetime": datetime(2022, 5, 5, 21, 26),
            "month_branch": "巳",
            "source": "国立天文台 令和4年(2022) 暦要項",
            "note": "2022年の月支切り替え確認用。国立天文台暦要項の確認値を使用。",
        },
        {
            "name": "芒種",
            "datetime": datetime(2022, 6, 6, 1, 26),
            "month_branch": "午",
            "source": "国立天文台 令和4年(2022) 暦要項",
            "note": "2022年の月支切り替え確認用。国立天文台暦要項の確認値を使用。",
        },
        {
            "name": "小暑",
            "datetime": datetime(2022, 7, 7, 11, 38),
            "month_branch": "未",
            "source": "国立天文台 令和4年(2022) 暦要項",
            "note": "2022年の月支切り替え確認用。国立天文台暦要項の確認値を使用。",
        },
        {
            "name": "立秋",
            "datetime": datetime(2022, 8, 7, 21, 29),
            "month_branch": "申",
            "source": "国立天文台 令和4年(2022) 暦要項",
            "note": "2022年の月支切り替え確認用。国立天文台暦要項の確認値を使用。",
        },
        {
            "name": "白露",
            "datetime": datetime(2022, 9, 8, 0, 32),
            "month_branch": "酉",
            "source": "国立天文台 令和4年(2022) 暦要項",
            "note": "2022年の月支切り替え確認用。国立天文台暦要項の確認値を使用。",
        },
        {
            "name": "寒露",
            "datetime": datetime(2022, 10, 8, 16, 22),
            "month_branch": "戌",
            "source": "国立天文台 令和4年(2022) 暦要項",
            "note": "2022年の月支切り替え確認用。国立天文台暦要項の確認値を使用。",
        },
        {
            "name": "立冬",
            "datetime": datetime(2022, 11, 7, 19, 45),
            "month_branch": "亥",
            "source": "国立天文台 令和4年(2022) 暦要項",
            "note": "2022年の月支切り替え確認用。国立天文台暦要項の確認値を使用。",
        },
        {
            "name": "大雪",
            "datetime": datetime(2022, 12, 7, 12, 46),
            "month_branch": "子",
            "source": "国立天文台 令和4年(2022) 暦要項",
            "note": "2022年の月支切り替え確認用。国立天文台暦要項の確認値を使用。",
        },
    ],
}


SUPPORTED_BIRTH_YEAR_START = 1940
SUPPORTED_BIRTH_YEAR_END = 2050
SEKKI_DATA_YEAR_START = SUPPORTED_BIRTH_YEAR_START - 1
SEKKI_DATA_YEAR_END = SUPPORTED_BIRTH_YEAR_END + 1

TARGET_SEKKI_TERMS = [
    ("小寒", 285, 1, 6, "丑"),
    ("立春", 315, 2, 4, "寅"),
    ("啓蟄", 345, 3, 6, "卯"),
    ("清明", 15, 4, 5, "辰"),
    ("立夏", 45, 5, 6, "巳"),
    ("芒種", 75, 6, 6, "午"),
    ("小暑", 105, 7, 7, "未"),
    ("立秋", 135, 8, 8, "申"),
    ("白露", 165, 9, 8, "酉"),
    ("寒露", 195, 10, 8, "戌"),
    ("立冬", 225, 11, 7, "亥"),
    ("大雪", 255, 12, 7, "子"),
]

ESTIMATED_SEKKI_SOURCE = "太陽黄経近似計算"
ESTIMATED_SEKKI_NOTE = (
    "1940-2050年公開画面用の推定節入り時刻。"
    "会食デモで広い生年を自動計算するための暫定データであり、"
    "泰山流差分と境界時刻の精密検証は後続課題。"
)


def get_supported_birth_year_range() -> tuple[int, int]:
    return SUPPORTED_BIRTH_YEAR_START, SUPPORTED_BIRTH_YEAR_END


def is_supported_birth_year(year: int) -> bool:
    year = int(year)
    return SUPPORTED_BIRTH_YEAR_START <= year <= SUPPORTED_BIRTH_YEAR_END


def _datetime_to_julian_day(value: datetime) -> float:
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)

    year = value.year
    month = value.month
    day = value.day + (
        value.hour
        + (
            value.minute
            + (value.second + value.microsecond / 1_000_000) / 60
        )
        / 60
    ) / 24

    if month <= 2:
        year -= 1
        month += 12

    century = year // 100
    gregorian_adjustment = 2 - century + century // 4
    return (
        int(365.25 * (year + 4716))
        + int(30.6001 * (month + 1))
        + day
        + gregorian_adjustment
        - 1524.5
    )


def _julian_day_to_datetime_utc(julian_day: float) -> datetime:
    unix_epoch_julian_day = 2440587.5
    return datetime(1970, 1, 1) + timedelta(days=julian_day - unix_epoch_julian_day)


def _solar_apparent_longitude(julian_day: float) -> float:
    """
    太陽の視黄経を近似計算で返す。

    外部ライブラリやCSVを実行時に使わず、Streamlit Cloud上で安定して
    十二節の切り替え時刻を持てるようにするための内蔵計算である。
    """
    julian_century = (julian_day - 2451545.0) / 36525.0
    mean_longitude = (
        280.46646
        + 36000.76983 * julian_century
        + 0.0003032 * julian_century * julian_century
    ) % 360
    mean_anomaly = (
        357.52911
        + 35999.05029 * julian_century
        - 0.0001537 * julian_century * julian_century
        - julian_century * julian_century * julian_century / 24490000
    )
    center = (
        (1.914602 - 0.004817 * julian_century - 0.000014 * julian_century * julian_century)
        * sin(radians(mean_anomaly))
        + (0.019993 - 0.000101 * julian_century)
        * sin(radians(2 * mean_anomaly))
        + 0.000289 * sin(radians(3 * mean_anomaly))
    )
    true_longitude = mean_longitude + center
    omega = 125.04 - 1934.136 * julian_century
    apparent_longitude = true_longitude - 0.00569 - 0.00478 * sin(radians(omega))
    return apparent_longitude % 360


def _angle_difference(current_longitude: float, target_longitude: float) -> float:
    return ((current_longitude - target_longitude + 180) % 360) - 180


def _estimate_sekki_datetime_jst(
    year: int,
    target_longitude: int,
    approximate_month: int,
    approximate_day: int,
) -> datetime:
    # JST正午を初期値にし、黄経差から日時を反復補正する。
    guess_jst = datetime(year, approximate_month, approximate_day, 12, 0)
    julian_day = _datetime_to_julian_day(guess_jst - timedelta(hours=9))

    for _ in range(12):
        difference = _angle_difference(
            _solar_apparent_longitude(julian_day),
            target_longitude,
        )
        julian_day -= difference / 0.98564736

    estimated_utc = _julian_day_to_datetime_utc(julian_day)
    estimated_jst = estimated_utc + timedelta(hours=9)
    if estimated_jst.second >= 30:
        estimated_jst += timedelta(minutes=1)
    return estimated_jst.replace(second=0, microsecond=0)


def _build_estimated_sekki_entries_by_year(start_year: int, end_year: int) -> dict:
    estimated_entries = {}

    for year in range(int(start_year), int(end_year) + 1):
        yearly_entries = []
        for term_name, target_longitude, month, day, month_branch in TARGET_SEKKI_TERMS:
            yearly_entries.append(
                {
                    "name": term_name,
                    "datetime": _estimate_sekki_datetime_jst(
                        year,
                        target_longitude,
                        month,
                        day,
                    ),
                    "month_branch": month_branch,
                    "source": ESTIMATED_SEKKI_SOURCE,
                    "note": ESTIMATED_SEKKI_NOTE,
                }
            )
        estimated_entries[year] = yearly_entries

    return estimated_entries


ESTIMATED_SEKKI_ENTRIES_BY_YEAR = _build_estimated_sekki_entries_by_year(
    SEKKI_DATA_YEAR_START,
    SEKKI_DATA_YEAR_END,
)


def _should_keep_explicit_sekki_entry(entry: dict) -> bool:
    source = entry.get("source", "")
    note = entry.get("note", "")
    return (
        "国立天文台" in source
        or "泰山流" in source
        or ("確認" in note and ("国立天文台" in note or "泰山流" in note))
    )


def _merge_explicit_sekki_entries() -> dict:
    merged_entries = {
        year: [entry.copy() for entry in entries]
        for year, entries in ESTIMATED_SEKKI_ENTRIES_BY_YEAR.items()
    }

    term_order = [term_name for term_name, *_rest in TARGET_SEKKI_TERMS]
    for explicit_year, explicit_entries in EXPLICIT_SEKKI_ENTRIES_BY_YEAR.items():
        entries_by_name = {
            entry["name"]: entry.copy()
            for entry in merged_entries.get(explicit_year, [])
        }
        for explicit_entry in explicit_entries:
            if _should_keep_explicit_sekki_entry(explicit_entry):
                entries_by_name[explicit_entry["name"]] = explicit_entry.copy()
        merged_entries[explicit_year] = [
            entries_by_name[term_name]
            for term_name in term_order
            if term_name in entries_by_name
        ]

    return merged_entries


SEKKI_ENTRIES_BY_YEAR = _merge_explicit_sekki_entries()


def get_sekki_entries_by_year(year: int) -> list:
    """
    指定年の節入り日時リストを返す。

    現時点では、1940-2050年の生年月日を公開画面で扱うために、
    境界用の1939年・2051年を含む内蔵データを返す。

    月柱判定では、年初や年末の日時を正しく判定するために、
    対象年だけでなく、前年末・翌年初の節入りデータが必要になる場合がある。
    将来的には、必要に応じて複数年の節入り日時を結合して渡す設計にする。
    """
    entries = SEKKI_ENTRIES_BY_YEAR.get(int(year), [])
    return [entry.copy() for entry in entries]


def get_risshun_datetime_by_year(year: int):
    for entry in get_sekki_entries_by_year(year):
        if entry.get("name") == "立春":
            return entry.get("datetime")
    return None


def get_sekki_entries_around_year(year: int) -> list:
    """
    年初・年末境界の月柱判定に使うため、前年・当年・翌年を結合する。
    """
    entries = []
    for target_year in (int(year) - 1, int(year), int(year) + 1):
        entries.extend(get_sekki_entries_by_year(target_year))
    return sorted(entries, key=lambda entry: entry["datetime"])
