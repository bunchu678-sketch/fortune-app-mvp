from __future__ import annotations

from datetime import date, datetime

from calendar_logic import shift_kanchi, split_kanchi
from fortune_data import JUUNI_UNSEI_TABLE, TSUHENSEI_TABLE


YANG_TENKAN = {"甲", "丙", "戊", "庚", "壬"}
YIN_TENKAN = {"乙", "丁", "己", "辛", "癸"}
MALE_LABELS = {"男", "男性"}
FEMALE_LABELS = {"女", "女性"}
SETSUBOKU_TRANSITIONS = {
    "forward": {("丑", "寅"), ("辰", "巳"), ("未", "申"), ("戌", "亥")},
    "reverse": {("寅", "丑"), ("巳", "辰"), ("申", "未"), ("亥", "戌")},
}
SETSUBOKU_DIRECTION_ALIASES = {
    "順行": "forward",
    "逆行": "reverse",
    "backward": "reverse",
}
DAIUN_TSUHENSEI_COMMENTS = {
    "比肩": (
        "自分の考えや気持ちを積極的に行動へ移すと良い時期。"
        "新しいことを始める力が出やすく、独立心も高まります。"
        "急に忙しくなったりするため、予定管理が大切です。"
        "何かを終わらせたら、新しいことが来る流れです。"
    ),
    "劫財": (
        "人との協調や周囲との関わりが大切になる時期です。"
        "肉体的に疲れが出やすい時でもあるため、無理をせず、自分を労わってください。"
        "信頼できる人との出逢いがあり、気が緩みやすい事にも注意が必要です。"
        "お金の使い方、浪費なのか投資なのかをよく考える時期でもあります。"
    ),
    "食神": (
        "体調もよく、人間関係も良好になりやすい時期です。"
        "大らかな気持ちでいる事が大切です。"
        "人気が高まりやすく、出費がかさむこともあります。"
        "宣伝や発信、人間ドックなど身体のメンテナンスにも向く時期です。"
        "ウッカリミスには注意してください。"
    ),
    "傷官": (
        "感覚が研ぎ澄まされる時期です。"
        "いつもなら気にならない事でも、イライラしたり、"
        "成長のチャンスでもありながらトラブルの原因にもなりやすい時です。"
        "直感や感情が強く動きやすいため、言葉や判断を少し丁寧に扱うことが大切です。"
        "10年に一度のステージアップのチャンスでもあります。"
        "成長できるように意識を変え、可能性を信じて進む時期です。"
    ),
    "偏財": (
        "新しい出逢いが多い時期です。"
        "男性は、恋人ができる時や出逢いを大切にしたい時期でもあります。"
        "目の前の好機を逃さないよう、情報に耳を傾けてください。"
        "出逢いたい人をイメージして出かけると、縁が広がりやすい時です。"
        "出逢いが多い時こそ、この時期に出逢った人との縁は深いものになりやすいです。"
    ),
    "正財": (
        "努力が実る時期です。"
        "いつもの二倍三倍頑張ってみましょう。"
        "やっただけ成果を得られます。"
        "収穫、資産、固定化に関わる流れがあり、前半は土台作り、後半から波に乗りやすくなります。"
        "めげずにやり続けることが大切です。"
    ),
    "偏官": (
        "自然と意識が外へ向かい、環境変化を起こしたくなる時期です。"
        "今までできなかったことを試すには最良の時でもあります。"
        "転換、変動、拡大の流れがあり、大きく動きたくなります。"
        "3つまで優先順位をつけることが大切です。"
        "転職や転居をする方も多い時期です。"
    ),
    "正官": (
        "冷静に正しい判断ができる時期です。"
        "5年10年先の長期プランを立てるのに向いています。"
        "周囲から認められることも多く、金運も上がりやすく、安定する流れです。"
        "しっかりした後、名前が残る方を取るとよい時期です。"
        "目の前のお金だけではなく、名誉や信頼を選ぶ意識も大切です。"
        "結婚や大きな買い物をする人も多い時期です。"
    ),
    "偏印": (
        "迷いや悩みが尽きず、気分的にすっきりしにくい時期です。"
        "慌てず、じっくり腰を据えて自分の力を蓄えてください。"
        "価値観の変化が起こりやすい時でもあります。"
        "掃除や整理整頓をするとよい時期です。"
        "あれもこれもとやりたくなるため、優先順位をつけることが大切です。"
        "新しい価値観に触れることもあります。"
    ),
    "印綬": (
        "今までの自分の反省すべき点をきちんと振り返り、"
        "次の動きのために準備をする時期です。"
        "吸収力が増すので、学ぶ姿勢を大切にしてください。"
        "憧れる人と話してみるのもよい時期です。"
        "未来を観るために反省をし、次の行動のための学びを始めてください。"
        "問題から逃げないことが大切です。"
    ),
}

