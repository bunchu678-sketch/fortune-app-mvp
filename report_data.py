"""Customer-facing report projection. Only supplied official values; no fortune calculation."""
from dataclasses import dataclass
from datetime import date
import math
import re


class ReportError(ValueError):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


@dataclass
class ReadingReport:
    filename: str
    cells: dict
    texts: dict
    chart_cells: dict
    setsuboku_boundaries: set
    kubou_months: set


def text(value):
    if value is None:
        return ""
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise ReportError("鑑定書の表示データ形式が不正です。")
    # XML 1.0 forbidden controls, including user-entered filename/name controls.
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]", "", str(value))


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ReportError("正式な数値データを取得できません。")
    return value


def format_number(value):
    return f"{number(value):g}"


def variant_message(variant):
    status = variant.get("status")
    return ("節入りの確認後に算出します。" if status == "boundary_pending" else
            "大運を取得できないため算出できません。" if status == "unavailable" else
            "算出結果を取得できませんでした。")


def difference(label, previous, following):
    if following.get("status") != "available":
        return label + "：" + variant_message(following)
    if previous.get("status") != "available":
        return label + "：" + variant_message(previous)
    left, right = previous["gogyo"]["scores"], following["gogyo"]["scores"]
    parts = []
    for element in "木火土金水":
        a, b = number(left[element]), number(right[element])
        if a != b:
            parts.append(f"{element} {a:g} → {b:g}（{b-a:+g}）")
    return label + "：" + ("、".join(parts) if parts else "五行点数に変化なし")


