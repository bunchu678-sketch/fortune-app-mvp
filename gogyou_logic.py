from fortune_data import (
    TENKAN_GOGYO_MAP,
    CHISHI_BASIC_GROUPS,
    CHONG_RULES,
    SANGO_SETS,
    GOGYO_ORDER,
    BASE_CHISHI_POINTS,
)
from meishiki_model import get_pillar_value
from utils import format_relation_members

GOGYO_CYCLE_ORDER = GOGYO_ORDER[:]

def init_gogyo_scores():
    return {element: 0 for element in GOGYO_ORDER}


def get_basic_group_for_chishi(chishi):
    for element, group in CHISHI_BASIC_GROUPS.items():
        if chishi in group:
            return element
    return ""


def resolve_normal_chishi_element(chishi, all_chishi_for_judgement):
    judgement_set = set(all_chishi_for_judgement)

    if chishi == "辰":
        return "木" if {"寅", "卯"} & judgement_set else "土"
    if chishi == "未":
        return "火" if {"巳", "午"} & judgement_set else "土"
    if chishi == "戌":
        return "金" if {"申", "酉"} & judgement_set else "土"
    if chishi == "丑":
        return "水" if {"亥", "子"} & judgement_set else "土"

    return get_basic_group_for_chishi(chishi)


def judge_chong(formula_chishi, kantei_year_chishi=""):
    all_chishi = [chishi for chishi in formula_chishi if chishi]

    if kantei_year_chishi:
        all_chishi.append(kantei_year_chishi)

    judgement_set = set(all_chishi)
    formula_set = set(chishi for chishi in formula_chishi if chishi)
    zero_score_targets = []
    details = []

    for trigger, target in CHONG_RULES.items():
        if trigger in judgement_set and target in judgement_set:
            details.append({"trigger": trigger, "target": target})

            if target in formula_set:
                zero_score_targets.append(target)

    return {
        "has_chong": bool(details),
        "zero_score_targets": list(dict.fromkeys(zero_score_targets)),
        "details": details,
    }


def judge_sango(all_chishi_for_judgement):
    judgement_set = set(all_chishi_for_judgement)

    for element, members in SANGO_SETS.items():
        if set(members).issubset(judgement_set):
            return {
                "element": element,
                "members": members,
                "formed": True,
            }

    return {
        "element": "",
        "members": [],
        "formed": False,
    }


def judge_hougou(all_chishi_for_judgement):
    judgement_set = set(all_chishi_for_judgement)

    for element, members in CHISHI_BASIC_GROUPS.items():
        if set(members).issubset(judgement_set):
            return {
                "element": element,
                "members": members,
                "formed": True,
            }

    return {
        "element": "",
        "members": [],
        "formed": False,
    }


def judge_hangou(all_chishi_for_judgement, sango=None):
    judgement_set = set(all_chishi_for_judgement)
    candidates = []

    for element, members in CHISHI_BASIC_GROUPS.items():
        matched_members = [member for member in members if member in judgement_set]

        if len(matched_members) >= 2:
            candidates.append({
                "element": element,
                "members": matched_members,
                "same_as_sango": bool(sango and sango.get("formed") and sango.get("element") == element),
            })

    if sango and sango.get("formed"):
        return [
            candidate
            for candidate in candidates
            if candidate["element"] == sango.get("element")
        ]

    if len(candidates) == 1:
        return candidates

    return []


def get_chong_zero_reason(chishi, chong, kantei_year_chishi=""):
    triggers = [
        detail.get("trigger", "")
        for detail in chong.get("details", [])
        if detail.get("target") == chishi
    ]

    if kantei_year_chishi and kantei_year_chishi in triggers:
        return f"鑑定年の{kantei_year_chishi}による沖で0点"

    if triggers:
        return f"{'・'.join(triggers)}による沖で0点"

    return "沖により0点"


def get_hangou_reason(chishi, hangou_data, kantei_year_chishi=""):
    element = hangou_data.get("element", "")
    members = hangou_data.get("members", [])

    if kantei_year_chishi and kantei_year_chishi in members:
        return f"鑑定年の{kantei_year_chishi}と方合半会して{element}"

    partners = [
        member
        for member in members
        if member != chishi
    ]

    if partners:
        return f"{'・'.join(partners)}と方合半会して{element}"

    return f"{element}の方合半会"


