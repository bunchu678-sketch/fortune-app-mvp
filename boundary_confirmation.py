"""Request-scoped confirmation for adopted sekki boundaries."""

from datetime import datetime, timedelta
from enum import Enum


class BoundaryChoice(str, Enum):
    BEFORE = "before"
    AFTER = "after"


BIRTH_CONFIRMATION_WINDOW = timedelta(minutes=5)


def get_birth_boundary(birth_date, adjusted_birth_datetime, birth_time_unknown, sekki_entries):
    """Return the relevant adopted boundary, if a human choice is needed."""
    if not birth_time_unknown and adjusted_birth_datetime is None:
        return None
    for entry in sekki_entries:
        boundary = entry["datetime"]
        if birth_time_unknown:
            if boundary.date() == birth_date:
                return entry
        elif abs(adjusted_birth_datetime - boundary) <= BIRTH_CONFIRMATION_WINDOW:
            return entry
    return None


def datetime_for_boundary_choice(boundary_datetime, choice):
    """Use the existing < / >= pillar rules on the requested side."""
    choice = BoundaryChoice(choice)
    if choice is BoundaryChoice.BEFORE:
        return boundary_datetime - timedelta(microseconds=1)
    return boundary_datetime


def get_reading_risshun(reading_date, risshun_datetime):
    return risshun_datetime if risshun_datetime and reading_date == risshun_datetime.date() else None


def parse_boundary_choice(value):
    if value is None:
        return None
    try:
        return BoundaryChoice(value)
    except (ValueError, TypeError):
        raise ValueError("境界選択はbeforeまたはafterで指定してください。") from None


def validate_boundary_selection(selection, boundary_datetime):
    if not isinstance(selection, dict):
        return None
    if selection.get("boundary_datetime") != boundary_datetime.isoformat():
        return None
    return parse_boundary_choice(selection.get("choice"))
