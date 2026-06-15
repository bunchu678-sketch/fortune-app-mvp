from datetime import date, datetime

from fortune_data import (
    CHISHI_GOGYO_FOR_GETSUREI,
    CHISHI_ORDER,
    GOKOTON_START_MONTH_KAN,
    GOSOTON_START_HOUR_KAN,
    HOUR_BRANCH_ORDER,
    KANCHI_CYCLE,
    MONTH_BRANCH_ORDER,
    SEKKI_TO_MONTH_BRANCH,
    TENKAN_GOGYO_MAP,
    TENKAN_ORDER,
)
from meishiki_model import build_auto_meishiki_record

YEAR_KANCHI_BASE_YEAR = 1984
YEAR_KANCHI_BASE = "甲子"
GETSUREI_SIMPLE_RULE = "日干の五行と月支の基本五行が一致するかで判定する簡易月令判定"


def build_getsurei_result(
    ok: bool,
    getsurei,
    label: str,
    day_tenkan: str = "",
    day_gogyo: str = "",
    month_chishi: str = "",
    month_gogyo: str = "",
    errors=None,
) -> dict:
    return {
        "ok": ok,
        "getsurei": getsurei,
        "label": label,
        "day_tenkan": day_tenkan,
        "day_gogyo": day_gogyo,
        "month_chishi": month_chishi,
        "month_gogyo": month_gogyo,
        "rule": GETSUREI_SIMPLE_RULE,
        "errors": errors or [],
    }


def judge_getsurei(day_tenkan: str, month_chishi: str) -> dict:
    """
    日干と月支から、月令を得ているかを判定する。

    簡易判定:
    日干の五行と月支の基本五行が一致すれば、月令を得ている。
    """
    errors = []

    if not day_tenkan:
        errors.append("日干が取得できません。")
    if not month_chishi:
        errors.append("月支が取得できません。")

    day_gogyo = TENKAN_GOGYO_MAP.get(day_tenkan or "", "")
    month_gogyo = CHISHI_GOGYO_FOR_GETSUREI.get(month_chishi or "", "")

    if day_tenkan and not day_gogyo:
        errors.append(f"日干の五行を取得できません: {day_tenkan}")
    if month_chishi and not month_gogyo:
        errors.append(f"月支の基本五行を取得できません: {month_chishi}")

    if errors:
        return build_getsurei_result(
            ok=False,
            getsurei=None,
            label="月令判定不可",
            day_tenkan=day_tenkan or "",
            day_gogyo=day_gogyo,
            month_chishi=month_chishi or "",
            month_gogyo=month_gogyo,
            errors=errors,
        )

    has_getsurei = day_gogyo == month_gogyo
    return build_getsurei_result(
        ok=True,
        getsurei=has_getsurei,
        label="月令を得ている" if has_getsurei else "月令を得ていない",
        day_tenkan=day_tenkan,
        day_gogyo=day_gogyo,
        month_chishi=month_chishi,
        month_gogyo=month_gogyo,
    )


def judge_getsurei_from_meishiki(meishiki: dict) -> dict:
    """
    meishiki から日干と月支を取り出し、月令を判定する。
    """
    if not isinstance(meishiki, dict):
        return build_getsurei_result(
            ok=False,
            getsurei=None,
            label="月令判定不可",
            errors=["meishiki が取得できません。"],
        )

    day = meishiki.get("day")
    month = meishiki.get("month")
    errors = []

    if not isinstance(day, dict):
        errors.append("day が取得できません。")
        day = {}
    if not isinstance(month, dict):
        errors.append("month が取得できません。")
        month = {}

    day_tenkan = day.get("tenkan", "")
    month_chishi = month.get("chishi", "")
    if errors:
        return build_getsurei_result(
            ok=False,
            getsurei=None,
            label="月令判定不可",
            day_tenkan=day_tenkan,
            month_chishi=month_chishi,
            errors=errors,
        )

    return judge_getsurei(day_tenkan, month_chishi)


def generate_kanchi_cycle() -> list[str]:
    """
    六十干支のリストを返す。
    甲子から始まり、癸亥で終わる。
    """
    return list(KANCHI_CYCLE)


def get_kanchi_index(kanchi: str) -> int:
    """
    干支が六十干支の何番目かを0始まりで返す。
    """
    return KANCHI_CYCLE.index(kanchi)