def add_gogyo_score(scores, details, source, symbol, element, points, reason):
    if not element or points <= 0:
        details.append({
            "対象": source,
            "干支": symbol,
            "五行": element if element else "判定不可",
            "点数": 0,
            "理由": reason,
        })
        return

    scores[element] += points
    details.append({
        "対象": source,
        "干支": symbol,
        "五行": element,
        "点数": points,
        "理由": reason,
    })


def add_chishi_gogyo_score(scores, details, source, chishi, element, points, reason, has_earth_tenkan):
    if points <= 0:
        add_gogyo_score(scores, details, source, chishi, element, 0, reason)
        return

    add_gogyo_score(scores, details, source, chishi, element, points, reason)

    if has_earth_tenkan and chishi in ["巳", "午", "未"] and element == "火":
        add_gogyo_score(scores, details, source, chishi, "土", points, "天干に戊・己があるため土にも加点")


def build_chishi_scoring(
    chishi_data,
    all_chishi_for_judgement,
    chong,
    sango,
    hougou,
    hangou,
    kantei_year_chishi="",
):
    scoring = {}
    zero_score_targets = set(chong.get("zero_score_targets", []))
    sango_members = set(sango.get("members", [])) if sango.get("formed") else set()
    hougou_members = set(hougou.get("members", [])) if hougou.get("formed") else set()

    for data in chishi_data:
        pillar_key = data["pillar_key"]
        chishi = data["chishi"]
        base_points = BASE_CHISHI_POINTS.get(pillar_key, 1)
        element = resolve_normal_chishi_element(chishi, all_chishi_for_judgement)
        scoring[pillar_key] = {
            "element": element,
            "points": base_points,
            "reason": "通常判定",
        }

        if not chishi:
            scoring[pillar_key] = {
                "element": "",
                "points": 0,
                "reason": "未入力",
            }
            continue

        if chishi in zero_score_targets:
            scoring[pillar_key] = {
                "element": element,
                "points": 0,
                "reason": get_chong_zero_reason(chishi, chong, kantei_year_chishi),
            }
            continue

        if sango.get("formed") and chishi in sango_members:
            reason = f"{sango['element']}局（三合会局）"

            if kantei_year_chishi and kantei_year_chishi in sango_members:
                reason = f"鑑定年の{kantei_year_chishi}を含む{sango['element']}局（三合会局）"

            scoring[pillar_key] = {
                "element": sango["element"],
                "points": 3,
                "reason": reason,
            }
            continue

        if hougou.get("formed") and chishi in hougou_members:
            reason = f"{hougou['element']}の方合"

            if kantei_year_chishi and kantei_year_chishi in hougou_members:
                reason = f"鑑定年の{kantei_year_chishi}を含む{hougou['element']}の方合"

            scoring[pillar_key] = {
                "element": hougou["element"],
                "points": 3,
                "reason": reason,
            }

    for hangou_data in hangou:
        hangou_members = set(hangou_data.get("members", []))

        for data in chishi_data:
            pillar_key = data["pillar_key"]
            chishi = data["chishi"]

            if chishi not in hangou_members:
                continue

            if chishi in zero_score_targets:
                continue

            if sango.get("formed") and chishi in sango_members:
                continue

            scoring[pillar_key] = {
                "element": hangou_data["element"],
                "points": 3 if pillar_key == "month" else 2,
                "reason": get_hangou_reason(chishi, hangou_data, kantei_year_chishi),
            }

    return scoring


