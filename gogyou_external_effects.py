"""Evaluate natal four-pillar scores with multiple unscored external effects.

The existing one-year engine remains the compatibility path for A and B.
External effects share one rule path; their order never establishes precedence.
"""
from fortune_data import (
    BASE_CHISHI_POINTS, CHISHI_BASIC_GROUPS, CHONG_RULES,
    SANGO_SETS, TENKAN_GOGYO_MAP,
)
from gogyou_logic import (
    add_chishi_gogyo_score, add_gogyo_score, get_basic_group_for_chishi,
    init_gogyo_scores, resolve_normal_chishi_element,
)
from meishiki_model import get_pillar_value


PILLARS = (("year", "年"), ("month", "月"), ("day", "日"), ("hour", "時"))
SOURCE_LABELS = {"kantei_year": "鑑定年", "daiun": "大運"}


def _effect_note(members, effects):
    labels = [
        f"{SOURCE_LABELS.get(effect['source'], effect['source'])}の{effect['chishi']}"
        for effect in effects
        if effect.get("chishi") in members
    ]
    return "・".join(labels)


def _effective_members(branches, element, relations):
    return [
        branch for branch in branches
        if all(
            branch not in relation["members"] or relation["element"] == element
            for relation in relations
        )
    ]


def _relation_candidates(branches, groups, blockers=()):
    candidates = []
    for element, members in groups.items():
        if set(members).issubset(set(_effective_members(branches, element, blockers))):
            candidates.append({"element": element, "members": members, "formed": True})
    return candidates


def _half_candidates(branches, sango, hougou):
    candidates = []
    for element, members in CHISHI_BASIC_GROUPS.items():
        eligible = set(_effective_members(branches, element, [*sango, *hougou]))
        matched = [member for member in members if member in eligible]
        if len(matched) == 2:
            candidates.append({
                "element": element,
                "members": matched,
                "same_as_sango": any(item["element"] == element for item in sango),
            })
    return candidates


def calculate_gogyo_scores_with_external_effects(meishiki, external_effects):
    """Score only natal pillars while all supplied effects participate in judgments."""
    effects = sorted(
        (
            {"source": effect["source"], "tenkan": effect.get("tenkan", ""),
             "chishi": effect.get("chishi", "")}
            for effect in external_effects
        ),
        key=lambda effect: (effect["source"], effect["tenkan"], effect["chishi"]),
    )
    natal = [
        {
            "key": key, "label": label,
            "tenkan": get_pillar_value(meishiki, key, "tenkan"),
            "chishi": get_pillar_value(meishiki, key, "chishi"),
        }
        for key, label in PILLARS
    ]
    scores = init_gogyo_scores()
    details = []
    for item in natal:
        element = TENKAN_GOGYO_MAP.get(item["tenkan"], "")
        add_gogyo_score(
            scores, details, item["label"] + "干", item["tenkan"], element,
            1 if element else 0, "天干",
        )

    formula_chishi = [item["chishi"] for item in natal if item["chishi"]]
    effect_chishi = [effect["chishi"] for effect in effects if effect["chishi"]]
    all_chishi = [*formula_chishi, *effect_chishi]
    judgement_set = set(all_chishi)
    formula_set = set(formula_chishi)
    zero_targets = []
    chong_details = []
    for trigger, target in CHONG_RULES.items():
        if trigger in judgement_set and target in judgement_set:
            chong_details.append({"trigger": trigger, "target": target})
            if target in formula_set:
                zero_targets.append(target)
    zero_set = set(zero_targets)
    chong = {
        "has_chong": bool(chong_details),
        "zero_score_targets": list(dict.fromkeys(zero_targets)),
        "details": chong_details,
    }

    relation_branches = [
        branch for branch in formula_chishi if branch not in zero_set
    ] + effect_chishi
    sango = _relation_candidates(relation_branches, SANGO_SETS)
    hougou = _relation_candidates(relation_branches, CHISHI_BASIC_GROUPS, sango)
    hangou = _half_candidates(relation_branches, sango, hougou)
    has_earth_stem = any(
        stem in ("戊", "己")
        for stem in (
            *[item["tenkan"] for item in natal],
            *[effect["tenkan"] for effect in effects],
        )
    )

    for item in natal:
        key, branch = item["key"], item["chishi"]
        normal_group = get_basic_group_for_chishi(branch)
        effective_for_normal = [
            member for member in all_chishi
            if (member not in zero_set or member in effect_chishi)
            and all(
                member not in relation["members"]
                or relation["element"] == normal_group
                for relation in [*sango, *hougou]
            )
        ]
        element = resolve_normal_chishi_element(branch, effective_for_normal)
        points = BASE_CHISHI_POINTS.get(key, 1)
        reason = "通常判定"
        if not branch:
            element, points, reason = "", 0, "未入力"
        elif branch in zero_set:
            triggers = [
                entry["trigger"] for entry in chong_details
                if entry["target"] == branch
            ]
            named = _effect_note(triggers, effects)
            reason = (
                f"{named}による沖で0点" if named
                else f"{'・'.join(triggers)}による沖で0点"
            )
            points = 0
        else:
            sango_match = next(
                (relation for relation in sango if branch in relation["members"]), None
            )
            hougou_match = next(
                (relation for relation in hougou if branch in relation["members"]), None
            )
            if sango_match:
                element, points = sango_match["element"], 3
                note = _effect_note(sango_match["members"], effects)
                reason = (
                    f"{note}を含む{element}局（三合会局）" if note
                    else f"{element}局（三合会局）"
                )
            elif hougou_match:
                element, points = hougou_match["element"], 3
                note = _effect_note(hougou_match["members"], effects)
                reason = (
                    f"{note}を含む{element}の方合" if note
                    else f"{element}の方合"
                )
            else:
                half_match = next(
                    (relation for relation in hangou if branch in relation["members"]),
                    None,
                )
                if half_match:
                    element = half_match["element"]
                    points = 3 if key == "month" else 2
                    note = _effect_note(half_match["members"], effects)
                    partners = [
                        member for member in half_match["members"] if member != branch
                    ]
                    reason = (
                        f"{note}と方合半会して{element}" if note
                        else f"{'・'.join(partners)}と方合半会して{element}"
                    )
        add_chishi_gogyo_score(
            scores, details, item["label"] + "支", branch, element, points,
            reason, has_earth_stem,
        )

    year = next((effect for effect in effects if effect["source"] == "kantei_year"), {})
    empty = {"element": "", "members": [], "formed": False}
    return {
        "scores": scores,
        "details": details,
        "include_kantei_year_gogyo_effects": bool(year),
        "formula_chishi": formula_chishi,
        "special_flags": {
            "chong": chong,
            "sango": sango[0] if sango else empty,
            "hougou": hougou[0] if hougou else empty,
            "hangou": hangou,
            "sango_all": sango,
            "hougou_all": hougou,
        },
        "kantei_year": {
            "tenkan": year.get("tenkan", ""),
            "chishi": year.get("chishi", ""),
        },
        "external_effects": effects,
    }
