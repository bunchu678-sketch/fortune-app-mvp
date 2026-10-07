"""SQLite product adapter. Explicit additive setup; legacy history is never assigned implicitly."""
from dataclasses import dataclass
from datetime import date
import json
import re
import sqlite3
from uuid import uuid4
from auth_service import AuthRepository
from auth_schema import apply_migration
from history_repository import SQLiteHistoryRepository, HistoryError, timestamp, encode


@dataclass(frozen=True)
class OrganizationContext:
    organization_id: str
    user_id: str
    role: str
    selected_theme_key: str


def text(value, maximum=200):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise HistoryError("Invalid product setting", 422)
    return value.strip()


def key(value):
    value = text(value, 63)
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*",value):
        raise HistoryError("Invalid product key", 422)
    return value


def day(value):
    if value is None: return None
    try:
        if not isinstance(value,str) or date.fromisoformat(value).isoformat() != value: raise ValueError()
    except (TypeError, ValueError):
        raise HistoryError("Invalid contract date",422) from None
    return value


class ProductRepository:
    def __init__(self, path):
        self.auth = AuthRepository(path)
        self.path = self.auth.path
        # Retain current history tables and FK contracts; no user or snapshot updates.
        self.history = SQLiteHistoryRepository(path)
        with self.auth.connection() as db:
            apply_migration(db, "product-foundation-001", [
                """CREATE TABLE organizations (id TEXT PRIMARY KEY, display_name TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE, logo_reference TEXT, settings_json TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
                """CREATE TABLE organization_themes (organization_id TEXT NOT NULL REFERENCES organizations(id),
                    theme_key TEXT NOT NULL, display_name TEXT NOT NULL, definition_json TEXT NOT NULL,
                    PRIMARY KEY(organization_id,theme_key))""",
                """CREATE TABLE memberships (id TEXT PRIMARY KEY, organization_id TEXT NOT NULL REFERENCES organizations(id),
                    user_id TEXT NOT NULL REFERENCES users(id), role TEXT NOT NULL, selected_theme_key TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(organization_id,user_id),
                    FOREIGN KEY(organization_id,selected_theme_key) REFERENCES organization_themes(organization_id,theme_key))""",
                "CREATE INDEX memberships_user ON memberships(user_id,organization_id)",
                """CREATE TABLE contracts (id TEXT PRIMARY KEY, organization_id TEXT NOT NULL REFERENCES organizations(id),
                    state TEXT NOT NULL CHECK(state IN ('active','suspended','terminated')),
                    start_date TEXT, end_date TEXT, plan TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    CHECK(end_date IS NULL OR start_date IS NULL OR end_date>=start_date))""",
                "CREATE INDEX contracts_organization ON contracts(organization_id,state)",
                """CREATE TABLE reading_organization_scopes (reading_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL, owner_user_id TEXT NOT NULL,
                    FOREIGN KEY(organization_id,owner_user_id) REFERENCES memberships(organization_id,user_id),
                    FOREIGN KEY(owner_user_id,reading_id) REFERENCES readings(owner_user_id,id))""",
                "CREATE INDEX reading_org_owner ON reading_organization_scopes(organization_id,owner_user_id)",
            ])

    @staticmethod
    def organization(db, organization_id):
        row = db.execute("SELECT * FROM organizations WHERE id=?",(organization_id,)).fetchone()
        if not row: raise HistoryError("Organization not found",404)
        return dict(row)

    @staticmethod
    def context(db, organization_id, authenticated_user_id):
        row = db.execute("""SELECT m.organization_id,m.user_id,m.role,m.selected_theme_key
            FROM memberships m JOIN users u ON u.id=m.user_id
            LEFT JOIN user_account_lifecycle l ON l.user_id=u.id
            WHERE m.organization_id=? AND m.user_id=? AND u.status='active'
            AND COALESCE(l.state,'active')='active'""",(organization_id,authenticated_user_id)).fetchone()
        if not row: raise HistoryError("Organization membership not found",404)
        return OrganizationContext(row["organization_id"],row["user_id"],row["role"],row["selected_theme_key"] or "default")

    def resolve_context(self, organization_id, authenticated_user_id):
        with self.auth.connection() as db: return self.context(db,organization_id,authenticated_user_id)

    def create_organization(self, display_name, slug, logo_reference=None, settings=None):
        display_name=text(display_name); slug=key(slug)
        if logo_reference is not None: logo_reference=text(logo_reference,2048)
        if settings is not None and not isinstance(settings,dict): raise HistoryError("Invalid settings",422)
        values=(str(uuid4()),display_name,slug,logo_reference,encode(settings or {}),timestamp(),timestamp())
        try:
            with self.auth.connection() as db:
                db.execute("INSERT INTO organizations VALUES (?,?,?,?,?,?,?)",values)
                db.execute("INSERT INTO organization_themes VALUES (?,?,?,?)",
                           (values[0],"default","Standard",encode({"background":"white","foreground":"black"})))
        except sqlite3.IntegrityError:
            raise HistoryError("Organization already exists",409) from None
        return {"id":values[0],"display_name":display_name,"slug":slug}

    def add_membership(self, organization_id, user_id, role):
        role=key(role); now=timestamp()
        try:
            with self.auth.connection() as db:
                self.organization(db,organization_id)
                if not db.execute("SELECT 1 FROM users WHERE id=?",(user_id,)).fetchone(): raise HistoryError("User not found",404)
                db.execute("INSERT INTO memberships VALUES (?,?,?,?,NULL,?,?)",(str(uuid4()),organization_id,user_id,role,now,now))
        except sqlite3.IntegrityError:
            raise HistoryError("Membership already exists",409) from None

    def add_theme(self, organization_id, theme_key, display_name, definition):
        theme_key=key(theme_key); display_name=text(display_name)
        if not isinstance(definition,dict): raise HistoryError("Invalid theme definition",422)
        try:
            with self.auth.connection() as db:
                self.organization(db,organization_id)
                db.execute("INSERT INTO organization_themes VALUES (?,?,?,?)",(organization_id,theme_key,display_name,encode(definition)))
        except sqlite3.IntegrityError: raise HistoryError("Theme already exists",409) from None

    def select_theme(self, organization_id, authenticated_user_id, theme_key):
        theme_key=key(theme_key)
        with self.auth.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self.context(db,organization_id,authenticated_user_id)
            if not db.execute("SELECT 1 FROM organization_themes WHERE organization_id=? AND theme_key=?",(organization_id,theme_key)).fetchone():
                raise HistoryError("Theme not found",404)
            db.execute("UPDATE memberships SET selected_theme_key=?,updated_at=? WHERE organization_id=? AND user_id=?",
                       (theme_key,timestamp(),organization_id,authenticated_user_id))

    def branding(self, organization_id, authenticated_user_id):
        with self.auth.connection() as db:
            context=self.context(db,organization_id,authenticated_user_id)
            org=self.organization(db,organization_id)
            themes=[{"key":r["theme_key"],"display_name":r["display_name"],"definition":json.loads(r["definition_json"])}
                    for r in db.execute("SELECT * FROM organization_themes WHERE organization_id=? ORDER BY theme_key",(organization_id,))]
            return {"display_name":org["display_name"],"logo_reference":org["logo_reference"],
                    "settings":json.loads(org["settings_json"]),"themes":themes,"selected_theme_key":context.selected_theme_key,
                    "provider":"Powered by 博士の占いらぼ","service_name":"占い師向け鑑定支援システム"}

    def create_contract(self, organization_id, state, start_date=None, end_date=None, plan=None):
        if state not in ("active","suspended","terminated"): raise HistoryError("Invalid contract state",422)
        start_date=day(start_date); end_date=day(end_date)
        if start_date and end_date and end_date<start_date: raise HistoryError("Invalid contract date range",422)
        if plan is not None: plan=text(plan)
        contract_id=str(uuid4()); now=timestamp()
        with self.auth.connection() as db:
            self.organization(db,organization_id)
            db.execute("INSERT INTO contracts VALUES (?,?,?,?,?,?,?,?)",(contract_id,organization_id,state,start_date,end_date,plan,now,now))
        return contract_id

    def set_contract_state(self, organization_id, contract_id, state):
        if state not in ("active","suspended","terminated"): raise HistoryError("Invalid contract state",422)
        with self.auth.connection() as db:
            updated=db.execute("UPDATE contracts SET state=?,updated_at=? WHERE organization_id=? AND id=?",(state,timestamp(),organization_id,contract_id))
            if updated.rowcount != 1: raise HistoryError("Contract not found",404)

    def bind_reading(self, organization_id, authenticated_user_id, reading_id):
        # Explicit binding only. One saved reading belongs to one org and the original owner.
        with self.auth.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self.context(db,organization_id,authenticated_user_id)
            self.history.reading(db,authenticated_user_id,reading_id)
            old=db.execute("SELECT * FROM reading_organization_scopes WHERE reading_id=?",(reading_id,)).fetchone()
            if old:
                if old["organization_id"]!=organization_id or old["owner_user_id"]!=authenticated_user_id:
                    raise HistoryError("Reading is already assigned to an organization",409)
                return
            db.execute("INSERT INTO reading_organization_scopes VALUES (?,?,?)",(reading_id,organization_id,authenticated_user_id))

    def scoped_readings(self, organization_id, authenticated_user_id):
        with self.auth.connection() as db:
            self.context(db,organization_id,authenticated_user_id)
            return [dict(r) for r in db.execute("""SELECT r.id,r.reading_date,r.saved_at FROM readings r
                JOIN reading_organization_scopes s ON s.reading_id=r.id AND s.owner_user_id=r.owner_user_id
                WHERE s.organization_id=? AND r.owner_user_id=? AND r.deleted_at IS NULL ORDER BY r.saved_at DESC""",
                (organization_id,authenticated_user_id))]

    def scoped_detail(self, organization_id, authenticated_user_id, reading_id):
        with self.auth.connection() as db:
            self.context(db,organization_id,authenticated_user_id)
            if not db.execute("SELECT 1 FROM reading_organization_scopes WHERE organization_id=? AND owner_user_id=? AND reading_id=?",
                              (organization_id,authenticated_user_id,reading_id)).fetchone(): raise HistoryError("Reading not found",404)
            return self.history.reading(db,authenticated_user_id,reading_id)
