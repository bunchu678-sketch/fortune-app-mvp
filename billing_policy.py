"""Pure policy previews only: dates/amounts must be explicitly supplied by the operator."""
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
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


JST = timezone(timedelta(hours=9))
MONTHLY_FEE = 2000


def first_billing_date(activated_at):
    """Initial JST calendar month is included in purchase; no prorating."""
    return add_months(utc(activated_at).astimezone(JST).replace(day=1), 1).date()


def month_end(value):
    return value.replace(day=monthrange(value.year, value.month)[1])


def paid_access_end(paid_through):
    """Inclusive paid date -> exclusive JST midnight, stored as UTC."""
    return datetime.combine(paid_through + timedelta(days=1), datetime.min.time(), JST).astimezone(timezone.utc)


def suspension_retention(suspended_at):
    from account_lifecycle import anniversary
    pending = anniversary(utc(suspended_at).astimezone(JST)).astimezone(timezone.utc)
    return pending, pending + timedelta(days=30)


def billing_preview(activated_at, state, now, *, resumed_at=None, access_ends_at=None, paid_through=None):
    """Read-only next eligible anchor, never generate/backfill invoices."""
    current = utc(now).astimezone(JST)
    if activated_at is None or state != 'active':
        return None
    first = first_billing_date(activated_at)
    anchor = current.date().replace(day=1)
    if current.date() != anchor or current.time() != datetime.min.time():
        anchor = add_months(anchor, 1)
    anchor = max(first, anchor)
    if paid_through is not None:
        anchor = max(anchor, paid_through + timedelta(days=1))
    if resumed_at is not None:
        # A missed suspended-period anchor is never retrospectively charged.
        resumed = utc(resumed_at).astimezone(JST)
        resume_anchor = resumed.date().replace(day=1)
        if resumed.date() != resume_anchor or resumed.time() != datetime.min.time():
            resume_anchor = add_months(resume_anchor, 1)
        anchor = max(anchor, resume_anchor)
    if access_ends_at is not None and paid_access_end(anchor - timedelta(days=1)) >= utc(access_ends_at):
        return None
    return anchor
