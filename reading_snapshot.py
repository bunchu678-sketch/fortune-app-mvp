"""Narrow interpretation projection; never recalculate a saved chart."""
from copy import deepcopy
from yearly_overall_comments import interpretation_fields


def public_result_snapshot(result):
    """Drop only retired K03 paths. Versioned official snapshots remain frozen."""
    value = deepcopy(result)
    personality = value.get("personality", {})
    for row in personality.get("life_stage_tsuhensei", []):
        row.pop("outer_private_comment", None)
        row.pop("inner_private_comment", None)
    personality.get("month_pair", {}).pop("private_comment", None)
    for row in personality.get("juuni_unsei", {}).get("rows", []):
        row.pop("private_comment", None)
    yearly = value.get("yearly_overall")
    # Unversioned test/old-client snapshots used a single 2026 dictionary.
    # Do not keep its text under another year, and never update versioned text.
    if isinstance(yearly, dict) and yearly.get("ok") and "interpretation_status" not in yearly:
        yearly.update(interpretation_fields(yearly.get("year"), yearly.get("tsuhensei")))
    return value
