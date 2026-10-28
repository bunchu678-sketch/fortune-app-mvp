"""F03: synthetic real ASGI entrance, current contracts and server-owned class scopes."""
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]
import json,os,time,unittest
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from uuid import uuid4
import product_api_cases as base
from auth_service import token_hash
from deployment_boundary import DeploymentBoundary
from history_repository import HistoryError,timestamp
from report_export_service import export_tokens,render_xlsx


class SecurityScopeCases(unittest.TestCase):
    setUpClass=classmethod(base.ProductAPICases.setUpClass.__func__)
    call=base.ProductAPICases.call
    data=base.ProductAPICases.data
    fortune=base.ProductAPICases.fortune

    def setUp(self):
        base.api_app.cache_clear();self.addCleanup(base.api_app.cache_clear)
        base.ProductAPICases.setUp(self)
        self.scoped=self.history.create(self.ids['student'],self.payload(self.org),organization_id=self.org)
        self.inner=self.app
        self.surface=patch.dict(os.environ,{'FORTUNE_DEPLOYMENT_SURFACE':'teacher'});self.surface.start()
        self.app=DeploymentBoundary(self.inner,'teacher')
        self.app_patch.stop()
        self.app_patch=patch('auth_cases.api_app',side_effect=lambda:self.app);self.app_patch.start()
        with export_tokens.lock:export_tokens.entries.clear()
        self.token=export_tokens.issue(self.ids['student'],base.FORM,self.result,token_hash(self.cookies['student']),self.org)
        with self.auth.connection() as db:self.schema=[tuple(r) for r in db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY type,name')]

    def tearDown(self):
        self.surface.stop();base.ProductAPICases.tearDown(self)

    def payload(self,org=None):
        return {'input_snapshot':{'form':base.FORM},'result_snapshot':deepcopy(self.result),'link':{'mode':'new_person'},**({'organization_id':org} if org else {})}

    def use(self,surface):
        os.environ['FORTUNE_DEPLOYMENT_SURFACE']=surface;self.app=DeploymentBoundary(self.inner,surface)

    def state(self,state):
        owner=self.ids['student']
        if state in ('suspended','arrears'):self.ops.services.suspend(self.ids['admin'],self.org,owner)
        elif state=='terminated':
            with self.auth.connection() as db:
                self.ops.services.ensure(db,self.org,owner,datetime.now(timezone.utc))
                db.execute('UPDATE service_contract_terms SET access_ends_at=? WHERE organization_id=? AND user_id=?',((datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(),self.org,owner))
        elif state=='revoked':
            with self.auth.connection() as db:db.execute("UPDATE memberships SET role='revoked' WHERE organization_id=? AND user_id=?",(self.org,owner))
        elif state=='account_suspended':self.ops.transition(self.ids['admin'],owner,'suspend')
        elif state in ('trial','trial_ended'):
            with self.auth.connection() as db:
                db.execute('DELETE FROM user_service_contracts WHERE organization_id=? AND user_id=?',(self.org,owner))
                db.execute('INSERT INTO user_initial_setup(user_id,completed_at) VALUES (?,?)',(owner,timestamp()))
                db.execute('''INSERT INTO initial_invitations(id,organization_id,user_id,alias,role,purpose,delivery_state,created_at,updated_at,cancelled_at)
                    VALUES (?,?,?,?,?,'free_trial','provider_accepted',?,?,?)''',(str(uuid4()),self.org,owner,'synthetic trial','student',timestamp(),timestamp(),timestamp() if state=='trial_ended' else None))

    def matrix(self,state):
        self.state(state);active=state in ('active','trial')
        expected=200 if active else 401 if state=='account_suspended' else 403
        status=self.fortune()[0];self.assertEqual(status,expected,(state,'fortune'))
        actions=[('POST','/api/history',self.payload(self.org)),
                 ('PATCH',f"/api/history/{self.scoped['id']}/memo",{'memo':'synthetic memo','updated_at':self.scoped['updated_at']}),
                 ('POST',f"/api/history/persons/{self.scoped['person_id']}",{'form':base.FORM}),
                 ('POST',f"/api/history/{self.scoped['id']}/rerun",{'mode':'new_group'}),
                 ('POST','/api/history/candidates',{**base.FORM,'organization_id':self.org}),
                 ('POST','/api/export/excel',{'export_token':self.token})]
        for method,path,body in actions:
            with self.subTest(state=state,path=path):self.assertEqual(self.call(method,path,body)[0],expected)
        # The existing viewing rule is observed, not selected as new product policy.
        try:self.history.detail(self.ids['student'],self.scoped['id']);old_status=200
        except HistoryError as exc:old_status=exc.status
        self.assertEqual(self.call('GET',f"/api/history/{self.scoped['id']}")[0],401 if state=='account_suspended' else old_status)
        delete_status=self.call('DELETE',f"/api/history/{self.scoped['id']}")[0]
        self.assertEqual(delete_status,expected)
        if active:self.assertEqual(self.call('POST',f"/api/history/{self.scoped['id']}/restore",{})[0],200)
        else:
            with self.auth.connection() as db:db.execute('UPDATE readings SET deleted_at=? WHERE id=?',(timestamp(),self.scoped['id']))
            self.assertEqual(self.call('POST',f"/api/history/{self.scoped['id']}/restore",{})[0],expected)
        with self.auth.connection() as db:self.assertEqual(self.schema,[tuple(r) for r in db.execute('SELECT type,name,sql FROM sqlite_master ORDER BY type,name')])

    def test_unscoped_fortune_all_roles_and_slash_are_404(self):
        for who in (None,'student','teacher','admin','other','b2c'):
            for path in ('/api/fortune','/api/fortune/'):
                with self.subTest(who=who,path=path):self.assertEqual(self.call('POST',path,base.FORM,who=who)[0],404)

    def test_unscoped_save_and_b2c_rows_cannot_be_changed_in_teacher(self):
        for who in ('student','teacher','admin','other','b2c'):
            self.assertEqual(self.call('POST','/api/history',self.payload(),who=who)[0],422)
        self.assertEqual(self.call('PATCH',f"/api/history/{self.reading['id']}/memo",{'memo':'x','updated_at':self.reading['updated_at']})[0],403)
        self.assertEqual(self.call('POST','/api/export/excel',{'reading_id':self.reading['id']})[0],403)
        self.assertEqual(self.call('POST','/api/history/candidates',base.FORM)[0],422)

    def test_current_owner_and_cross_class_ids_are_checked(self):
        for who in (None,'teacher','admin','other','b2c'):
            expected=401 if who is None else 404
            for method,path,body in [('GET',f"/api/history/{self.scoped['id']}",None),('PATCH',f"/api/history/{self.scoped['id']}/memo",{'memo':'x','updated_at':self.scoped['updated_at']}),('POST','/api/export/excel',{'reading_id':self.scoped['id']})]:
                self.assertEqual(self.call(method,path,body,who=who)[0],expected,(who,path))
        self.assertEqual(self.fortune(org=self.second)[0],404)

    def test_one_suspended_class_does_not_disable_other_class_or_combined_b2c(self):
        self.ops.assign(self.ids['admin'],self.second,self.ids['student'],'student',True,2000)
        self.state('suspended');self.assertEqual(self.fortune()[0],403);self.assertEqual(self.fortune(org=self.second)[0],200)
        self.assertEqual(self.call('POST','/api/history',self.payload(self.second))[0],200)
        self.assertEqual(self.call('POST','/api/export/excel',{'export_token':self.token})[0],403)
        self.use('combined')
        self.assertEqual(self.call('POST','/api/fortune',base.FORM)[0],200)
        self.assertEqual(self.call('POST','/api/history',self.payload())[0],200)
        self.assertEqual(self.call('POST','/api/export/excel',{'reading_id':self.reading['id']})[0],200)

    def test_cross_class_person_group_source_links_refused_even_if_both_active(self):
        self.ops.assign(self.ids['admin'],self.second,self.ids['student'],'student',True,2000)
        for mode in ('new_group','existing_group'):
            p=self.payload(self.second);p['link']={'mode':mode,'person_id':self.scoped['person_id'],'group_id':self.scoped['group_id'],'source_reading_id':self.scoped['id']}
            self.assertEqual(self.call('POST','/api/history',p)[0],404)
        p=self.payload(self.second);p['link']={'mode':'new_group','person_id':self.scoped['person_id']}
        self.assertEqual(self.call('POST','/api/history',p)[0],404)
        candidates=self.data('POST','/api/history/candidates',{**base.FORM,'organization_id':self.second})
        self.assertEqual(candidates,[])

    def test_teacher_own_history_and_collaboration_end_preserve_student_access(self):
        self.ops.teacher_contract(self.ids['admin'],self.org,'terminated')
        self.assertEqual(self.fortune()[0],200)
        self.assertEqual(self.fortune(who='teacher')[0],200)
        value=self.data('POST','/api/history',self.payload(self.org),who='teacher')
        self.assertEqual(self.call('POST','/api/export/excel',{'reading_id':value['id']},who='teacher')[0],200)
        self.assertEqual(self.call('GET',f"/api/history/{self.scoped['id']}",who='teacher')[0],404)

    def test_admin_boundary_stays_closed_and_combined_anonymous_calculation_survives(self):
        self.use('admin')
        for method,path,p in [('POST','/api/fortune',base.FORM),('GET','/api/history',None),('POST','/api/export/excel',{'export_token':self.token})]:self.assertEqual(self.call(method,path,p,who='admin')[0],404)
        self.use('combined');self.assertEqual(self.call('POST','/api/fortune',base.FORM,who=None)[0],200)

    def test_token_owner_session_old_format_expiry_restart_and_reuse(self):
        self.assertEqual(self.call('POST','/api/export/excel',{'export_token':self.token},who='other')[0],404)
        original=self.cookies['student'];self.cookies['student']=self.auth.login('student@example.test',base.PASSWORD)[1]
        self.assertEqual(self.call('POST','/api/export/excel',{'export_token':self.token})[0],404);self.cookies['student']=original
        for _ in range(2):self.assertEqual(self.call('POST','/api/export/excel',{'export_token':self.token})[0],200)
        with export_tokens.lock:export_tokens.entries[self.token]=export_tokens.entries[self.token][:5]
        self.assertEqual(self.call('POST','/api/export/excel',{'export_token':self.token})[0],403)
        self.use('combined');self.assertEqual(self.call('POST','/api/export/excel',{'export_token':self.token})[0],200)
        with export_tokens.lock:export_tokens.entries[self.token]=(0,*export_tokens.entries[self.token][1:])
        self.assertEqual(self.call('POST','/api/export/excel',{'export_token':self.token})[0],404)
        with export_tokens.lock:export_tokens.entries.clear()
        self.assertEqual(self.call('POST','/api/export/excel',{'export_token':self.token})[0],404)

    def test_new_tokens_carry_class_and_reject_after_membership_change(self):
        status,_,body=self.fortune();self.assertEqual(status,200);token=json.loads(body)['excel_export_token']
        self.assertEqual(export_tokens.source(self.ids['student'],token,token_hash(self.cookies['student']))[2],self.org)
        self.state('revoked');self.assertEqual(self.call('POST','/api/export/excel',{'export_token':token})[0],403)

    def test_reading_and_token_pdf_authorization_precedes_converter(self):
        class Converter:
            def convert(self,body):return b'%PDF-synthetic'
        with patch('report_pdf.get_pdf_converter',return_value=Converter()) as converter:
            for source in ({'reading_id':self.scoped['id']},{'export_token':self.token}):self.assertEqual(self.call('POST','/api/export/pdf',source)[0],200)
            converter.reset_mock();self.state('suspended')
            for source in ({'reading_id':self.scoped['id']},{'export_token':self.token}):self.assertEqual(self.call('POST','/api/export/pdf',source)[0],403)
            converter.assert_not_called()

    def test_contract_change_during_xlsx_render_rechecks_before_response(self):
        def changed(report):
            body=render_xlsx(report);self.state('suspended');return body
        with patch('report_export_service.render_xlsx',side_effect=changed):self.assertEqual(self.call('POST','/api/export/excel',{'export_token':self.token})[0],403)

    def test_contract_change_during_pdf_conversion_rechecks_before_response(self):
        outer=self
        class Converter:
            def convert(self,body):outer.state('suspended');return b'%PDF-synthetic'
        with patch('report_pdf.get_pdf_converter',return_value=Converter()):self.assertEqual(self.call('POST','/api/export/pdf',{'export_token':self.token})[0],403)

    def test_mutations_remain_blocked_after_repository_precheck(self):
        # Actual write transaction revalidates, even if an API precheck had passed.
        self.ops.context(self.org,self.ids['student']);self.state('suspended')
        self.assertEqual(self.call('PATCH',f"/api/history/{self.scoped['id']}/memo",{'memo':'x','updated_at':self.scoped['updated_at']})[0],403)


for _state in ('active','trial','trial_ended','suspended','arrears','terminated','revoked','account_suspended'):
    setattr(SecurityScopeCases,'test_matrix_'+_state,lambda self,state=_state:self.matrix(state))

if __name__=='__main__':unittest.main()
