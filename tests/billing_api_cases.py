"""Real ASGI scoped billing authorization, no live side effects."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parent))
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
import product_api_cases as existing
from billing_policy import JST


class BillingAPICases(unittest.TestCase):
    setUpClass=classmethod(existing.ProductAPICases.setUpClass.__func__)
    setUp=existing.ProductAPICases.setUp
    tearDown=existing.ProductAPICases.tearDown
    call=existing.ProductAPICases.call
    data=existing.ProductAPICases.data
    fortune=existing.ProductAPICases.fortune
    def base(self):return f"/api/operations/users/{self.ids['student']}/organizations/{self.org}/contract"
    def own(self,org=None):return f'/api/account/organizations/{org or self.org}/'
    def test_operator_activate_paid_and_content_free_summary(self):
        value=self.data('POST',self.base()+'/activate',{},'admin')
        self.assertIsNotNone(value['activated_at']);self.assertEqual(value['monthly_fee'],2000)
        value=self.data('GET',self.base(),who='admin')
        self.assertFalse(value['automatic_actions_enabled']);self.assertNotIn('PRIVATE-CONTENT',str(value))
    def test_new_api_membership_grant_records_start_existing_membership_not_backfilled(self):
        path=f"/api/operations/users/{self.ids['student']}/membership"
        self.data('POST',path,{'organization_id':self.second,'role':'student','initial_payment_confirmed':True},'admin')
        value=self.data('GET',self.own(self.second)+'contract')
        self.assertIsNotNone(value['activated_at']);self.assertEqual(value['monthly_fee'],2000)
        self.data('POST',path,{'organization_id':self.org,'role':'student','initial_payment_confirmed':True},'admin')
        self.assertIsNone(self.data('GET',self.own()+'contract')['activated_at'])
    def test_teacher_all_contract_actions_and_dry_run_forbidden(self):
        for action in ['activate','paid-period','suspend','resume','cancellation','data-recovery','purge']:
            self.assertEqual(self.call('POST',self.base()+'/'+action,{'paid_through':'2026-11-30'},'teacher')[0],403)
        self.assertEqual(self.call('GET',self.base(),who='teacher')[0],403)
    def test_self_contract_other_owner_body_ignored(self):
        value=self.data('POST',self.own()+'cancellation',{'user_id':self.ids['other']})
        self.assertTrue(value['cancellation_needs_review'])
        self.assertEqual(self.call('GET',self.own(self.second)+'contract')[0],404)
    def test_other_user_cannot_get_contract(self):
        self.assertEqual(self.call('GET',self.own()+'contract',who='b2c')[0],404)
    def test_scoped_suspend_preserves_b2c_and_other_org(self):
        self.ops.assign(self.ids['admin'],self.second,self.ids['student'],'student',True,2000)
        self.data('POST',self.base()+'/suspend',{},'admin')
        self.assertEqual(self.fortune()[0],403)
        self.assertEqual(self.fortune(org=self.second)[0],200)
        self.assertEqual(self.call('GET','/api/account/summary')[0],200)
        self.assertEqual(self.call('GET',f"/api/history/{self.reading['id']}")[0],200)
    def test_teacher_sees_state_only_no_finances_or_individual_usage(self):
        self.data('POST',self.base()+'/suspend',{},'admin')
        value=self.data('GET',f'/api/b2b/organizations/{self.org}/teacher',who='teacher')
        self.assertEqual(value['students'][0]['account_state'],'suspended')
        self.assertEqual(set(value['students'][0]),{'display_name','account_state'})
        for field in ['paid_through','monthly_fee','arrears','cancellation','first_billing_date']:
            self.assertNotIn(field,str(value))
    def test_post_requires_csrf_and_no_host_self_claim(self):
        self.assertEqual(self.call('POST',self.own()+'cancellation',{},origin='https://evil.example')[0],403)
        self.assertEqual(self.call('POST',self.base()+'/suspend',{},headers={'X-Organization-ID':self.org,'X-Operator-ID':self.ids['admin']})[0],403)
    def test_unknown_action_no_purge_api(self):
        self.assertEqual(self.call('POST',self.base()+'/purge',{},'admin')[0],404)
    def test_cancel_ends_b2b_retained_history_recovery_not_resume(self):
        owner=self.ids['student'];admin=self.ids['admin']
        self.ops.product.bind_reading(self.org,owner,self.reading['id'])
        start=datetime(2026,10,20,tzinfo=JST)
        with patch('service_contract_repository.utc',side_effect=lambda v=None:(v or start).astimezone(timezone.utc)):
            self.ops.services.activate(admin,self.org,owner)
            self.data('POST',self.own()+'cancellation',{})
        ended=datetime(2026,11,2,tzinfo=JST)
        with patch('service_contract_repository.utc',side_effect=lambda v=None:(v or ended).astimezone(timezone.utc)):
            self.assertEqual(self.fortune()[0],403)
            self.assertEqual(self.call('GET',f"/api/history/{self.reading['id']}")[0],404)
            value=self.data('POST',self.own()+'data-recovery',{})
            self.assertEqual(value['state'],'terminated')
            self.assertEqual(self.call('GET',f"/api/history/{self.reading['id']}")[0],200)
            self.assertEqual(self.fortune()[0],403)
    def test_initial_payment_setting_does_not_cancel_formal_termination(self):
        owner=self.ids['student'];admin=self.ids['admin']
        self.ops.services.activate(admin,self.org,owner,datetime(2026,10,20,tzinfo=JST))
        self.ops.services.cancel(owner,self.org,datetime(2026,10,20,tzinfo=JST))
        self.ops.assign(admin,self.org,owner,'student',True,2000)
        with patch('service_contract_repository.utc',return_value=datetime(2026,11,2,tzinfo=timezone.utc)):
            self.assertEqual(self.fortune()[0],403)


if __name__=='__main__':unittest.main()
