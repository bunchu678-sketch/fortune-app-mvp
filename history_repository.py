"""SQLite adapter. All persisted objects and queries are scoped by owner."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
from reading_snapshot import public_result_snapshot


class HistoryError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def normalize(value):
    import unicodedata
    return unicodedata.normalize("NFKC", value).strip()


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


class SQLiteHistoryRepository:
    """Adapter boundary: SQL and storage layout stay in this class."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS persons (
                id TEXT PRIMARY KEY, owner_user_id TEXT NOT NULL,
                surname TEXT NOT NULL, given_name TEXT NOT NULL,
                surname_kana TEXT NOT NULL, given_name_kana TEXT NOT NULL,
                normalized_surname TEXT NOT NULL, normalized_given_name TEXT NOT NULL,
                birth_date TEXT NOT NULL, current_input TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(owner_user_id,id));
            CREATE INDEX IF NOT EXISTS persons_match
                ON persons(owner_user_id,normalized_surname,normalized_given_name,birth_date);
            CREATE TABLE IF NOT EXISTS reading_groups (
                id TEXT PRIMARY KEY, owner_user_id TEXT NOT NULL, person_id TEXT NOT NULL,
                created_at TEXT NOT NULL, UNIQUE(owner_user_id,id,person_id),
                FOREIGN KEY(owner_user_id,person_id) REFERENCES persons(owner_user_id,id));
            CREATE TABLE IF NOT EXISTS readings (
                id TEXT PRIMARY KEY, owner_user_id TEXT NOT NULL,
                person_id TEXT NOT NULL, group_id TEXT NOT NULL, source_reading_id TEXT,
                reading_date TEXT NOT NULL, saved_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                deleted_at TEXT, memo TEXT NOT NULL, input_snapshot TEXT NOT NULL,
                result_snapshot TEXT NOT NULL, app_version TEXT NOT NULL,
                calculation_logic_version TEXT NOT NULL, data_schema_version INTEGER NOT NULL,
                UNIQUE(owner_user_id,id),
                FOREIGN KEY(owner_user_id,person_id) REFERENCES persons(owner_user_id,id),
                FOREIGN KEY(owner_user_id,group_id,person_id)
                    REFERENCES reading_groups(owner_user_id,id,person_id),
                FOREIGN KEY(owner_user_id,source_reading_id) REFERENCES readings(owner_user_id,id));
            CREATE INDEX IF NOT EXISTS readings_list ON readings(owner_user_id,deleted_at,saved_at);
            CREATE INDEX IF NOT EXISTS readings_group ON readings(owner_user_id,group_id,saved_at);
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def person(db, owner, person_id):
        row = db.execute("SELECT * FROM persons WHERE owner_user_id=? AND id=?",
                         (owner, person_id)).fetchone()
        if not row:
            raise HistoryError("鑑定対象者が見つかりません。", 404)
        from service_contract_repository import content_visible
        readings=db.execute('SELECT id FROM readings WHERE owner_user_id=? AND person_id=?',(owner,person_id)).fetchall()
        if readings and not any(content_visible(db,owner,r[0]) for r in readings):
            raise HistoryError('鑑定対象者が見つかりません。',404)
        return dict(row)

    @staticmethod
    def reading(db, owner, reading_id):
        row = db.execute("SELECT * FROM readings WHERE owner_user_id=? AND id=? AND deleted_at IS NULL",
                         (owner, reading_id)).fetchone()
        if not row:
            raise HistoryError("鑑定履歴が見つかりません。", 404)
        from service_contract_repository import content_visible
        if not content_visible(db,owner,reading_id):
            raise HistoryError('鑑定履歴が見つかりません。',404)
        data = dict(row)
        for key in ("input_snapshot", "result_snapshot"):
            data[key] = json.loads(data[key])
        data["result_snapshot"] = public_result_snapshot(data["result_snapshot"])
        return data

    def candidates(self, owner, form):
        surname, given = normalize(form.get("surname", "")), normalize(form.get("givenName", ""))
        if not surname or not given:
            return []
        with self.connection() as db:
            rows = db.execute("""SELECT * FROM persons WHERE owner_user_id=?
                AND normalized_surname=? AND normalized_given_name=? AND birth_date=?
                AND EXISTS(SELECT 1 FROM readings r WHERE r.owner_user_id=persons.owner_user_id
                    AND r.person_id=persons.id AND r.deleted_at IS NULL)
                ORDER BY created_at DESC""", (owner, surname, given, form.get("birthDate"))).fetchall()
            from service_contract_repository import content_visible
            candidates = []
            for row in rows:
                person = dict(row)
                history = db.execute("""SELECT id,group_id,reading_date,saved_at FROM readings
                    WHERE owner_user_id=? AND person_id=? AND deleted_at IS NULL
                    ORDER BY saved_at DESC""", (owner, row["id"])).fetchall()
                history=[h for h in history if content_visible(db,owner,h['id'])]
                if not history: continue
                candidates.append({
                    "id": row["id"], "surname": row["surname"], "givenName": row["given_name"],
                    "birthDate": row["birth_date"], "birthPlace": json.loads(person["current_input"]).get("form", {}).get("birthPlace", ""),
                    "histories": [dict(h) for h in history],
                })
            return candidates

    def create(self, owner, payload, versions, organization_id=None):
        snapshot, result = payload["input_snapshot"], public_result_snapshot(payload["result_snapshot"])
        form, link = snapshot["form"], payload.get("link") or {"mode": "new_person"}
        now, reading_id = timestamp(), str(uuid4())
        with self.connection() as db:
            if organization_id:
                from operations_repository import OperationsRepository
                db.execute("BEGIN IMMEDIATE")
                OperationsRepository.member_access(db,organization_id,owner)
                source_id=link.get("source_reading_id")
                if source_id:
                    source_scope=db.execute("SELECT organization_id FROM reading_organization_scopes WHERE reading_id=? AND owner_user_id=?",(source_id,owner)).fetchone()
                    if source_scope and source_scope[0]!=organization_id:
                        raise HistoryError("別Organizationの再鑑定元を使用できません。",404)
            person_id = link.get("person_id")
            source = None
            if link.get("source_reading_id"):
                source = self.reading(db, owner, link["source_reading_id"])
                if source["person_id"] != person_id:
                    raise HistoryError("再鑑定元の人物が一致しません。")
            if link["mode"] == "new_person":
                if person_id or source:
                    raise HistoryError("別人登録の指定が不正です。")
                person_id = str(uuid4())
                db.execute("""INSERT INTO persons VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    person_id, owner, form.get("surname", ""), form.get("givenName", ""),
                    form.get("surnameKana", ""), form.get("givenNameKana", ""),
                    normalize(form.get("surname", "")), normalize(form.get("givenName", "")),
                    form["birthDate"], encode(snapshot), now, now))
            else:
                self.person(db, owner, person_id)
                # Current person information can change; historical snapshots never change.
                db.execute("""UPDATE persons SET surname=?,given_name=?,surname_kana=?,given_name_kana=?,
                    normalized_surname=?,normalized_given_name=?,birth_date=?,current_input=?,updated_at=?
                    WHERE owner_user_id=? AND id=?""", (
                    form.get("surname", ""), form.get("givenName", ""),
                    form.get("surnameKana", ""), form.get("givenNameKana", ""),
                    normalize(form.get("surname", "")), normalize(form.get("givenName", "")),
                    form["birthDate"], encode(snapshot), now, owner, person_id))
            if link["mode"] == "existing_group":
                group_id = link.get("group_id")
                row = db.execute("""SELECT id FROM reading_groups WHERE owner_user_id=? AND id=? AND person_id=?""",
                                 (owner, group_id, person_id)).fetchone()
                if not row or (source and source["group_id"] != group_id):
                    raise HistoryError("鑑定グループが一致しません。", 404)
            else:
                group_id = str(uuid4())
                db.execute("INSERT INTO reading_groups VALUES (?,?,?,?)", (group_id, owner, person_id, now))
            db.execute("""INSERT INTO readings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                reading_id, owner, person_id, group_id, link.get("source_reading_id"),
                form["readingDate"], now, now, None, payload.get("memo", ""),
                encode(snapshot), encode(result), *versions))
            if organization_id:
                db.execute("INSERT INTO reading_organization_scopes VALUES (?,?,?)",(reading_id,organization_id,owner))
            return self.reading(db, owner, reading_id)

    def organization_scope(self, owner, reading_id):
        with self.connection() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='reading_organization_scopes'").fetchone():
                return None
            row=db.execute("SELECT organization_id FROM reading_organization_scopes WHERE reading_id=? AND owner_user_id=?",(reading_id,owner)).fetchone()
            return row[0] if row else None

    def detail(self, owner, reading_id):
        with self.connection() as db:
            return self.reading(db, owner, reading_id)

    def memos(self, owner, group_id, exclude=None):
        with self.connection() as db:
            if not db.execute("SELECT id FROM reading_groups WHERE owner_user_id=? AND id=?",
                              (owner, group_id)).fetchone():
                raise HistoryError("鑑定グループが見つかりません。", 404)
            from service_contract_repository import content_visible
            return [dict(r) for r in db.execute("""SELECT id,reading_date,memo FROM readings
                WHERE owner_user_id=? AND group_id=? AND deleted_at IS NULL AND id<>?
                AND memo<>'' ORDER BY reading_date ASC,saved_at ASC""", (owner, group_id, exclude or "")) if content_visible(db,owner,r["id"])]

    def list(self, owner, keyword="", start="", end=""):
        with self.connection() as db:
            rows = db.execute("""SELECT * FROM readings WHERE owner_user_id=? AND deleted_at IS NULL
                AND (?='' OR reading_date>=?) AND (?='' OR reading_date<=?)
                ORDER BY saved_at DESC,id DESC""", (owner, start, start, end, end)).fetchall()
            found = []
            needle = normalize(keyword).casefold()
            from service_contract_repository import content_visible
            for row in rows:
                if not content_visible(db,owner,row["id"]): continue
                # List/search use contemporaneous input, not mutable current person data.
                form = json.loads(row["input_snapshot"])["form"]
                names = [form.get(k, "") for k in ("surname", "givenName", "surnameKana", "givenNameKana")]
                haystacks = names + [names[0]+names[1], names[0]+" "+names[1], names[2]+names[3], form["birthDate"]]
                if needle and not any(needle in normalize(h).casefold() for h in haystacks):
                    continue
                found.append({k: row[k] for k in ("id", "person_id", "group_id", "reading_date", "saved_at")} |
                             {"name": (names[0]+names[1]).strip() or "無記名", "birth_date": form["birthDate"]})
            return found

    def update_memo(self, owner, reading_id, memo, expected_updated_at):
        with self.connection() as db:
            self.reading(db, owner, reading_id)
            updated = db.execute("""UPDATE readings SET memo=?,updated_at=?
                WHERE owner_user_id=? AND id=? AND deleted_at IS NULL AND updated_at=?""",
                (memo, timestamp(), owner, reading_id, expected_updated_at))
            if updated.rowcount != 1:
                raise HistoryError("別の画面で変更されています。履歴を開き直して確認してください。", 409)
            return self.reading(db, owner, reading_id)

    def soft_delete(self, owner, reading_id):
        with self.connection() as db:
            self.reading(db, owner, reading_id)
            now = timestamp()
            db.execute("UPDATE readings SET deleted_at=?,updated_at=? WHERE owner_user_id=? AND id=?",
                       (now, now, owner, reading_id))

    def update_person(self, owner, person_id, snapshot):
        form = snapshot["form"]
        with self.connection() as db:
            self.person(db, owner, person_id)
            db.execute("""UPDATE persons SET surname=?,given_name=?,surname_kana=?,given_name_kana=?,
                normalized_surname=?,normalized_given_name=?,birth_date=?,current_input=?,updated_at=?
                WHERE owner_user_id=? AND id=?""", (
                form.get("surname", ""), form.get("givenName", ""), form.get("surnameKana", ""),
                form.get("givenNameKana", ""), normalize(form.get("surname", "")),
                normalize(form.get("givenName", "")), form["birthDate"], encode(snapshot),
                timestamp(), owner, person_id))

    def current_person(self, owner, person_id):
        with self.connection() as db:
            return json.loads(self.person(db, owner, person_id)["current_input"])

    @staticmethod
    def recovery_window(deleted_at, now):
        try:
            deleted=datetime.fromisoformat(deleted_at)
            if deleted.tzinfo is None or now.tzinfo is None: raise ValueError()
        except (ValueError, TypeError):
            raise HistoryError("履歴の削除日時を確認できません。",503) from None
        deadline=deleted+timedelta(days=30)
        return deleted<=now<deadline,deadline

    def deleted_list(self, owner, now=None):
        now=now or datetime.now(timezone.utc)
        with self.connection() as db:
            rows=db.execute("SELECT * FROM readings WHERE owner_user_id=? AND deleted_at IS NOT NULL ORDER BY deleted_at DESC,id DESC",(owner,)).fetchall()
            result=[]
            from service_contract_repository import content_visible
            for row in rows:
                if not content_visible(db,owner,row["id"],now): continue
                recoverable,deadline=self.recovery_window(row["deleted_at"],now)
                if not recoverable: continue
                form=json.loads(row["input_snapshot"])["form"]
                result.append({"id":row["id"],"name":(form.get("surname","")+form.get("givenName","")).strip() or "無記名",
                    "birth_date":form["birthDate"],"reading_date":row["reading_date"],"saved_at":row["saved_at"],
                    "deleted_at":row["deleted_at"],"restore_until":deadline.astimezone(timezone.utc).isoformat(timespec="microseconds")})
            return result

    def restore(self, owner, reading_id, now=None):
        now=now or datetime.now(timezone.utc)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT deleted_at FROM readings WHERE owner_user_id=? AND id=? AND deleted_at IS NOT NULL",(owner,reading_id)).fetchone()
            from service_contract_repository import content_visible
            if not content_visible(db,owner,reading_id,now): raise HistoryError("復旧可能な鑑定履歴が見つかりません。",404)
            if not row or not self.recovery_window(row["deleted_at"],now)[0]:
                raise HistoryError("復旧可能な鑑定履歴が見つかりません。",404)
            db.execute("UPDATE readings SET deleted_at=NULL,updated_at=? WHERE owner_user_id=? AND id=?",
                       (now.astimezone(timezone.utc).isoformat(timespec="microseconds"),owner,reading_id))
            return {"restored":True}

    def deletion_candidates(self, owner, now=None):
        """Read-only candidates. Physical deletion requires a separate source-FK policy."""
        now=now or datetime.now(timezone.utc)
        with self.connection() as db:
            result=[]
            for row in db.execute("SELECT id,deleted_at FROM readings WHERE owner_user_id=? AND deleted_at IS NOT NULL",(owner,)):
                _,deadline=self.recovery_window(row["deleted_at"],now)
                if deadline<=now:
                    dependent=db.execute("SELECT 1 FROM readings WHERE owner_user_id=? AND source_reading_id=? LIMIT 1",(owner,row["id"])).fetchone()
                    result.append({"id":row["id"],"has_dependents":bool(dependent)})
            return result
