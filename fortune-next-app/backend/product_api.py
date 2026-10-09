"""Authenticated self, teacher and singleton-operator APIs with distinct projections."""
import json
import logging
import sqlite3
from fastapi import APIRouter,Request,BackgroundTasks
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from auth_service import AuthRepository,AuthError,COOKIE_NAME,database_path
from auth_api import csrf_check,safe_error
from history_repository import HistoryError
from operations_repository import OperationsRepository
from execution_repository import ExecutionRepository

router=APIRouter()


def identity(request):
    # B2B and management never accept development owner, supplied IDs or membership role as operator.
    token=request.cookies.get(COOKIE_NAME)
    if not token: raise AuthError("ログインしてください。",401)
    return AuthRepository().authenticate(token)


def repositories():
    operations=OperationsRepository(database_path())
    return operations,ExecutionRepository(operations)


async def payload(request):
    raw=bytearray()
    async for chunk in request.stream():
        if len(raw)+len(chunk)>16384: raise HistoryError("入力内容を確認してください。",422)
        raw.extend(chunk)
    value=json.loads(raw)
    if not isinstance(value,dict): raise HistoryError("入力内容を確認してください。",422)
    return value


async def handle(request,action,write=False):
    try:
        user=await run_in_threadpool(identity,request)
        if write:csrf_check(request)
        body=await payload(request) if write else None
        def run():
            operations,executions=repositories()
            if request.url.path.startswith("/api/operations/"):
                with operations.auth.connection() as db:operations.require_admin(db,user["id"])
            return action(operations,executions,user,body)
        value=await run_in_threadpool(run)
        return JSONResponse({"ok":True,"data":value},headers={"Cache-Control":"no-store"})
    except HistoryError as exc:
        return JSONResponse({"ok":False,"error":str(exc)},status_code=exc.status,headers={"Cache-Control":"no-store"})
    except (sqlite3.Error,OSError):
        logging.getLogger(__name__).error("Product storage unavailable")
        return safe_error(AuthError("保存先を利用できません。",503))
    except (ValueError,TypeError,KeyError):return safe_error(AuthError("入力内容を確認してください。",422))


@router.get("/api/account/summary")
async def personal(request:Request):
    return await handle(request,lambda o,e,u,p:{"email":u["email"],**o.access(u["id"]),**e.personal(u["id"])})


@router.get("/api/b2b/organizations/{org}/me")
async def membership_self(org:str,request:Request):
    def action(o,e,u,p):
        context=o.context(org,u["id"])
        return {"organization_id":org,"role":context.role,"branding":o.product.branding(org,u["id"]),**e.personal(u["id"],org)}
    return await handle(request,action)


@router.get("/api/b2b/organizations/{org}/teacher")
async def teacher(org:str,request:Request):
    return await handle(request,lambda o,e,u,p:{**o.teacher(org,u["id"]),**e.organization_totals(org)})


@router.get("/api/operations/organizations")
async def organizations(request:Request):
    return await handle(request,lambda o,e,u,p:[{**item,**e.organization_totals(item["id"])} for item in o.organizations(u["id"])])


@router.post("/api/operations/organizations")
async def organization_create(request:Request):
    return await handle(request,lambda o,e,u,p:o.create_organization(u["id"],p["display_name"],p["slug"]),True)


@router.get("/api/operations/organizations/{org}")
async def organization_detail(org:str,request:Request):
    return await handle(request,lambda o,e,u,p:{**o.organization(u["id"],org),**e.organization_totals(org)})


@router.patch("/api/operations/organizations/{org}")
async def organization_update(org:str,request:Request):
    return await handle(request,lambda o,e,u,p:o.update_organization(u["id"],org,p["display_name"],p.get("logo_reference")),True)


@router.post("/api/operations/organizations/{org}/teacher-contract")
async def teacher_contract(org:str,request:Request):
    return await handle(request,lambda o,e,u,p:o.teacher_contract(u["id"],org,p["state"],p.get("contract_id")),True)


@router.get("/api/operations/users")
async def users(request:Request):
    return await handle(request,lambda o,e,u,p:o.users(u["id"]))


@router.get("/api/operations/users/{owner}")
async def user_detail(owner:str,request:Request):
    return await handle(request,lambda o,e,u,p:{**o.user(u["id"],owner),**e.personal(owner)})


@router.patch("/api/operations/users/{owner}")
async def user_name(owner:str,request:Request):
    return await handle(request,lambda o,e,u,p:o.set_name(u["id"],owner,p["display_name"]),True)


@router.post("/api/operations/users/{owner}/membership")
async def membership(owner:str,request:Request):
    return await handle(request,lambda o,e,u,p:o.assign(u["id"],p["organization_id"],owner,p["role"],p.get("initial_payment_confirmed",False),p.get("monthly_fee"),activate_new=True),True)


@router.post("/api/operations/users/{owner}/suspend")
async def suspend(owner:str,request:Request):
    return await handle(request,lambda o,e,u,p:o.transition(u["id"],owner,"suspend"),True)


@router.post("/api/operations/users/{owner}/resume")
async def resume(owner:str,request:Request):
    return await handle(request,lambda o,e,u,p:o.transition(u["id"],owner,"resume"),True)


def invite_service(request):
    service=getattr(request.app.state,"password_reset_service",None)
    if service is None or service.mailer is None or service.public_origin is None:return None
    if service.repository.auth.path.resolve()!=database_path().resolve():raise AuthError("メール設定を確認してください。",503)
    return service


