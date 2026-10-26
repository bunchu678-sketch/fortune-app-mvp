"""Single-operator administration. Content-free projections and atomic audited writes."""
from contextlib import contextmanager, nullcontext
import json
import secrets
import sqlite3
from uuid import uuid4
from auth_schema import apply_migration, set_account_state
from auth_service import AuthError, normalized_email, password_hash
from history_repository import timestamp, encode, HistoryError
from product_repository import ProductRepository, text, day
from usage_repository import STATE
from billing_policy import resume_commitment
from account_lifecycle import utc

OPERATOR = "しぜんとらぼ"
BRAND = "博士の占いらぼ"


class OperationsRepository:
    def __init__(self, path):
        self.product = ProductRepository(path)
        self.auth = self.product.auth
        with self.auth.connection() as db:
            apply_migration(db, "product-operations-002", [
                """CREATE TABLE operating_administrator (singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    user_id TEXT NOT NULL UNIQUE REFERENCES users(id), granted_at TEXT NOT NULL)""",
                """CREATE TABLE user_profiles (user_id TEXT PRIMARY KEY REFERENCES users(id), display_name TEXT NOT NULL)""",
                """CREATE TABLE user_service_contracts (organization_id TEXT NOT NULL, user_id TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('active','suspended','terminated')),
                    initial_payment_confirmed INTEGER NOT NULL CHECK(initial_payment_confirmed IN (0,1)),
                    monthly_fee INTEGER CHECK(monthly_fee IS NULL OR monthly_fee>=0),
                    resumed_at TEXT, minimum_term_until TEXT, updated_at TEXT NOT NULL,
                    PRIMARY KEY(organization_id,user_id),
                    FOREIGN KEY(organization_id,user_id) REFERENCES memberships(organization_id,user_id))""",
                """CREATE TABLE manual_dues (id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, user_id TEXT NOT NULL,
                    due_date TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0),
                    confirmed_at TEXT NOT NULL, settled_at TEXT,
                    UNIQUE(organization_id,user_id,due_date),
                    FOREIGN KEY(organization_id,user_id) REFERENCES user_service_contracts(organization_id,user_id))""",
                """CREATE TABLE management_audit (id TEXT PRIMARY KEY, actor_user_id TEXT NOT NULL REFERENCES users(id),
                    action TEXT NOT NULL, target_id TEXT NOT NULL, organization_id TEXT, occurred_at TEXT NOT NULL)""",
                "CREATE INDEX audit_time ON management_audit(occurred_at)",
            ])

        from service_contract_repository import ServiceContractRepository
        self.services = ServiceContractRepository(self)
        from retention_repository import RetentionRepository
        self.retention = RetentionRepository(self)

    @staticmethod
    def require_admin(db, actor):
        row = db.execute("""SELECT u.id FROM operating_administrator a JOIN users u ON u.id=a.user_id
            LEFT JOIN user_account_lifecycle l ON l.user_id=u.id
            WHERE a.singleton=1 AND a.user_id=? AND u.status='active' AND COALESCE(l.state,'active')='active'
            AND NOT EXISTS(SELECT 1 FROM user_initial_setup i WHERE i.user_id=u.id AND i.completed_at IS NULL)""", (actor,)).fetchone()
        if not row:
            raise AuthError("運営権限がありません。", 403)

    @staticmethod
    def audit(db, actor, action, target, org=None):
        db.execute("INSERT INTO management_audit VALUES (?,?,?,?,?,?)",
                   (str(uuid4()), actor, action, target, org, timestamp()))

    @contextmanager
    def change(self, actor):
        with self.auth.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self.require_admin(db, actor)
            yield db

    def bootstrap(self, user_id):
        """Explicit local CLI only. Never assign the first signup, email, host or membership role."""
        with self.auth.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("""SELECT 1 FROM users u LEFT JOIN user_account_lifecycle l ON l.user_id=u.id
                WHERE u.id=? AND u.status='active' AND COALESCE(l.state,'active')='active'
                AND NOT EXISTS(SELECT 1 FROM user_initial_setup i WHERE i.user_id=u.id AND i.completed_at IS NULL)""", (user_id,)).fetchone():
                raise AuthError("利用可能な既存Userを指定してください。",422)
            old = db.execute("SELECT user_id FROM operating_administrator WHERE singleton=1").fetchone()
            if old:
                if old[0] == user_id: return
                raise AuthError("運営管理者は既に設定済みです。",409)
            db.execute("INSERT INTO operating_administrator VALUES (1,?,?)",(user_id,timestamp()))
            self.audit(db,user_id,"administrator-bootstrap",user_id)

    @staticmethod
    def member_access(db, org, owner):
        context = ProductRepository.context(db,org,owner)
        if context.role not in ("teacher","student"):
            raise AuthError("利用権限がありません。",403)
        if context.role == "student":
            row=db.execute("SELECT state,initial_payment_confirmed FROM user_service_contracts WHERE organization_id=? AND user_id=?",(org,owner)).fetchone()
            if not row or row["state"]!="active" or not row["initial_payment_confirmed"]:
                raise AuthError("利用契約を確認してください。",403)
            from service_contract_repository import terms, effective_state
            if effective_state(row['state'],terms(db,org,owner),None)!='active':
                raise AuthError('利用契約を確認してください。',403)
        # Teacher collaboration contract is deliberately NOT an access dependency.
        return context

    def context(self, org, owner):
        with self.auth.connection() as db: return self.member_access(db,org,owner)

    def access(self, owner):
        with self.auth.connection() as db:
            admin=db.execute("SELECT 1 FROM operating_administrator WHERE singleton=1 AND user_id=?",(owner,)).fetchone()
            memberships=[dict(r) for r in db.execute("""SELECT m.organization_id,m.role,o.display_name
                FROM memberships m JOIN organizations o ON o.id=m.organization_id
                WHERE m.user_id=? AND m.role IN ('student','teacher') ORDER BY o.display_name""",(owner,))]
            return {"operator":OPERATOR,"brand":BRAND,"is_operator":bool(admin),"memberships":memberships}

    def organizations(self, actor):
        with self.auth.connection() as db:
            self.require_admin(db,actor)
            return [dict(r) for r in db.execute("""SELECT o.id,o.display_name,o.slug,
                (SELECT count(*) FROM memberships m WHERE m.organization_id=o.id AND m.role='student') AS students
                FROM organizations o ORDER BY o.display_name""")]

    def organization(self, actor, org):
        with self.auth.connection() as db:
            self.require_admin(db,actor)
            value=self.product.organization(db,org)
            value["settings"]=json.loads(value.pop("settings_json"))
            value["teacher_contracts"]=[dict(r) for r in db.execute("SELECT id,state,start_date,end_date,plan FROM contracts WHERE organization_id=?",(org,))]
            value["members"]=[dict(r) for r in db.execute(f"""SELECT m.user_id,m.role,p.display_name,u.email,{STATE} AS account_state
                FROM memberships m JOIN users u ON u.id=m.user_id LEFT JOIN user_profiles p ON p.user_id=u.id
                LEFT JOIN user_account_lifecycle l ON l.user_id=u.id WHERE m.organization_id=? ORDER BY u.created_at""",(org,))]
            return value

    def create_organization(self, actor, display_name, slug):
        with self.change(actor) as db:
            value=self.product.create_organization(display_name,slug,connection=db)
            self.audit(db,actor,"organization-create",value["id"],value["id"])
            return value

    def update_organization(self, actor, org, display_name, logo_reference=None):
        display_name=text(display_name)
        if logo_reference is not None: logo_reference=text(logo_reference,2048)
        with self.change(actor) as db:
            self.product.organization(db,org)
            db.execute("UPDATE organizations SET display_name=?,logo_reference=?,updated_at=? WHERE id=?",(display_name,logo_reference,timestamp(),org))
            self.audit(db,actor,"organization-update",org,org)

    @staticmethod
    def membership(db, org, owner, role, payment_confirmed, monthly_fee):
        if role not in ("teacher","student"): raise HistoryError("所属区分を確認してください。",422)
        if type(payment_confirmed) is not bool: raise HistoryError("入金確認状態を確認してください。",422)
        if monthly_fee is not None and (type(monthly_fee) is not int or monthly_fee<0): raise HistoryError("月額費用を確認してください。",422)
        if not db.execute("SELECT 1 FROM memberships WHERE organization_id=? AND user_id=?",(org,owner)).fetchone():
            raise HistoryError("所属が見つかりません。",404)
        db.execute("UPDATE memberships SET role=?,updated_at=? WHERE organization_id=? AND user_id=?",(role,timestamp(),org,owner))
        if role=="student":
            db.execute("""INSERT INTO user_service_contracts VALUES (?,?, 'active',?,?,NULL,NULL,?)
                ON CONFLICT(organization_id,user_id) DO UPDATE SET initial_payment_confirmed=excluded.initial_payment_confirmed,
                monthly_fee=excluded.monthly_fee,updated_at=excluded.updated_at""",(org,owner,int(payment_confirmed),monthly_fee,timestamp()))

    def assign(self, actor, org, owner, role, payment_confirmed=False, monthly_fee=None, *, activate_new=False):
        with self.change(actor) as db:
            self.product.organization(db,org)
            previous=db.execute("SELECT initial_payment_confirmed FROM user_service_contracts WHERE organization_id=? AND user_id=?",(org,owner)).fetchone()
            exists=db.execute("SELECT 1 FROM memberships WHERE organization_id=? AND user_id=?",(org,owner)).fetchone()
            if not exists: self.product.add_membership(org,owner,role,connection=db)
            self.membership(db,org,owner,role,payment_confirmed,monthly_fee)
            if activate_new and role=='student' and payment_confirmed and (not previous or not previous[0]):
                # A new server-side grant to an existing ready User is an actual eligibility event.
                ready=db.execute("""SELECT 1 FROM users u LEFT JOIN user_account_lifecycle l ON l.user_id=u.id
                    WHERE u.id=? AND u.status='active' AND COALESCE(l.state,'active')='active'
                    AND NOT EXISTS(SELECT 1 FROM user_initial_setup i WHERE i.user_id=u.id AND i.completed_at IS NULL)""",(owner,)).fetchone()
                if ready:
                    from service_contract_repository import mark_activation
                    mark_activation(db,org,owner,utc(None))
                    self.audit(db,actor,'service-grant-activate',owner,org)
                elif db.execute("SELECT 1 FROM user_initial_setup i JOIN users u ON u.id=i.user_id WHERE i.user_id=? AND i.completed_at IS NULL AND u.status='active'",(owner,)).fetchone():
                    self.services.ensure(db,org,owner,utc(None))
                    db.execute('UPDATE service_contract_terms SET awaiting_initial_setup=1 WHERE organization_id=? AND user_id=? AND activated_at IS NULL AND cancellation_requested_at IS NULL AND suspended_at IS NULL',(org,owner))
            self.audit(db,actor,"membership-set",owner,org)

    def issue_account(self, actor, org, email, display_name, payment_confirmed, monthly_fee=None, *, connection=None):
        if payment_confirmed is not True: raise HistoryError("入金確認後に発行してください。",422)
        normalized=normalized_email(email); name=text(display_name); encoded=password_hash(secrets.token_urlsafe(48))
        owner=str(uuid4()); now=timestamp()
        try:
            with nullcontext(connection) if connection is not None else self.change(actor) as db:
                self.require_admin(db,actor)
                self.product.organization(db,org)
                db.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)",(owner,email.strip(),normalized,encoded,"active",now,now))
                db.execute("INSERT INTO user_profiles VALUES (?,?)",(owner,name))
                db.execute("INSERT INTO user_initial_setup VALUES (?,NULL)",(owner,))
                self.product.add_membership(org,owner,"student",connection=db)
                self.membership(db,org,owner,"student",True,monthly_fee)
                db.execute("INSERT INTO service_contract_terms(organization_id,user_id,awaiting_initial_setup,updated_at) VALUES (?,?,1,?)",(org,owner,now))
                self.audit(db,actor,"account-issue",owner,org)
        except sqlite3.IntegrityError: raise HistoryError("同じメールアドレスは登録済みです。",409) from None
        return {"id":owner,"email":email.strip(),"setup_pending":True}

    def users(self, actor):
        with self.auth.connection() as db:
            self.require_admin(db,actor)
            return [dict(r) for r in db.execute(f"""SELECT u.id,u.email,p.display_name,{STATE} AS account_state
                FROM users u LEFT JOIN user_profiles p ON p.user_id=u.id LEFT JOIN user_account_lifecycle l ON l.user_id=u.id
                ORDER BY u.created_at DESC""")]

    def user(self, actor, owner):
        with self.auth.connection() as db:
            self.require_admin(db,actor)
            row=db.execute(f"""SELECT u.id,u.email,p.display_name,{STATE} AS account_state,a.last_login_at,
                i.completed_at,CASE WHEN i.user_id IS NOT NULL AND i.completed_at IS NULL THEN 1 ELSE 0 END AS setup_pending,
                l.suspended_at,l.deletion_pending_at FROM users u LEFT JOIN user_profiles p ON p.user_id=u.id
                LEFT JOIN user_account_lifecycle l ON l.user_id=u.id LEFT JOIN user_activity a ON a.user_id=u.id
                LEFT JOIN user_initial_setup i ON i.user_id=u.id WHERE u.id=?""",(owner,)).fetchone()
            if not row: raise HistoryError("利用者が見つかりません。",404)
            value=dict(row)
            value["memberships"]=[dict(r) for r in db.execute("""SELECT m.organization_id,m.role,o.display_name,c.state AS contract_state,
                c.initial_payment_confirmed,c.monthly_fee,c.minimum_term_until FROM memberships m JOIN organizations o ON o.id=m.organization_id
                LEFT JOIN user_service_contracts c ON c.organization_id=m.organization_id AND c.user_id=m.user_id WHERE m.user_id=?""",(owner,))]
            value["service_contracts"]=[self.services.summary(m["organization_id"],owner,connection=db) for m in value["memberships"] if m["role"]=="student"]
            value["dues"]=[dict(r) for r in db.execute("SELECT id,organization_id,due_date,amount,confirmed_at,settled_at FROM manual_dues WHERE user_id=? ORDER BY due_date",(owner,))]
            return value

    def set_name(self, actor, owner, display_name):
        with self.change(actor) as db:
            if not db.execute("SELECT 1 FROM users WHERE id=?",(owner,)).fetchone(): raise HistoryError("利用者が見つかりません。",404)
            db.execute("INSERT INTO user_profiles VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET display_name=excluded.display_name",(owner,text(display_name)))
            self.audit(db,actor,"user-name-set",owner)

    def transition(self, actor, owner, action, now=None):
        if action not in ("suspend","resume"): raise HistoryError("状態操作を確認してください。",422)
        instant=utc(now); stamp=instant.isoformat(timespec="microseconds")
        with self.change(actor) as db:
            if owner==actor: raise HistoryError("運営管理者自身は停止・再開できません。",409)
            if not db.execute("SELECT 1 FROM users WHERE id=?",(owner,)).fetchone(): raise HistoryError("利用者が見つかりません。",404)
            if action=="resume" and db.execute("SELECT 1 FROM manual_dues WHERE user_id=? AND settled_at IS NULL",(owner,)).fetchone():
                raise HistoryError("未納分の全額精算を確認してから再開してください。",409)
            set_account_state(db,owner,"suspended" if action=="suspend" else "active",stamp)
            db.execute("UPDATE users SET status=?,updated_at=? WHERE id=?",("disabled" if action=="suspend" else "active",stamp,owner))
            db.execute("UPDATE auth_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL",(stamp,owner))
            if action=="suspend":
                db.execute("UPDATE user_service_contracts SET state='suspended',updated_at=? WHERE user_id=? AND state='active'",(stamp,owner))
            else:
                db.execute("""UPDATE user_service_contracts SET state='active',resumed_at=?,minimum_term_until=?,updated_at=?
                    WHERE user_id=? AND state='suspended'""",(stamp,resume_commitment(instant).isoformat(timespec="microseconds"),stamp,owner))
            self.audit(db,actor,"account-"+action,owner)

    def record_due(self, actor, org, owner, due_date, amount):
        due_date=day(due_date)
        if due_date is None or type(amount) is not int or amount<=0: raise HistoryError("未納記録を確認してください。",422)
        with self.change(actor) as db:
            contract=db.execute("SELECT state FROM user_service_contracts WHERE organization_id=? AND user_id=?",(org,owner)).fetchone()
            if not contract: raise HistoryError("利用契約が見つかりません。",404)
            from service_contract_repository import terms, effective_state, moment
            from billing_policy import JST, first_billing_date
            from datetime import date
            value=terms(db,org,owner)
            if date.fromisoformat(due_date)>utc(None).astimezone(JST).date():
                raise HistoryError('将来の期日を未納として記録できません。',422)
            if value and value['paid_through'] and due_date<=value['paid_through']:
                raise HistoryError('支払済み期間を未納として記録できません。',409)
            if effective_state(contract[0],value,utc(None))!='active':
                raise HistoryError('休止・利用終了後に新しい月額料金を記録できません。',409)
            from billing_policy import paid_access_end
            from datetime import timedelta
            anchor=paid_access_end(date.fromisoformat(due_date)-timedelta(days=1))
            for pause in db.execute('SELECT started_at,ended_at FROM service_suspensions WHERE organization_id=? AND user_id=?',(org,owner)):
                if moment(pause['started_at'])<=anchor and (not pause['ended_at'] or anchor<moment(pause['ended_at'])):
                    raise HistoryError('休止期間の月額料金は記録できません。',422)
            if value and value['activated_at']:
                due=date.fromisoformat(due_date)
                if due.day!=1 or due<first_billing_date(moment(value['activated_at'])) or due>utc(None).astimezone(JST).date():
                    raise HistoryError('初月・将来・起算日前の未納は記録できません。',422)
            if contract[0]!="active": raise HistoryError("休止中に新しい月額料金を記録できません。",409)
            value=str(uuid4())
            try: db.execute("INSERT INTO manual_dues VALUES (?,?,?,?,?,?,NULL)",(value,org,owner,due_date,amount,timestamp()))
            except sqlite3.IntegrityError: raise HistoryError("同じ期日の未納記録が存在します。",409) from None
            self.audit(db,actor,"arrears-record",value,org)
            return {"id":value}

    def settle_due(self, actor, owner, due_id):
        with self.change(actor) as db:
            row=db.execute("SELECT organization_id,settled_at FROM manual_dues WHERE id=? AND user_id=?",(due_id,owner)).fetchone()
            if not row: raise HistoryError("未納記録が見つかりません。",404)
            if row["settled_at"]: return
            db.execute("UPDATE manual_dues SET settled_at=? WHERE id=?",(timestamp(),due_id))
            self.audit(db,actor,"arrears-settle",due_id,row["organization_id"])

    def teacher(self, org, owner):
        with self.auth.connection() as db:
            context=self.member_access(db,org,owner)
            if context.role!="teacher": raise AuthError("先生用の権限がありません。",403)
            name=self.product.organization(db,org)["display_name"]
            students=[dict(r) for r in db.execute(f"""SELECT m.user_id,COALESCE(p.display_name,'氏名未登録') AS display_name,{STATE} AS account_state
                FROM memberships m JOIN users u ON u.id=m.user_id LEFT JOIN user_profiles p ON p.user_id=u.id
                LEFT JOIN user_account_lifecycle l ON l.user_id=u.id WHERE m.organization_id=? AND m.role='student'
                ORDER BY m.created_at""",(org,))]
            from service_contract_repository import terms, effective_state
            scoped_states={r['user_id']:effective_state(r['state'],terms(db,org,r['user_id']),None) for r in db.execute('SELECT user_id,state FROM user_service_contracts WHERE organization_id=?',(org,))}
            for student in students:
                student_owner=student.pop('user_id')
                if student['account_state']=='active': student['account_state']=scoped_states.get(student_owner,'active')
            return {"organization_id":org,"display_name":name,"students":students}

    def teacher_contract(self, actor, org, state, contract_id=None):
        with self.change(actor) as db:
            if contract_id:
                self.product.set_contract_state(org,contract_id,state,connection=db)
            else:
                contract_id=self.product.create_contract(org,state,connection=db)
            self.audit(db,actor,"teacher-contract-set",contract_id,org)
            return {"id":contract_id,"state":state}

    def audit_list(self, actor):
        with self.auth.connection() as db:
            self.require_admin(db,actor)
            return [dict(r) for r in db.execute("SELECT * FROM management_audit ORDER BY occurred_at DESC LIMIT 200")]
