"""Synthetic ASGI separation; no production configuration or live mail."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parent))
import os,json,unittest
from unittest.mock import patch
import invitation_cases as invitations
import product_api_cases as api
from deployment_boundary import DeploymentBoundary
from password_reset_service import PasswordResetService
from mail_delivery import MemoryMailTransport


class AdminDomainCases(unittest.TestCase):
    call=api.ProductAPICases.call
    data=api.ProductAPICases.data
    tearDown=api.ProductAPICases.tearDown
    @classmethod
    def setUpClass(cls):api.ProductAPICases.setUpClass.__func__(cls)

    def setUp(self):
        api.api_app.cache_clear()
        self.addCleanup(api.api_app.cache_clear)
        invitations.InvitationCases.setUp(self)

    def use_surface(self,surface):
        self.app_patch.stop()
        api.api_app.cache_clear()
        with patch.dict(os.environ,{'FORTUNE_DEPLOYMENT_SURFACE':surface}):self.app=api.api_app()
        self.app.state.password_reset_service=self.service
        self.app_patch=patch('auth_cases.api_app',return_value=self.app)
        self.app_patch.start()

    def test_teacher_process_refuses_management_even_for_valid_operator(self):
        self.use_surface('teacher')
        for who in ('admin','teacher',None):
            for path in ('/api/operations/invitations','/api/operations/users'):
                status,headers,_=self.call('GET',path,who=who)
                self.assertEqual(status,404);self.assertEqual(headers[b'cache-control'],b'no-store')
        self.assertEqual(self.call('GET',f'/api/b2b/organizations/{self.org}/me',who='teacher')[0],200)

    def test_admin_process_keeps_operator_authorization_and_refuses_readings(self):
        self.use_surface('admin')
        self.assertEqual(self.call('GET','/api/operations/invitations',who='admin')[0],200)
        for who in ('teacher','student'):
            self.assertEqual(self.call('GET','/api/operations/invitations',who=who)[0],403)
        for path in ('/api/history',f'/api/b2b/organizations/{self.org}/me'):
            self.assertEqual(self.call('GET',path,who='admin')[0],404)
        self.assertEqual(self.call('GET','/api/account/summary',who='admin')[0],200)

    def test_admin_csrf_matches_admin_origin_only(self):
        self.use_surface('admin')
        os.environ['FORTUNE_PUBLIC_ORIGIN']='https://admin.example.test'
        body={'organization_id':self.org,'alias':'合成先生','role':'teacher','email':'new-teacher@example.test',
              'recipient_confirmed':True,'free_trial_confirmed':True}
        self.assertEqual(self.call('POST','/api/operations/invitations',body,'admin',origin='https://teacher.example.test')[0],403)
        self.assertEqual(self.call('POST','/api/operations/invitations',body,'admin',origin='https://admin.example.test')[0],200)

    def test_admin_login_cookie_remains_secure_and_host_only(self):
        self.use_surface('admin');os.environ['FORTUNE_PUBLIC_ORIGIN']='https://admin.example.test'
        status,headers,_=self.call('POST','/api/auth/login',{'email':'admin@example.test','password':api.PASSWORD},who=None,origin='https://admin.example.test')
        self.assertEqual(status,200)
        cookie=headers[b'set-cookie'].decode().lower()
        for attribute in ('secure','httponly','samesite=lax','path=/'):self.assertIn(attribute,cookie)
        self.assertNotIn('domain=',cookie)

    def test_invite_from_admin_completes_at_teacher_and_notifies_teacher_origin(self):
        os.environ['FORTUNE_PUBLIC_ORIGIN']='https://admin.example.test'
        admin_mail=MemoryMailTransport();teacher_mail=MemoryMailTransport()
        admin_service=PasswordResetService(self.auth,admin_mail,'https://admin.example.test')
        invite_service=PasswordResetService(self.auth,teacher_mail,'https://teacher.example.test')
        self.app.state.password_reset_service=admin_service;self.app.state.invitation_service=invite_service
        self.data('POST','/api/operations/invitations',{'organization_id':self.org,'alias':'任意の管理名42','role':'student','email':'new-student@example.test',
            'recipient_confirmed':True,'free_trial_confirmed':True},'admin',origin='https://admin.example.test')
        self.assertEqual(len(admin_mail.messages),0);self.assertEqual(len(teacher_mail.messages),1)
        message=teacher_mail.messages[0];self.assertIn('https://teacher.example.test/reset-password#token=',message.body)
        token=message.body.split('#token=')[1].split()[0]
        with patch.dict(os.environ,{'FORTUNE_PUBLIC_ORIGIN':'https://teacher.example.test'}):
            self.assertEqual(self.call('POST','/api/auth/password-reset/complete',{'token':token,'password':api.PASSWORD},who=None,origin='https://teacher.example.test')[0],200)
        self.assertEqual(self.data('GET','/api/operations/invitations',who='admin')[0]['setup_state'],'completed')

    def test_free_names_trim_and_invalid_names_or_duplicate_do_not_create_users(self):
        body={'organization_id':self.org,'alias':'  自由な管理名  ','role':'teacher','email':'free-name@example.test',
              'recipient_confirmed':True,'free_trial_confirmed':True}
        self.data('POST','/api/operations/invitations',body,'admin')
        self.assertEqual(self.data('GET','/api/operations/invitations',who='admin')[0]['alias'],'自由な管理名')
        for alias,expected in [(' ',422),('a'*65,422),('自由な管理名',409)]:
            self.assertEqual(self.call('POST','/api/operations/invitations',{**body,'alias':alias,'email':'must-not-exist@example.test'},'admin')[0],expected)
        with self.auth.connection() as db:self.assertEqual(db.execute("SELECT count(*) FROM users WHERE normalized_email='must-not-exist@example.test'").fetchone()[0],0)

    def test_invalid_surface_refused(self):
        with self.assertRaises(ValueError):DeploymentBoundary(self.app,'guess-from-host')


if __name__=='__main__':unittest.main()