def build_reading_report(form, result):
    """Whitelist every field. Never serialize result wholesale or fetch comments anew."""
    if not isinstance(form, dict) or not isinstance(result, dict) or result.get("ok") is not True:
        raise ReportError("正式な鑑定結果が必要です。")
    variants = result.get("gogyo_variants", {})
    a, b, c = (variants.get(key, {}) for key in "ABC")
    if a.get("status") != "available":
        raise ReportError("元命式の五行結果がないため出力できません。")
    specials = result.get("special_meishiki", {}).get("rows", [])
    if len(specials) > 6:
        raise ReportError("特殊な命式がテンプレートの6行を超えています。省略せず確認が必要です。")
    daiun = result.get("daiun", {}).get("rows", [])
    if len(daiun) > 10:
        raise ReportError("大運がテンプレートの10列を超えています。")
    basic = {x["項目"]: x.get("内容", "") for x in result.get("basic_info", [])}
    display = result.get("display_snapshot", {})
    basic.update({x["項目"]: x.get("内容", "") for x in display.get("basicRows", [])})
    name = (text(form.get("surname", "")) + text(form.get("givenName", ""))).strip() or "無記名"
    try:
        birth = date.fromisoformat(form["birthDate"])
        reading = date.fromisoformat(form["readingDate"])
    except (KeyError, ValueError, TypeError) as exc:
        raise ReportError("生年月日・鑑定日を確認してください。") from exc
    age = result.get("personality", {}).get("current_life_stage_pair") or {}
    age_value = age.get("age")
    if age_value is None:
        age_value = reading.year - birth.year - ((reading.month, reading.day) < (birth.month, birth.day))
    birth_time = "出生時刻不明"
    if not form.get("birthTimeUnknown"):
        match = re.fullmatch(r"(\d{1,2}):(\d{2})", text(form.get("birthTime", "")))
        if not match or int(match[1]) > 23 or int(match[2]) > 59:
            raise ReportError("出生時刻を確認してください。")
        birth_time = f"{int(match[1])}時{int(match[2]):02d}分生まれ"
    cells = {
        "C2": "鑑定日", "D2": f"{reading.year}年{reading.month}月{reading.day}日",
        "D3": name, "G3": f"{birth.year}年", "H3": f"{birth.month}月", "I3": f"{birth.day}日", "J3": birth_time,
        "L3": text(basic.get("出生地", form.get("birthPlace", ""))),
        "M3": age_value if age_value >= 0 else "", "N3": text(basic.get("性別", form.get("gender", ""))),
        "E13": text(result.get("kubou", "")), "N14": "",
        "C15": difference("今年の影響", a, b), "C16": difference("大運の影響", b, c),
        "C17": "",
        "B60": "●年運　太罫線：接木運の境界",
    }
    for addr in ("L3", "N3"):
        if cells[addr] == "未選択": cells[addr] = "未入力"
    # Stem and branch occupy the existing separate rows under the combined chart label.
    stars = result["star_data"]
    for col, pillar in zip("DEFG", ("hour", "day", "month", "year")):
        values = result["meishiki"][pillar]
        missing = pillar == "hour" and form.get("birthTimeUnknown")
        cells[col+"7"] = "" if missing else text(values.get("tenkan"))
        cells[col+"8"] = "" if missing else text(values.get("chishi"))
        cells[col+"9"] = "" if missing else text(values.get("zokkan"))
        cells[col+"10"] = "－" if pillar == "day" else "" if missing else text(stars.get(pillar+"_tsuhensei"))
        cells[col+"11"] = "" if missing else text(stars.get(pillar+"_zokkan_tsuhensei"))
        cells[col+"12"] = "" if missing else text(stars.get(pillar+"_juuni_unsei"))
    gogyo = a["gogyo"]
    if len(gogyo["chart_order"]) != 5 or set(gogyo["chart_order"]) != set("木火土金水"):
        raise ReportError("五行図の正式配置を取得できません。")
    for address, element in zip(("K6", "M8", "L12", "J12", "I8"), gogyo["chart_order"]):
        cells[address] = f"{element} {format_number(gogyo['scores'][element])}"
    for i in range(6):
        row = specials[i] if i < len(specials) else {}
        cells[f"C{19+i}"] = text(row.get("判定"))
        cells[f"E{19+i}"] = text(row.get("結果"))
    personality = result.get("personality", {})
    nikkan = personality.get("nikkan", {})
    keywords = text(nikkan.get("keywords"))
    cells["B25"] = "●干支から読み取れるもの" + ("　キーワード："+keywords if keywords else "")
    texts = {"Phase5_Nikkan": text(nikkan.get("description")), "3": text(result.get("yearly_overall", {}).get("comment") or result.get("yearly_overall", {}).get("interpretation_message") or result.get("yearly_overall", {}).get("error"))}
    stages = ("幼年期", "青年期", "成熟期", "老年期")
    life = personality.get("life_stage_tsuhensei", [])
    if len(life) != 4:
        raise ReportError("人生4段階の正式結果が不足しています。")
    for i, row in enumerate(life):
        texts[f"Phase5_Stage{i}"] = "\n".join(part for part in (
            "社会に見せている自分：" + (text(row.get("outer")) or "－"), text(row.get("outer_comment")),
            "本来の自分：" + (text(row.get("inner")) or "－"), text(row.get("inner_comment")),
        ) if part)
    stage_name = text(display.get("currentStageName"))
    if not stage_name and isinstance(age.get("age"), int) and age["age"] >= 0:
        stage_name = stages[0 if age["age"] < 5 else 1 if age["age"] < 30 else 2 if age["age"] < 65 else 3]
    cells["B34"] = "●本来の自分らしさ" + (f"　{stage_name}：{text(age.get('outer'))} × {text(age.get('inner'))}" if age else "")
    texts["Phase5_CurrentStage"] = text(age.get("public_comment"))
    juuni = {x["pillar_key"]: x for x in personality.get("juuni_unsei", {}).get("rows", [])}
    for i, key in enumerate(("year", "month", "day", "hour")):
        row = juuni.get(key, {})
        texts[f"Phase5_Juuni{i}"] = text(row.get("public_comment"))
        col, heading_row, footer_row = ("C" if i%2==0 else "I"), (37 if i<2 else 40), (39 if i<2 else 42)
        if row:
            cells[f"{col}{heading_row}"] = f"{text(row.get('personality_heading'))}（{text(row.get('pillar_label'))}）"
        cells[f"{col}{footer_row}"] = text(row.get("juuni_unsei")) + ("　キーワード："+text(row.get("keywords")) if row.get("keywords") else "")
    borders = set()
    for i, col in enumerate("CDEFGHIJKL"):
        row = daiun[i] if i < len(daiun) else {}
        cells[col+"56"] = (text(row.get("開始年齢")) + "〜" + text(row.get("終了年齢"))) if row else ""
        cells[col+"57"] = text(row.get("通変星"))
        cells[col+"58"] = text(row.get("天干"))
        cells[col+"59"] = text(row.get("地支"))
        if i < len(daiun)-1 and row.get("次の大運との間が接木運"):
            borders.add(i)
    year = result.get("yearly_overall", {})
    cells.update({"L60": year.get("year", ""), "M60": text(year.get("tenkan")), "N60": text(year.get("chishi")),
                  "E61": text(year.get("tsuhensei")), "G61": "年運テーマ："+text(year.get("theme")) if year.get("theme") else ""})
    months = result.get("yearly_flow", {}).get("rows", [])
    if len(months) != 12 or [x.get("月番号") for x in months] != list(range(2,13))+[1]:
        raise ReportError("正式な月運12か月の結果が不足しています。")
    kubou_months = set()
    for i, (col, row) in enumerate(zip("CDEFGHIJKLMN", months)):
        cells[col+"63"] = text(row["月番号"])+"月"
        for target, key in ((64,"天干"),(65,"地支"),(66,"通変星")):
            cells[col+str(target)] = text(row.get(key))
        if row.get("空亡"): kubou_months.add(i)
    chart_cells = {}
    thinking = personality.get("juuni_unsei", {}).get("thinking", {})
    for group, labels, label_col, value_col, start in (
        ("brain_type", ("左脳","右脳"), "Q","R",103),
        ("merit_type", ("デメリット型","メリット型"), "Q","R",106),
        ("goal_type", ("目標変化型","目標直進型"), "T","U",103),
        ("principle_type", ("原理原則型","応用拡大型"), "T","U",105),
        ("work_type", ("現場型攻め","現場型守り","管理型ムードメーカー","管理型アイデアマン"), "W","X",103),
    ):
        scores = thinking.get(group, {})
        total = sum(number(scores.get(label,0)) for label in labels)
        for i, label in enumerate(labels):
            value = number(scores.get(label,0))
            chart_cells[label_col+str(start+i)] = label
            chart_cells[value_col+str(start+i)] = value if group == "work_type" else value/total if total else 0
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "", name).strip(" .")[:80] or "無記名"
    return ReadingReport(f"鑑定書_{safe_name}_{reading.isoformat()}.xlsx", cells, texts, chart_cells, borders, kubou_months)
