"""Content-free management queries. Counts saved histories; never tracks views/clicks/logins."""
from datetime import datetime, timedelta, timezone
from history_repository import HistoryError

JST=timezone(timedelta(hours=9))
STATE="CASE WHEN l.state='deletion_pending' THEN 'deletion_pending' WHEN u.status='disabled' OR l.state='suspended' THEN 'suspended' ELSE 'active' END"


def month_window(now=None):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None: raise ValueError("Aware datetime required")
    start=now.astimezone(JST).replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    end=start.replace(year=start.year+1,month=1) if start.month==12 else start.replace(month=start.month+1)
    return tuple(value.astimezone(timezone.utc).isoformat(timespec="microseconds") for value in (start,end))


class UsageRepository:
    """Internal management adapter only; not a Web authorization mechanism."""
    def __init__(self, product_repository): self.product=product_repository

    @staticmethod
    def counts(db, organization_id, user_id, window):
        row=db.execute("""SELECT COUNT(*) AS saved_readings_total,
            COALESCE(SUM(CASE WHEN r.saved_at>=? AND r.saved_at<? THEN 1 ELSE 0 END),0) AS saved_readings_this_month,
            MAX(r.saved_at) AS last_saved_reading_at
            FROM readings r JOIN reading_organization_scopes s
            ON s.reading_id=r.id AND s.owner_user_id=r.owner_user_id
            WHERE s.organization_id=? AND (? IS NULL OR s.owner_user_id=?)""",
            (*window,organization_id,user_id,user_id)).fetchone()
        return dict(row)

    def organization(self, organization_id, now=None):
        window=month_window(now)
        with self.product.auth.connection() as db:
            self.product.organization(db,organization_id)
            states=[r[0] for r in db.execute(f"""SELECT {STATE} FROM memberships m JOIN users u ON u.id=m.user_id
                LEFT JOIN user_account_lifecycle l ON l.user_id=u.id WHERE m.organization_id=?""",(organization_id,))]
            return {"organization_id":organization_id,"registered_users":len(states),
                    "active_users":states.count("active"),"suspended_users":states.count("suspended"),
                    "deletion_pending_users":states.count("deletion_pending"),
                    **self.counts(db,organization_id,None,window),
                    "count_basis":"saved_history_including_soft_deleted","month_timezone":"Asia/Tokyo"}

    def user(self, organization_id, user_id, now=None):
        window=month_window(now)
        with self.product.auth.connection() as db:
            row=db.execute(f"""SELECT u.id,{STATE} AS account_state,a.last_login_at
                FROM memberships m JOIN users u ON u.id=m.user_id
                LEFT JOIN user_account_lifecycle l ON l.user_id=u.id LEFT JOIN user_activity a ON a.user_id=u.id
                WHERE m.organization_id=? AND m.user_id=?""",(organization_id,user_id)).fetchone()
            if not row: raise HistoryError("Membership not found",404)
            return {"organization_id":organization_id,"user_id":row["id"],"account_state":row["account_state"],
                    "last_login_at":row["last_login_at"],**self.counts(db,organization_id,user_id,window),
                    "count_basis":"saved_history_including_soft_deleted","month_timezone":"Asia/Tokyo"}