def get_kanchi_by_index(index: int) -> str:
    """
    0始まりの番号から干支を返す。
    60を超える場合も、60周期で循環させる。
    """
    return KANCHI_CYCLE[index % len(KANCHI_CYCLE)]


def shift_kanchi(kanchi: str, offset: int) -> str:
    """
    指定した干支を、offset分だけ進める／戻す。
    """
    return get_kanchi_by_index(get_kanchi_index(kanchi) + offset)


def split_kanchi(kanchi: str) -> tuple[str, str]:
    """
    例: "甲子" -> ("甲", "子")
    """
    if len(kanchi) != 2:
        raise ValueError("kanchi must be a two-character stem-branch string.")

    tenkan, chishi = kanchi[0], kanchi[1]
    if tenkan not in TENKAN_ORDER or chishi not in CHISHI_ORDER:
        raise ValueError(f"Invalid kanchi: {kanchi}")

    return tenkan, chishi


def get_year_kanchi_by_year(year: int) -> str:
    """
    西暦年から、その年の年柱干支を返す。
    立春前後は考慮しない。

    基準:
    - 1984年 = 甲子

    1984年より前の年も、負の年数差を六十干支の循環で扱う。
    """
    year_offset = int(year) - YEAR_KANCHI_BASE_YEAR
    return get_kanchi_by_index(year_offset)


def calculate_year_pillar(target_datetime, risshun_datetime) -> dict:
    """
    対象日時と、その年の立春日時をもとに年柱を計算する。

    target_datetime は命式計算に使う日時で、将来的には
    birth_info["adjusted_birth_datetime"] を渡す想定。

    ルール:
    - target_datetime >= risshun_datetime なら対象年の年柱
    - target_datetime < risshun_datetime なら前年の年柱

    日付だけではなく、必ず時刻まで含めた datetime で判定する。
    """
    if target_datetime is None:
        raise ValueError("target_datetime is required.")
    if risshun_datetime is None:
        raise ValueError("risshun_datetime is required.")

    is_before_risshun = target_datetime < risshun_datetime
    effective_year = target_datetime.year - 1 if is_before_risshun else target_datetime.year
    year_kanchi = get_year_kanchi_by_year(effective_year)
    tenkan, chishi = split_kanchi(year_kanchi)

    return {
        "input_datetime": target_datetime,
        "risshun_datetime": risshun_datetime,
        "effective_year": effective_year,
        "year_kanchi": year_kanchi,
        "tenkan": tenkan,
        "chishi": chishi,
        "is_before_risshun": is_before_risshun,
    }


def get_tiger_month_start_tenkan(year_tenkan: str) -> str:
    """
    年干から、寅月の月干を返す。
    五虎遁の対応表を使う。
    """
    try:
        return GOKOTON_START_MONTH_KAN[year_tenkan]
    except KeyError as exc:
        raise ValueError(f"Invalid year tenkan: {year_tenkan}") from exc


def generate_month_pillars_by_year_tenkan(year_tenkan: str) -> dict:
    """
    年干をもとに、寅月から丑月までの月柱干支を返す。
    節入り日時による対象月の自動判定はまだ行わない。
    """
    start_tenkan = get_tiger_month_start_tenkan(year_tenkan)
    start_tenkan_index = TENKAN_ORDER.index(start_tenkan)

    month_pillars = {}
    for month_index, month_branch in enumerate(MONTH_BRANCH_ORDER):
        month_tenkan = TENKAN_ORDER[
            (start_tenkan_index + month_index) % len(TENKAN_ORDER)
        ]
        month_pillars[month_branch] = f"{month_tenkan}{month_branch}"

    return month_pillars


def get_month_pillar_by_branch(year_tenkan: str, month_branch: str) -> dict:
    """
    年干と月支から、月柱を返す。
    節入り日時による月支判定は、将来の別関数で扱う。
    """
    month_pillars = generate_month_pillars_by_year_tenkan(year_tenkan)
    try:
        month_kanchi = month_pillars[month_branch]
    except KeyError as exc:
        raise ValueError(f"Invalid month branch: {month_branch}") from exc

    tenkan, chishi = split_kanchi(month_kanchi)

    return {
        "year_tenkan": year_tenkan,
        "month_branch": month_branch,
        "month_kanchi": month_kanchi,
        "tenkan": tenkan,
        "chishi": chishi,
    }