def queue_setup(o,actor,owner,email,service,background,ip):
    # Operator-only creation/resend; public reset remains enumeration-resistant.
    if service is None:return "disabled"
    normalized=service.admit_request(email,ip)
    with o.change(actor) as db:o.audit(db,actor,"setup-mail-request",owner)
    background.add_task(service.deliver,normalized)
    return "queued"


@router.post("/api/operations/users")
async def issue(request:Request,background:BackgroundTasks):
    def action(o,e,u,p):
        service=invite_service(request)
        issued=o.issue_account(u["id"],p["organization_id"],p["email"],p["display_name"],p.get("initial_payment_confirmed"),p.get("monthly_fee"))
        # A transient delivery/rate failure does not turn committed creation into an ambiguous error.
        try: status=queue_setup(o,u["id"],issued["id"],issued["email"],service,background,request.client.host if request.client else "unknown")
        except AuthError: status="unavailable"
        return {**issued,"mail_status":status}
    return await handle(request,action,True)


@router.post("/api/operations/users/{owner}/setup-mail")
async def setup_mail(owner:str,request:Request,background:BackgroundTasks):
    def action(o,e,u,p):
        target=o.user(u["id"],owner)
        if not target["setup_pending"]:raise HistoryError("初回設定は完了済みです。",409)
        if target["account_state"]!="active":raise HistoryError("利用者は停止中です。",409)
        return {"mail_status":queue_setup(o,u["id"],owner,target["email"],invite_service(request),background,request.client.host if request.client else "unknown")}
    return await handle(request,action,True)


@router.post("/api/operations/users/{owner}/dues")
async def due(owner:str,request:Request):
    return await handle(request,lambda o,e,u,p:o.record_due(u["id"],p["organization_id"],owner,p["due_date"],p["amount"]),True)


@router.post("/api/operations/users/{owner}/dues/{due_id}/settle")
async def settle(owner:str,due_id:str,request:Request):
    return await handle(request,lambda o,e,u,p:o.settle_due(u["id"],owner,due_id),True)


@router.get("/api/operations/audit")
async def audit(request:Request):
    return await handle(request,lambda o,e,u,p:o.audit_list(u["id"]))


@router.get('/api/account/organizations/{org}/contract')
async def own_contract(org:str,request:Request):
    return await handle(request,lambda o,e,u,p:o.services.summary(org,u['id']))


@router.post('/api/account/organizations/{org}/cancellation')
async def own_cancel(org:str,request:Request):
    return await handle(request,lambda o,e,u,p:o.services.cancel(u['id'],org),True)


@router.post('/api/account/organizations/{org}/data-recovery')
async def own_recovery(org:str,request:Request):
    return await handle(request,lambda o,e,u,p:o.services.recover(u['id'],org),True)


@router.get('/api/operations/users/{owner}/organizations/{org}/contract')
async def service_detail(owner:str,org:str,request:Request):
    return await handle(request,lambda o,e,u,p:{**o.services.summary(org,owner),
        'arrears':o.services.arrears(u['id'],org,owner),
        'deletion_plan':o.services.deletion_plan(u['id'],org,owner)})


@router.post('/api/operations/users/{owner}/organizations/{org}/contract/{action}')
async def service_action(owner:str,org:str,action:str,request:Request):
    def apply(o,e,u,p):
        if action=='activate':return o.services.activate(u['id'],org,owner)
        if action=='paid-period':return o.services.paid_period(u['id'],org,owner,p['paid_through'])
        if action=='suspend':return o.services.suspend(u['id'],org,owner)
        if action=='resume':return o.services.resume(u['id'],org,owner)
        if action=='cancellation':return o.services.cancel(owner,org,actor=u['id'])
        if action=='data-recovery':return o.services.recover(owner,org,actor=u['id'])
        raise HistoryError('操作を確認してください。',404)
    return await handle(request,apply,True)


@router.get('/api/operations/purchases')
async def purchases(request:Request):
    return await handle(request,lambda o,e,u,p:o.retention.purchases(u['id']))


@router.post('/api/operations/purchases')
async def register_purchase(request:Request):
    return await handle(request,lambda o,e,u,p:o.retention.register_purchase(u['id'],p['purchase_number'],p['organization_id'],p['purchased_on'],p['email'],p['payment_confirmed'],p['review_on'],p.get('user_id')),True)


@router.post('/api/operations/purchases/{number}/recontract')
async def recontract(number:str,request:Request):
    return await handle(request,lambda o,e,u,p:o.retention.recontract(u['id'],number,p['organization_id'],p['email'],p['display_name'],p.get('identity_verified'),p.get('monthly_payment_confirmed'),p['paid_through']),True)


@router.get('/api/operations/users/{owner}/retention')
async def user_retention(owner:str,request:Request):
    return await handle(request,lambda o,e,u,p:o.retention.user_plan(u['id'],owner))


@router.post('/api/operations/users/{owner}/b2c-retention')
async def confirm_b2c_retention(owner:str,request:Request):
    return await handle(request,lambda o,e,u,p:o.retention.confirm_b2c(u['id'],owner,p['state']),True)


@router.get('/api/operations/retention-reviews')
async def retention_reviews(request:Request):
    return await handle(request,lambda o,e,u,p:o.retention.retention_reviews(u['id']))


@router.post('/api/operations/retention-reviews/{kind}/{identifier}')
async def retention_review(kind:str,identifier:str,request:Request):
    return await handle(request,lambda o,e,u,p:o.retention.review(u['id'],kind,identifier,p['review_on'],p['basis']),True)