def calculate_gogyo_scores(
    year_tenkan, month_tenkan, day_tenkan, hour_tenkan,
    year_chishi, month_chishi, day_chishi, hour_chishi,
    kantei_year_tenkan="", kantei_year_chishi=""
):
    scores = init_gogyo_scores()
    details = []
    tenkan_data = [
        ("年干", year_tenkan),
        ("月干", month_tenkan),
        ("日干", day_tenkan),
        ("時干", hour_tenkan),
    ]
    chishi_data = [
        {"pillar_key": "year", "label": "年支", "chishi": year_chishi},
        {"pillar_key": "month", "label": "月支", "chishi": month_chishi},
        {"pillar_key": "day", "label": "日支", "chishi": day_chishi},
        {"pillar_key": "hour", "label": "時支", "chishi": hour_chishi},
    ]

    for label, tenkan in tenkan_data:
        element = TENKAN_GOGYO_MAP.get(tenkan, "")
        add_gogyo_score(scores, details, label, tenkan, element, 1 if element else 0, "天干")

    formula_chishi = [data["chishi"] for data in chishi_data if data["chishi"]]
    all_chishi_for_judgement = formula_chishi[:]

    if kantei_year_chishi:
        all_chishi_for_judgement.append(kantei_year_chishi)

    chong = judge_chong(formula_chishi, kantei_year_chishi)
    zero_score_targets = set(chong.get("zero_score_targets", []))
    relation_chishi_for_judgement = [
        chishi
        for chishi in formula_chishi
        if chishi not in zero_score_targets
    ]

    if kantei_year_chishi:
        relation_chishi_for_judgement.append(kantei_year_chishi)

    sango = judge_sango(relation_chishi_for_judgement)
    hougou = {"element": "", "members": [], "formed": False}

    if not sango.get("formed"):
        hougou = judge_hougou(relation_chishi_for_judgement)

    hangou = []

    if sango.get("formed") or not hougou.get("formed"):
        hangou = judge_hangou(relation_chishi_for_judgement, sango)

    all_tenkan_for_judgement = [
        tenkan
        for _label, tenkan in tenkan_data
        if tenkan
    ]

    if kantei_year_tenkan:
        all_tenkan_for_judgement.append(kantei_year_tenkan)

    has_earth_tenkan = bool({"戊", "己"} & set(all_tenkan_for_judgement))
    chishi_scoring = build_chishi_scoring(
        chishi_data,
        all_chishi_for_judgement,
        chong,
        sango,
        hougou,
        hangou,
        kantei_year_chishi,
    )

    for data in chishi_data:
        pillar_key = data["pillar_key"]
        scoring = chishi_scoring.get(pillar_key, {})
        add_chishi_gogyo_score(
            scores,
            details,
            data["label"],
            data["chishi"],
            scoring.get("element", ""),
            scoring.get("points", 0),
            scoring.get("reason", "通常判定"),
            has_earth_tenkan,
        )

    return {
        "scores": scores,
        "details": details,
        "formula_chishi": formula_chishi,
        "special_flags": {
            "chong": chong,
            "sango": sango,
            "hougou": hougou,
            "hangou": hangou,
        },
        "kantei_year": {
            "tenkan": kantei_year_tenkan,
            "chishi": kantei_year_chishi,
        },
    }


def get_gogyo_chart_order(day_tenkan):
    day_gogyo = TENKAN_GOGYO_MAP.get(day_tenkan, "")

    if day_gogyo not in GOGYO_CYCLE_ORDER:
        return GOGYO_CYCLE_ORDER

    start_index = GOGYO_CYCLE_ORDER.index(day_gogyo)
    return GOGYO_CYCLE_ORDER[start_index:] + GOGYO_CYCLE_ORDER[:start_index]


def format_gogyo_special_flags(special_flags):
    chong = special_flags.get("chong", {})
    sango = special_flags.get("sango", {})
    hougou = special_flags.get("hougou", {})
    hangou = special_flags.get("hangou", [])

    chong_text = "なし"
    if chong.get("details"):
        chong_text = " / ".join(
            f"{detail.get('trigger', '')} → {detail.get('target', '')}"
            for detail in chong.get("details", [])
        )

    sango_text = "なし"
    if sango.get("formed"):
        sango_text = f"{sango.get('element', '')}局（{format_relation_members(sango.get('members', []))}）"

    hougou_text = "なし"
    if hougou.get("formed"):
        hougou_text = f"{hougou.get('element', '')}の方合（{format_relation_members(hougou.get('members', []))}）"

    hangou_text = "なし"
    if hangou:
        hangou_text = " / ".join(
            f"{item.get('element', '')}（{format_relation_members(item.get('members', []))}）"
            for item in hangou
        )

    return [
        {"判定": "沖", "結果": chong_text},
        {"判定": "三合会局", "結果": sango_text},
        {"判定": "方合", "結果": hougou_text},
        {"判定": "方合半会", "結果": hangou_text},
    ]


def calculate_gogyo_scores_from_meishiki(meishiki, analysis_context=None):
    context = analysis_context or {}
    return calculate_gogyo_scores(
        get_pillar_value(meishiki, "year", "tenkan"),
        get_pillar_value(meishiki, "month", "tenkan"),
        get_pillar_value(meishiki, "day", "tenkan"),
        get_pillar_value(meishiki, "hour", "tenkan"),
        get_pillar_value(meishiki, "year", "chishi"),
        get_pillar_value(meishiki, "month", "chishi"),
        get_pillar_value(meishiki, "day", "chishi"),
        get_pillar_value(meishiki, "hour", "chishi"),
        context.get("target_year_tenkan", ""),
        context.get("target_year_chishi", ""),
    )