DAIUN_TSUHENSEI_SUMMARY = {
    "比肩": {
        "period": "発芽期〜芽を出す時〜",
        "keywords": "独立・積極・実行",
    },
    "劫財": {
        "period": "発芽期〜芽を出す時〜",
        "keywords": "協調・消極・緩慢",
    },
    "食神": {
        "period": "成長期〜芽から茎へと成長するとき〜",
        "keywords": "調整・安定・宣伝",
    },
    "傷官": {
        "period": "成長期〜芽から茎へと成長するとき〜",
        "keywords": "直感・感情・紛争",
    },
    "偏財": {
        "period": "開花期〜花を咲かせる時〜",
        "keywords": "奉仕・出入・流動",
    },
    "正財": {
        "period": "開花期〜花を咲かせる時〜",
        "keywords": "収穫・資産・固定",
    },
    "偏官": {
        "period": "収穫期〜結実の時〜",
        "keywords": "転換・変動・拡大",
    },
    "正官": {
        "period": "収穫期〜結実の時〜",
        "keywords": "発展・責任・完成",
    },
    "偏印": {
        "period": "開墾期〜後始末、次の準備の時〜",
        "keywords": "変化・開発・整理",
    },
    "印綬": {
        "period": "開墾期〜後始末、次の準備の時〜",
        "keywords": "反省・研究・結果",
    },
}


def normalize_to_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def is_yang_tenkan(tenkan):
    return tenkan in YANG_TENKAN


def normalize_gender(gender):
    if not isinstance(gender, str):
        return ""

    normalized = gender.strip()
    if normalized in MALE_LABELS:
        return "male"
    if normalized in FEMALE_LABELS:
        return "female"
    return ""


def determine_daiun_direction(year_tenkan, gender):
    gender_key = normalize_gender(gender)
    if year_tenkan not in YANG_TENKAN and year_tenkan not in YIN_TENKAN:
        return {
            "ok": False,
            "direction": "",
            "label": "",
            "message": "年干を確認できませんでした。",
        }
    if not gender_key:
        return {
            "ok": False,
            "direction": "",
            "label": "",
            "message": "性別を選択すると大運を表示できます。",
        }

    year_is_yang = is_yang_tenkan(year_tenkan)
    is_forward = (
        (year_is_yang and gender_key == "male")
        or (not year_is_yang and gender_key == "female")
    )
    return {
        "ok": True,
        "direction": "forward" if is_forward else "reverse",
        "label": "順行" if is_forward else "逆行",
        "step": 1 if is_forward else -1,
        "message": "",
    }


def find_previous_and_next_sekki(birth_date, sekki_entries):
    target_date = normalize_to_date(birth_date)
    if target_date is None:
        return {
            "previous": None,
            "next": None,
        }

    previous_entry = None
    next_entry = None
    sorted_entries = sorted(
        (entry for entry in sekki_entries or [] if entry.get("datetime")),
        key=lambda entry: entry["datetime"],
    )

    for entry in sorted_entries:
        entry_date = normalize_to_date(entry.get("datetime"))
        if entry_date is None:
            continue
        if entry_date <= target_date:
            previous_entry = entry
        if entry_date >= target_date and next_entry is None:
            next_entry = entry

    return {
        "previous": previous_entry,
        "next": next_entry,
    }


def calculate_kigun_age_by_days(birth_date, target_sekki_date):
    birth = normalize_to_date(birth_date)
    target = normalize_to_date(target_sekki_date)
    if birth is None or target is None:
        return None

    day_diff = abs((target - birth).days)
    if day_diff <= 3:
        return 1

    return max(1, int(day_diff / 3 + 0.5))


def format_age(age_int):
    if age_int is None:
        return ""
    return f"{int(age_int)}歳"


def format_setsuboku_age_range(start_age, end_age):
    return f"{int(start_age)}歳〜{int(end_age)}歳頃"


def is_setsuboku_transition(current_branch, next_branch, direction):
    direction_key = SETSUBOKU_DIRECTION_ALIASES.get(direction, direction)
    transitions = SETSUBOKU_TRANSITIONS.get(direction_key, set())
    return (current_branch, next_branch) in transitions


def _get_tsuhensei(day_tenkan, target_tenkan):
    try:
        from personality_logic import get_tsuhensei

        return get_tsuhensei(day_tenkan, target_tenkan)
    except Exception:
        return TSUHENSEI_TABLE.get(day_tenkan, {}).get(target_tenkan, "")