def get_month_branch_from_sekki_entry(sekki_entry: dict):
    if sekki_entry.get("month_branch"):
        return sekki_entry["month_branch"]

    sekki_name = sekki_entry.get("name")
    return SEKKI_TO_MONTH_BRANCH.get(sekki_name)


def find_month_branch_by_sekki(target_datetime, sekki_entries) -> dict:
    """
    対象日時が、どの節入り以降に属するかを判定し、月支を返す。

    ルール:
    - sekki_entries は datetime 昇順に並べて扱う
    - target_datetime 以下の節入り日時のうち、最も新しいものを採用する
    - target_datetime が節入り日時ちょうどの場合は、新しい月に入ったものとして扱う
    - target_datetime が最初の節入りより前の場合は、error を含む dict を返す
    """
    if target_datetime is None:
        raise ValueError("target_datetime is required.")
    if not sekki_entries:
        return {
            "target_datetime": target_datetime,
            "month_branch": None,
            "matched_sekki_name": None,
            "matched_sekki_datetime": None,
            "error": "節入りデータがありません。",
        }

    sorted_entries = sorted(sekki_entries, key=lambda entry: entry["datetime"])
    matched_entry = None

    for sekki_entry in sorted_entries:
        if target_datetime >= sekki_entry["datetime"]:
            matched_entry = sekki_entry
        else:
            break

    if matched_entry is None:
        return {
            "target_datetime": target_datetime,
            "month_branch": None,
            "matched_sekki_name": None,
            "matched_sekki_datetime": None,
            "error": "対象日時より前の節入りデータがありません。前月または前年の節入りデータが必要です。",
        }

    month_branch = get_month_branch_from_sekki_entry(matched_entry)
    if month_branch is None:
        return {
            "target_datetime": target_datetime,
            "month_branch": None,
            "matched_sekki_name": matched_entry.get("name"),
            "matched_sekki_datetime": matched_entry.get("datetime"),
            "error": "節名から月支を判定できません。month_branch を指定してください。",
        }

    return {
        "target_datetime": target_datetime,
        "month_branch": month_branch,
        "matched_sekki_name": matched_entry.get("name"),
        "matched_sekki_datetime": matched_entry.get("datetime"),
    }


def calculate_month_pillar(target_datetime, year_tenkan: str, sekki_entries) -> dict:
    """
    対象日時、年干、節入り日時リストから月柱を計算する。

    target_datetime は命式計算に使う日時で、将来的には
    birth_info["adjusted_birth_datetime"] を渡す想定。
    year_tenkan は将来的には calculate_year_pillar() の結果から取得する。
    """
    branch_result = find_month_branch_by_sekki(target_datetime, sekki_entries)
    if branch_result.get("error"):
        return {
            "target_datetime": target_datetime,
            "year_tenkan": year_tenkan,
            "month_branch": None,
            "month_kanchi": None,
            "tenkan": None,
            "chishi": None,
            "matched_sekki_name": branch_result.get("matched_sekki_name"),
            "matched_sekki_datetime": branch_result.get("matched_sekki_datetime"),
            "error": branch_result["error"],
        }

    month_pillar = get_month_pillar_by_branch(
        year_tenkan,
        branch_result["month_branch"],
    )

    return {
        "target_datetime": target_datetime,
        "year_tenkan": year_tenkan,
        "month_branch": branch_result["month_branch"],
        "month_kanchi": month_pillar["month_kanchi"],
        "tenkan": month_pillar["tenkan"],
        "chishi": month_pillar["chishi"],
        "matched_sekki_name": branch_result["matched_sekki_name"],
        "matched_sekki_datetime": branch_result["matched_sekki_datetime"],
    }


# TODO(日柱): 日柱計算では、基準日と基準日の干支を正確に決める必要がある。
# 基準日を誤ると、すべての日柱がずれる。
# 将来的には、泰山流万年暦や信頼できる暦データと照合し、
# 基準日を確定してから本運用する。
# 現時点では calculate_day_pillar() に base_date と base_day_kanchi を
# 外から渡す設計にする。


