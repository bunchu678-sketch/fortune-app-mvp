"""Presentation settings only; official interpretation dictionaries remain untouched."""
from copy import deepcopy
import json
from fortune_data import JUUNI_UNSEI_PILLAR_WEIGHTS

MARI_SLUG = "mari-mutsuro"
THREE_GROUPS = {
    star: group for group, stars in {
        "地球": ("胎", "長生", "帝旺", "病"),
        "月": ("養", "衰", "冠帯", "墓"),
        "太陽": ("絶", "建禄", "沐浴", "死"),
    }.items() for star in stars
}

LIGHT = {"bg": "#ffffff", "bg-soft": "#f7f7f5", "panel": "#ffffff",
         "panel-strong": "#f2f2ef", "line": "#d2d3cc", "ink": "#171917",
         "muted": "#42463f", "soft": "#565d52", "danger": "#b02020",
         "shadow": "#0000000c", "button-text": "#ffffff"}


def theme(name, accent, dark=False):
    definition = {**LIGHT, "accent": accent, "accent-2": accent,
                  "accent-3": accent, "blue": accent, "button": accent}
    if dark:
        definition.update({"bg": "#151816", "bg-soft": "#1d211f", "panel": "#232825",
                           "panel-strong": "#2c332f", "line": "#5c665e", "ink": "#f4efe6",
                           "muted": "#d5d2c9", "soft": "#bdc8bc", "danger": "#ffada3",
                           "button-text": "#171917", "shadow": "#00000038"})
    return {"display_name": name, "definition": definition}


MARI_THEMES = {
    "default": theme("標準（金）", "#806018"),
    "red": theme("赤", "#ad2837"),
    "blue": theme("青", "#245ba8"),
    "black": theme("ブラック", "#e2be75", True),
}


def presentation(org, stored_themes):
    """Merge code defaults with existing organization definitions without GET writes."""
    if org["slug"] != MARI_SLUG:
        return {}
    settings = json.loads(org["settings_json"])
    allowed = settings.get("available_theme_keys", list(MARI_THEMES))
    if not isinstance(allowed, list):
        allowed = list(MARI_THEMES)
    allowed = [key for key in MARI_THEMES if key == "default" or key in allowed]
    saved = {item["key"]: item for item in stored_themes}
    themes = []
    for key in allowed:
        item = {"key": key, **deepcopy(MARI_THEMES[key])}
        stored = saved.get(key)
        if stored:
            # Original generic default used only white/black; keep those aliases.
            item["definition"].update(stored["definition"])
            if stored["display_name"] != "Standard":
                item["display_name"] = stored["display_name"]
        themes.append(item)
    return {"presentation_mode": "mari-keywords", "themes": themes,
            "thinking_groups": {"classification": dict(THREE_GROUPS),
                                "weights": dict(JUUNI_UNSEI_PILLAR_WEIGHTS)}}
