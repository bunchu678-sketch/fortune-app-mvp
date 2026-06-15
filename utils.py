def format_relation_members(members):
    return "・".join(members) if members else ""


def format_score_percent(score):
    if score is None:
        return "0%"

    try:
        return f"{float(score):.0f}%"
    except (TypeError, ValueError):
        return str(score)