def normalize_to_date(value):
    """
    datetime または date を date にそろえる。
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError("value must be datetime.date or datetime.datetime.")


def calculate_day_pillar(target_datetime, base_date, base_day_kanchi: str) -> dict:
    """
    対象日時から日柱を計算する。

    target_datetime は命式計算に使う日時で、将来的には
    birth_info["adjusted_birth_datetime"] を渡す想定。

    base_date は日柱計算の基準日で、base_day_kanchi はその日の干支。
    今回は基準日をコード内で決め打ちせず、外から渡す。

    ルール:
    - 日替わりは0時切り替え
    - target_datetime の date() を使う
    - base_date と target_date の日数差を計算する
    - base_day_kanchi から日数差ぶん干支を進める
    - 日数差が負でも六十干支の循環で扱う
    """
    if target_datetime is None:
        raise ValueError("target_datetime is required.")
    if base_date is None:
        raise ValueError("base_date is required.")
    if not base_day_kanchi:
        raise ValueError("base_day_kanchi is required.")

    target_date = normalize_to_date(target_datetime)
    normalized_base_date = normalize_to_date(base_date)
    day_diff = (target_date - normalized_base_date).days
    day_kanchi = shift_kanchi(base_day_kanchi, day_diff)
    tenkan, chishi = split_kanchi(day_kanchi)

    return {
        "target_datetime": target_datetime,
        "target_date": target_date,
        "base_date": normalized_base_date,
        "base_day_kanchi": base_day_kanchi,
        "day_diff": day_diff,
        "day_kanchi": day_kanchi,
        "tenkan": tenkan,
        "chishi": chishi,
        "day_change_rule": "0時切り替え",
    }


# TODO(時柱): このアプリは泰山流専用として扱う。
# 23:00〜00:59 は子刻とするが、23時台の時干算出では泰山流の
# 生時干支早見表に合わせて翌日の日干を使う。
# 日柱そのものは calculate_day_pillar() の0時切り替えを維持する。


def get_hour_branch_time_range_label(hour_branch: str) -> str:
    if hour_branch == "子":
        return "23:00〜00:59"

    branch_index = HOUR_BRANCH_ORDER.index(hour_branch)
    start_hour = branch_index * 2 - 1
    end_hour = start_hour + 1
    return f"{start_hour:02d}:00〜{end_hour:02d}:59"


def get_hour_branch_by_time(target_datetime) -> dict:
    """
    対象日時の時刻から時支を判定する。

    23:00〜00:59 は子、以降は2時間ごとに時支を進める。
    日替わりはここでは扱わない。
    """
    if target_datetime is None:
        raise ValueError("target_datetime is required.")

    hour = target_datetime.hour
    minute = target_datetime.minute
    if hour == 23:
        branch_index = 0
    else:
        branch_index = (hour + 1) // 2

    hour_branch = HOUR_BRANCH_ORDER[branch_index]

    return {
        "target_datetime": target_datetime,
        "hour": hour,
        "minute": minute,
        "hour_branch": hour_branch,
        "time_range_label": get_hour_branch_time_range_label(hour_branch),
    }


def get_rat_hour_start_tenkan(day_tenkan: str) -> str:
    """
    日干から、子刻の時干を返す。
    五鼠遁の対応表を使う。
    """
    try:
        return GOSOTON_START_HOUR_KAN[day_tenkan]
    except KeyError as exc:
        raise ValueError(f"Invalid day tenkan: {day_tenkan}") from exc


def generate_hour_pillars_by_day_tenkan(day_tenkan: str) -> dict:
    """
    日干をもとに、子刻から亥刻までの時柱干支を返す。
    """
    start_tenkan = get_rat_hour_start_tenkan(day_tenkan)
    start_tenkan_index = TENKAN_ORDER.index(start_tenkan)

    hour_pillars = {}
    for hour_index, hour_branch in enumerate(HOUR_BRANCH_ORDER):
        hour_tenkan = TENKAN_ORDER[
            (start_tenkan_index + hour_index) % len(TENKAN_ORDER)
        ]
        hour_pillars[hour_branch] = f"{hour_tenkan}{hour_branch}"

    return hour_pillars


def get_hour_pillar_by_branch(day_tenkan: str, hour_branch: str) -> dict:
    """
    日干と時支から、時柱を返す。
    """
    hour_pillars = generate_hour_pillars_by_day_tenkan(day_tenkan)
    try:
        hour_kanchi = hour_pillars[hour_branch]
    except KeyError as exc:
        raise ValueError(f"Invalid hour branch: {hour_branch}") from exc

    tenkan, chishi = split_kanchi(hour_kanchi)

    return {
        "day_tenkan": day_tenkan,
        "hour_branch": hour_branch,
        "hour_kanchi": hour_kanchi,
        "tenkan": tenkan,
        "chishi": chishi,
    }


def get_next_day_tenkan(day_tenkan: str) -> str:
    """
    日干から、翌日の日干を返す。
    """
    try:
        tenkan_index = TENKAN_ORDER.index(day_tenkan)
    except ValueError as exc:
        raise ValueError(f"Invalid day tenkan: {day_tenkan}") from exc

    return TENKAN_ORDER[(tenkan_index + 1) % len(TENKAN_ORDER)]


def get_hour_tenkan_basis_for_taizan(target_datetime, day_tenkan: str) -> dict:
    """
    泰山流の時柱計算で、時干算出に使う日干を返す。

    23時台は日柱自体を翌日に切り替えず、時干算出だけ翌日の日干を使う。
    0時台は、通常どおりその日の日干を使う。
    """
    if target_datetime is None:
        raise ValueError("target_datetime is required.")
    if not day_tenkan:
        raise ValueError("day_tenkan is required.")

    if target_datetime.hour == 23:
        return {
            "input_day_tenkan": day_tenkan,
            "hour_day_tenkan": get_next_day_tenkan(day_tenkan),
            "uses_next_day_tenkan": True,
            "rule": "泰山流: 23時台は時干算出のみ翌日の日干を使う",
        }

    return {
        "input_day_tenkan": day_tenkan,
        "hour_day_tenkan": day_tenkan,
        "uses_next_day_tenkan": False,
        "rule": "泰山流: 0時台以降はその日の日干を使う",
    }


def calculate_hour_pillar(target_datetime, day_tenkan: str) -> dict:
    """
    対象日時と日干から時柱を計算する。

    target_datetime は命式計算に使う日時で、将来的には
    birth_info["adjusted_birth_datetime"] を渡す想定。
    day_tenkan は calculate_day_pillar() の結果から取得する。

    泰山流専用仕様:
    - 日柱そのものは0時切り替えのまま維持する。
    - 23時台は、時干算出に限り翌日の日干を使う。
    - 0時台は、その日の日干を使う。
    """
    branch_result = get_hour_branch_by_time(target_datetime)
    tenkan_basis = get_hour_tenkan_basis_for_taizan(target_datetime, day_tenkan)
    hour_pillar = get_hour_pillar_by_branch(
        tenkan_basis["hour_day_tenkan"],
        branch_result["hour_branch"],
    )

    return {
        "target_datetime": target_datetime,
        "day_tenkan": day_tenkan,
        "hour_day_tenkan": tenkan_basis["hour_day_tenkan"],
        "uses_next_day_tenkan": tenkan_basis["uses_next_day_tenkan"],
        "hour_branch": branch_result["hour_branch"],
        "hour_kanchi": hour_pillar["hour_kanchi"],
        "tenkan": hour_pillar["tenkan"],
        "chishi": hour_pillar["chishi"],
        "time_range_label": branch_result["time_range_label"],
        "day_change_rule": "0時切り替え",
        "hour_tenkan_rule": tenkan_basis["rule"],
    }


# TODO(自動命式): この統合関数は、命式自動計算の土台である。
# 本運用には、正確な節入り日時データと、正確な日柱基準日の確定が必要である。
# 泰山流万年暦との差分検証を行ってから、既存の命式表へ接続する。


def build_auto_pillar_result(kanchi_key: str, detail: dict) -> dict:
    kanchi = detail[kanchi_key]
    tenkan, chishi = split_kanchi(kanchi)
    return {
        "kanchi": kanchi,
        "tenkan": tenkan,
        "chishi": chishi,
        "detail": detail,
    }


def build_auto_meishiki_error(message: str, birth_info=None, calculation_datetime=None, details=None) -> dict:
    return {
        "birth_info": birth_info,
        "calculation_datetime": calculation_datetime,
        "error": message,
        "details": details or {},
        "notes": [
            "日柱計算の基準日は検証中です。",
            "節入り日時データは検証用または外部入力です。",
        ],
    }


def calculate_auto_meishiki(
    birth_info,
    risshun_datetime,
    sekki_entries,
    base_date,
    base_day_kanchi: str,
) -> dict:
    """
    birth_info と暦計算用データから、年柱・月柱・日柱・時柱を自動計算する。

    birth_info["adjusted_birth_datetime"] を命式計算に使う。
    risshun_datetime、sekki_entries、base_date、base_day_kanchi は、
    正確な暦データを検証してから外から渡す想定。
    """
    if not birth_info or "adjusted_birth_datetime" not in birth_info:
        return build_auto_meishiki_error(
            "birth_info に adjusted_birth_datetime がありません。",
            birth_info=birth_info,
        )

    calculation_datetime = birth_info.get("adjusted_birth_datetime")
    if calculation_datetime is None:
        return build_auto_meishiki_error(
            "adjusted_birth_datetime が未設定です。",
            birth_info=birth_info,
        )
    if risshun_datetime is None:
        return build_auto_meishiki_error(
            "risshun_datetime が未設定です。",
            birth_info=birth_info,
            calculation_datetime=calculation_datetime,
        )
    if not sekki_entries:
        return build_auto_meishiki_error(
            "sekki_entries が空です。",
            birth_info=birth_info,
            calculation_datetime=calculation_datetime,
        )
    if base_date is None:
        return build_auto_meishiki_error(
            "base_date が未設定です。",
            birth_info=birth_info,
            calculation_datetime=calculation_datetime,
        )
    if not base_day_kanchi:
        return build_auto_meishiki_error(
            "base_day_kanchi が未設定です。",
            birth_info=birth_info,
            calculation_datetime=calculation_datetime,
        )

    year_result = calculate_year_pillar(calculation_datetime, risshun_datetime)
    month_result = calculate_month_pillar(
        calculation_datetime,
        year_result["tenkan"],
        sekki_entries,
    )
    if month_result.get("error"):
        return build_auto_meishiki_error(
            month_result["error"],
            birth_info=birth_info,
            calculation_datetime=calculation_datetime,
            details={
                "year": year_result,
                "month": month_result,
            },
        )

    day_result = calculate_day_pillar(
        calculation_datetime,
        base_date,
        base_day_kanchi,
    )
    hour_result = calculate_hour_pillar(calculation_datetime, day_result["tenkan"])

    return {
        "birth_info": birth_info,
        "calculation_datetime": calculation_datetime,
        "year": build_auto_pillar_result("year_kanchi", year_result),
        "month": build_auto_pillar_result("month_kanchi", month_result),
        "day": build_auto_pillar_result("day_kanchi", day_result),
        "hour": build_auto_pillar_result("hour_kanchi", hour_result),
        "notes": [
            "日柱計算の基準日は検証中です。",
            "節入り日時データは検証用または外部入力です。",
            "正確な節入り日時データと日柱基準日を確定してから既存の命式表へ接続します。",
        ],
    }


# TODO(月柱): 月柱は、節入り日の日付だけではなく節入り時刻で切り替える。
# 例: 2020年2月4日 立春、節入り時刻 6:03 の場合、
# 2020年2月4日 6:02 までは前月の丑月として扱い、
# 2020年2月4日 6:03 以降は寅月として扱う。
# 将来の月柱自動判定では、対象日時 adjusted_birth_datetime が、
# どの節入り日時から次の節入り日時までの範囲に入るかを
# datetime で判定する。


def calculate_meishiki_from_birth_info(birth_info):
    """
    将来的に、birth_info["adjusted_birth_datetime"] を基準に
    年柱・月柱・日柱・時柱を計算する。

    予定範囲:
    - 年柱: 立春切り替え
    - 月柱: 二十四節気の節切り替え
    - 日柱: 国立天文台ベースの暦処理
    - 時柱: 補正後日時の時刻
    - 検証: 泰山流万年暦との差分記録

    現時点では自動計算を完成扱いにしない。
    """
    raise NotImplementedError("命式自動計算は今後実装予定です。")


def build_pending_auto_meishiki_record(birth_info):
    return build_auto_meishiki_record(birth_info)