def _get_juuni_unsei(day_tenkan, chishi):
    try:
        from personality_logic import get_juuni_unsei

        return get_juuni_unsei(day_tenkan, chishi)
    except Exception:
        return JUUNI_UNSEI_TABLE.get(day_tenkan, {}).get(chishi, "")


def get_daiun_tsuhensei_comment(tsuhensei):
    if not isinstance(tsuhensei, str):
        return ""

    return DAIUN_TSUHENSEI_COMMENTS.get(tsuhensei.strip(), "")


def get_daiun_tsuhensei_summary(tsuhensei):
    if not isinstance(tsuhensei, str):
        return {
            "period": "",
            "keywords": "",
        }

    return DAIUN_TSUHENSEI_SUMMARY.get(
        tsuhensei.strip(),
        {
            "period": "",
            "keywords": "",
        },
    )


def _build_empty_result(message):
    return {
        "ok": False,
        "direction": "",
        "direction_label": "",
        "kigun_age": None,
        "rows": [],
        "message": message,
    }


def build_daiun_table(
    birth_date,
    birth_year,
    gender,
    year_tenkan,
    month_kanchi,
    day_tenkan,
    sekki_entries,
    count=10,
):
    direction = determine_daiun_direction(year_tenkan, gender)
    if not direction["ok"]:
        return _build_empty_result(direction["message"])

    if not birth_date or not birth_year:
        return _build_empty_result("生年月日を確認できませんでした。")
    if not month_kanchi or len(month_kanchi) != 2:
        return _build_empty_result("月柱を確認できませんでした。")
    if not day_tenkan:
        return _build_empty_result("日干を確認できませんでした。")

    sekki_pair = find_previous_and_next_sekki(birth_date, sekki_entries)
    target_entry = (
        sekki_pair["next"]
        if direction["direction"] == "forward"
        else sekki_pair["previous"]
    )
    if not target_entry:
        return _build_empty_result("大運を表示するための暦情報を確認できませんでした。")

    kigun_age = calculate_kigun_age_by_days(
        birth_date,
        target_entry.get("datetime"),
    )
    if kigun_age is None:
        return _build_empty_result("起運年齢を計算できませんでした。")

    rows = []
    age_ranges = []
    step = direction["step"]
    for index in range(1, int(count) + 1):
        offset = step * (index - 1)
        daiun_kanchi = shift_kanchi(month_kanchi, offset)
        tenkan, chishi = split_kanchi(daiun_kanchi)
        tsuhensei = _get_tsuhensei(day_tenkan, tenkan)
        summary = get_daiun_tsuhensei_summary(tsuhensei)
        if index == 1:
            start_age = 0
            end_age = kigun_age
        else:
            start_age = kigun_age + 1 + (index - 2) * 10
            end_age = kigun_age + (index - 1) * 10
        age_ranges.append((start_age, end_age))
        rows.append({
            "大運": f"第{index}大運",
            "開始年齢": format_age(start_age),
            "終了年齢": format_age(end_age),
            "目安開始年": int(birth_year) + start_age,
            "目安終了年": int(birth_year) + end_age,
            "大運干支": daiun_kanchi,
            "天干": tenkan,
            "地支": chishi,
            "通変星": tsuhensei,
            "十二運星": _get_juuni_unsei(day_tenkan, chishi),
            "コメント": get_daiun_tsuhensei_comment(tsuhensei),
            "周期": summary["period"],
            "キーワード": summary["keywords"],
            "次の大運との間が接木運": False,
            "接木運_次大運": "",
            "接木運_次地支": "",
            "接木運_開始年齢": None,
            "接木運_終了年齢": None,
            "接木運_表示年齢": "",
        })

    for index in range(len(rows) - 1):
        current_row = rows[index]
        next_row = rows[index + 1]
        current_branch = current_row.get("地支", "")
        next_branch = next_row.get("地支", "")
        switch_age = age_ranges[index + 1][0]
        setsuboku_start_age = max(0, switch_age - 3)
        setsuboku_end_age = switch_age + 3

        current_row["接木運_次大運"] = next_row.get("大運", "")
        current_row["接木運_次地支"] = next_branch
        if is_setsuboku_transition(
            current_branch,
            next_branch,
            direction["direction"],
        ):
            current_row["次の大運との間が接木運"] = True
            current_row["接木運_開始年齢"] = setsuboku_start_age
            current_row["接木運_終了年齢"] = setsuboku_end_age
            current_row["接木運_表示年齢"] = format_setsuboku_age_range(
                setsuboku_start_age,
                setsuboku_end_age,
            )

    return {
        "ok": True,
        "direction": direction["direction"],
        "direction_label": direction["label"],
        "kigun_age": kigun_age,
        "rows": rows,
        "message": "",
    }
