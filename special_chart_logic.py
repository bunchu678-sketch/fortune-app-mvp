from fortune_data import IJOU_KANSHI_MAP
from meishiki_model import PILLAR_DISPLAY_ORDER, PILLAR_LABELS, get_pillar_value
from utils import format_relation_members

SPECIAL_CHART_EMPTY_MESSAGE = "特殊な命式に該当していません。"

def get_ijou_kanshi_type(tenkan, chishi):
    if not tenkan or not chishi:
        return ""

    kanshi = f"{tenkan}{chishi}"
    return IJOU_KANSHI_MAP.get(kanshi, "")


def format_ijou_kanshi_type(ijou_type):
    if ijou_type == "通常":
        return "通常異常干支"
    if ijou_type == "暗合":
        return "暗合異常干支"
    return ijou_type


def format_special_relation_members(members):
    return format_relation_members(members)


def get_kantei_year_relation_note(members, kantei_year_chishi):
    if kantei_year_chishi and kantei_year_chishi in members:
        return f"（鑑定年の{kantei_year_chishi}を含む）"
    return ""


def format_chong_member(member, kantei_year_chishi):
    if kantei_year_chishi and member == kantei_year_chishi:
        return f"鑑定年の{member}"
    return member


def format_special_chong(chong, kantei_year_chishi, formula_chishi=None):
    zero_score_targets = set(chong.get("zero_score_targets", []))
    formula_chishi_set = set(chishi for chishi in (formula_chishi or []) if chishi)
    texts = []

    for detail in chong.get("details", []):
        trigger = detail.get("trigger", "")
        target = detail.get("target", "")

        if not trigger or not target:
            continue

        target_is_formula_chishi = target in formula_chishi_set or target in zero_score_targets

        if kantei_year_chishi and target == kantei_year_chishi and not target_is_formula_chishi:
            continue

        display_trigger = trigger
        if trigger not in formula_chishi_set:
            display_trigger = format_chong_member(trigger, kantei_year_chishi)

        display_target = target
        if not target_is_formula_chishi:
            display_target = format_chong_member(target, kantei_year_chishi)

        text = (
            f"{display_trigger}"
            f" → {display_target}"
        )

        if target in zero_score_targets:
            text += f"（{target}は五行点数0点）"

        texts.append(text)

    return " / ".join(texts)


def build_ijou_kanshi_texts(ijou_kanshi_data):
    texts = []

    for data in ijou_kanshi_data:
        ijou_type = data.get("ijou_type", "")
        tenkan = data.get("tenkan", "")
        chishi = data.get("chishi", "")

        if not ijou_type or not tenkan or not chishi:
            continue

        texts.append(
            f"{data.get('pillar_label', '')}：{tenkan}{chishi}"
            f"（{format_ijou_kanshi_type(ijou_type)}）"
        )

    return texts


def build_special_meishiki_rows(ijou_kanshi_data, gogyo_result):
    special_flags = gogyo_result.get("special_flags", {})
    kantei_year = gogyo_result.get("kantei_year", {})
    kantei_year_chishi = kantei_year.get("chishi", "")
    formula_chishi = gogyo_result.get("formula_chishi", [])
    rows = []

    ijou_texts = build_ijou_kanshi_texts(ijou_kanshi_data)
    if ijou_texts:
        rows.append({"判定": "異常干支", "結果": " / ".join(ijou_texts)})

    chong = special_flags.get("chong", {})
    chong_text = format_special_chong(chong, kantei_year_chishi, formula_chishi)
    if chong_text:
        rows.append({"判定": "沖", "結果": chong_text})

    hougou = special_flags.get("hougou", {})
    if hougou.get("formed"):
        members = hougou.get("members", [])
        rows.append({
            "判定": "方合",
            "結果": (
                f"{hougou.get('element', '')}の方合："
                f"{format_special_relation_members(members)}"
                f"{get_kantei_year_relation_note(members, kantei_year_chishi)}"
            ),
        })

    hangou = special_flags.get("hangou", [])
    hangou_texts = []
    for item in hangou:
        members = item.get("members", [])
        hangou_texts.append(
            f"{item.get('element', '')}の方合半会："
            f"{format_special_relation_members(members)}"
            f"{get_kantei_year_relation_note(members, kantei_year_chishi)}"
        )

    if hangou_texts:
        rows.append({"判定": "方合半会", "結果": " / ".join(hangou_texts)})

    sango = special_flags.get("sango", {})
    if sango.get("formed"):
        members = sango.get("members", [])
        rows.append({
            "判定": "三合会局",
            "結果": (
                f"{sango.get('element', '')}局（三合会局）："
                f"{format_special_relation_members(members)}"
                f"{get_kantei_year_relation_note(members, kantei_year_chishi)}"
            ),
        })

    return rows


def build_ijou_kanshi_data_from_meishiki(meishiki):
    return [
        {
            "pillar_label": PILLAR_LABELS[pillar_key],
            "tenkan": get_pillar_value(meishiki, pillar_key, "tenkan"),
            "chishi": get_pillar_value(meishiki, pillar_key, "chishi"),
            "ijou_type": get_ijou_kanshi_type(
                get_pillar_value(meishiki, pillar_key, "tenkan"),
                get_pillar_value(meishiki, pillar_key, "chishi"),
            ),
        }
        for pillar_key in PILLAR_DISPLAY_ORDER
    ]
