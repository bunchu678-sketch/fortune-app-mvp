"""Synthetic recipients and memory mail only; no live accounts or SMTP."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parent))
import json,time,unittest
from unittest.mock import patch
import product_api_cases as api
from auth_service import AuthError
from mail_delivery import MemoryMailTransport
from password_reset_service import PasswordResetService,RESET_TTL_SECONDS


class InvitationCases(unittest.TestCase):
    call=api.ProductAPICases.call
    data=api.ProductAPICases.data
    tearDown=api.ProductAPICases.tearDown
    @classmethod
    def setUpClass(cls):api.ProductAPICases.setUpClass.__func__(cls)
    def setUp(self):
        api.ProductAPICases.setUp(self)
        self.now=time.time();self.mail=MemoryMailTransport()
        self.service=PasswordResetService(self.auth,self.mail,'https://app.example.test',clock=lambda:self.now)
        self.app.state.password_reset_service=self.service
    def invite(self,role='student',alias='synthetic-student',email='invite@example.test',**changes):
        body={'organization_id':self.org,'alias':alias,'role':role,'email':email,
              'recipient_confirmed':True,'free_trial_confirmed':True,**changes}
        return self.data('POST','/api/operations/invitations',body,'admin')
    def rows(self):return self.data('GET','/api/operations/invitations',who='admin')
    def token(self,index=-1):return self.mail.messages[index].body.split('#token=')[1].split()[0]
    def complete(self,index=-1):self.service.complete(self.token(index),api.PASSWORD)

    def test_only_operator_can_manage_invitations(self):
        for who in ('teacher','student',None):
            for method,path in [('GET','/api/operations/invitations'),('POST','/api/operations/invitations'),
                ('POST','/api/operations/invitations/unknown/resend'),('POST','/api/operations/invitations/unknown/cancel')]:
                self.assertIn(self.call(method,path,{} if method=='POST' else None,who)[0],(401,403))

    def test_teacher_student_setup_context_login_logout_and_no_payment_records(self):
        self.invite('teacher','synthetic-teacher','invite-teacher@example.test')
        self.invite()
        rows=self.rows();self.assertEqual(len(rows),2)
        for row in rows:
            with self.assertRaises(AuthError):self.auth.login(row['email'],api.PASSWORD)
        self.complete(0);self.complete(1)
        for row in self.rows():
            self.assertEqual(row['setup_state'],'completed')
            _,session=self.auth.login(row['email'],api.PASSWORD)
            self.assertEqual(self.ops.context(self.org,row['user_id']).role,row['role'])
            self.cookies['invited']=session
            self.assertEqual(self.call('GET','/api/operations/users',who='invited')[0],403)
            self.assertEqual(self.call('GET',f'/api/b2b/organizations/{self.second}/me',who='invited')[0],404)
            if row['role']=='student':
                summary=self.ops.services.summary(self.org,row['user_id'])
                self.assertEqual(summary['access_mode'],'free_trial');self.assertEqual(summary['monthly_fee'],0)
                self.assertIsNone(summary['next_billing_date'])
                with self.auth.connection() as db:
                    for table in ('user_service_contracts','service_contract_terms','manual_dues','purchase_links'):
                        self.assertEqual(db.execute('SELECT count(*) FROM '+table+' WHERE user_id=?',(row['user_id'],)).fetchone()[0],0)
            self.auth.logout(session)
            with self.assertRaises(AuthError):self.auth.authenticate(session)
            self.auth.login(row['email'],api.PASSWORD)
        self.assertTrue(all('token' not in row and 'password' not in row for row in self.rows()))

    def test_exact_expiry_and_single_use(self):
        self.invite();first=self.token();self.now+=RESET_TTL_SECONDS
        with self.assertRaises(AuthError):self.service.complete(first,api.PASSWORD)
        self.assertEqual(self.ops.invitations.list(self.ids['admin'],self.now)[0]['setup_state'],'expired')
        row=self.rows()[0]
        self.data('POST',f"/api/operations/invitations/{row['id']}/resend",{'recipient_confirmed':True},'admin')
        new=self.token();self.service.complete(new,api.PASSWORD)
        with self.assertRaises(AuthError):self.service.complete(new,api.PASSWORD)
        with self.assertRaises(AuthError):self.service.complete(first,api.PASSWORD)

    def test_resend_revokes_old_and_does_not_duplicate_users(self):
        issued=self.invite();old=self.token()
        repeated=self.invite();self.assertEqual(issued['id'],repeated['id'])
        self.assertEqual(len(self.rows()),1)
        with self.assertRaises(AuthError):self.service.complete(old,api.PASSWORD)
        self.complete()

    def test_failed_send_revokes_token_and_retry_succeeds(self):
        class Broken:
            def send(self,message):raise RuntimeError('synthetic smtp sensitive detail')
        self.service.mailer=Broken()
        with self.assertLogs('invitation_repository',level='ERROR') as logs:self.invite()
        self.assertNotIn('sensitive detail',str(logs.output))
        row=self.rows()[0];self.assertEqual(row['delivery_state'],'failed')
        with self.auth.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM password_reset_tokens WHERE user_id=? AND used_at IS NULL',(row['user_id'],)).fetchone()[0],0)
        self.service.mailer=self.mail
        self.data('POST',f"/api/operations/invitations/{row['id']}/resend",{'recipient_confirmed':True},'admin')
        self.assertEqual(self.rows()[0]['delivery_state'],'provider_accepted');self.complete()

    def test_cancellation_disables_user_and_token_and_prevents_resend(self):
        self.invite();token=self.token();row=self.rows()[0]
        self.data('POST',f"/api/operations/invitations/{row['id']}/cancel",{},'admin')
        with self.assertRaises(AuthError):self.service.complete(token,api.PASSWORD)
        self.assertEqual(self.rows()[0]['setup_state'],'cancelled')
        self.assertEqual(self.call('POST',f"/api/operations/invitations/{row['id']}/resend",{'recipient_confirmed':True},'admin')[0],409)
        self.assertIsNone(self.service.repository.issue(row['email'],self.now))

    def test_duplicate_cross_org_role_existing_operator_rejected(self):
        self.invite();row=self.rows()[0]
        for values in ({'role':'operator'},{'email':'admin@example.test'},{'email':'teacher@example.test'},
                       {'organization_id':self.second}):
            with self.assertRaises(AssertionError):self.invite(**values)
        with self.auth.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM operating_administrator').fetchone()[0],1)
        self.assertEqual(self.rows()[0]['organization_id'],row['organization_id'])

    def test_unconfigured_mail_and_missing_confirmation_create_no_user(self):
        self.app.state.password_reset_service=None
        body={'organization_id':self.org,'alias':'safe','role':'student','email':'safe@example.test','recipient_confirmed':True,'free_trial_confirmed':True}
        self.assertEqual(self.call('POST','/api/operations/invitations',body,'admin')[0],503)
        self.app.state.password_reset_service=self.service
        self.assertEqual(self.call('POST','/api/operations/invitations',{**body,'recipient_confirmed':False},'admin')[0],422)
        self.assertEqual(self.call('POST','/api/operations/invitations',{**body,'free_trial_confirmed':False},'admin')[0],422)
        with self.auth.connection() as db:self.assertEqual(db.execute("SELECT count(*) FROM users WHERE normalized_email='safe@example.test'").fetchone()[0],0)

    def test_obsolete_queued_worker_cannot_invalidate_newer_link(self):
        self.invite();row=self.rows()[0]
        first=self.ops.invitations.queue(self.ids['admin'],row['id'],self.service,'synthetic')
        second=self.ops.invitations.queue(self.ids['admin'],row['id'],self.service,'synthetic')
        count=len(self.mail.messages)
        self.ops.invitations.deliver(row['id'],second,self.service);new=self.token()
        self.ops.invitations.deliver(row['id'],first,self.service)
        self.assertEqual(len(self.mail.messages),count+1);self.service.complete(new,api.PASSWORD)

    def test_formal_unpaid_contract_is_not_overridden_by_trial(self):
        self.invite();self.complete();row=self.rows()[0]
        self.ops.assign(self.ids['admin'],self.org,row['user_id'],'student',False,2000)
        with self.assertRaises(AuthError):self.ops.context(self.org,row['user_id'])

    def test_initial_operator_waits_for_password_then_explicit_singleton_grant(self):
        created=self.auth.create_setup_user('new-operator@example.test')
        with self.assertRaises(AuthError):self.auth.login('new-operator@example.test',api.PASSWORD)
        with self.assertRaises(AuthError):self.ops.bootstrap(created['id'])
        self.service.request('new-operator@example.test');self.complete()
        self.auth.login('new-operator@example.test',api.PASSWORD)
        # Existing singleton cannot be replaced, even by a ready new User.
        with self.assertRaises(AuthError):self.ops.bootstrap(created['id'])

    def test_fresh_operator_bootstrap_completes_after_own_setup(self):
        from operations_repository import OperationsRepository
        fresh=OperationsRepository(self.path.with_name('fresh-operator.sqlite3'))
        created=fresh.auth.create_setup_user('operator.synthetic@example.test')
        service=PasswordResetService(fresh.auth,self.mail,'https://app.example.test',clock=lambda:self.now)
        with self.assertRaises(AuthError):fresh.bootstrap(created['id'])
        service.request('operator.synthetic@example.test')
        service.complete(self.token(),api.PASSWORD)
        fresh.bootstrap(created['id']);fresh.bootstrap(created['id'])
        with fresh.auth.connection() as db:
            fresh.require_admin(db,created['id'])
            self.assertEqual(db.execute('SELECT count(*) FROM operating_administrator').fetchone()[0],1)

    def test_cancelled_queued_delivery_never_sends(self):
        self.invite();row=self.rows()[0]
        attempt=self.ops.invitations.queue(self.ids['admin'],row['id'],self.service,'synthetic')
        self.ops.invitations.cancel(self.ids['admin'],row['id'])
        count=len(self.mail.messages)
        self.ops.invitations.deliver(row['id'],attempt,self.service)
        self.assertEqual(len(self.mail.messages),count)

    def test_token_plaintext_not_in_persisted_invitation_or_api(self):
        self.invite();token=self.token()
        with self.auth.connection() as db:
            rows=[tuple(row) for row in db.execute('SELECT * FROM initial_invitations')]
            self.assertNotIn(token,str(rows))
        self.assertNotIn(token,str(self.rows()))


if __name__=='__main__':unittest.main()
