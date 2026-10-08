"""Pure policy previews only: dates/amounts must be explicitly supplied by the operator."""
from calendar import monthrange
from datetime import timedelta, timezone
from account_lifecycle import utc


def add_months(value, months):
    month = value.year * 12 + value.month - 1 + months
    year, index = divmod(month, 12)
    return value.replace(year=year, month=index + 1, day=min(value.day, monthrange(year, index + 1)[1]))


def arrears_preview(first_unpaid_due_at, confirmed_at, now, last_reminded_at=None):
    """Two calendar months' grace; reminders every 14 days after manual confirmation.
    This does not determine billing anchors or schedule any transition/message.
    """
    due = utc(first_unpaid_due_at).astimezone(timezone(timedelta(hours=9)))
    confirmed, now = utc(confirmed_at), utc(now)
    if confirmed < due:
        raise ValueError("Confirmation precedes due date")
    reminder = utc(last_reminded_at) + timedelta(days=14) if last_reminded_at else confirmed + timedelta(days=14)
    return {"suspension_eligible_at": add_months(due, 2).astimezone(timezone.utc),
            "suspension_due": now >= add_months(due, 2),
            "next_reminder_at": reminder, "reminder_due": now >= reminder,
            "automatic_actions_enabled": False}


def resume_commitment(resumed_at):
    return add_months(utc(resumed_at).astimezone(timezone(timedelta(hours=9))), 2).astimezone(timezone.utc)
