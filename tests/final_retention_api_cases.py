"""Actual ASGI operator-only proof/retention routes, CSRF and content isolation."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parent))
import unittest
from datetime import datetime,timezone
from unittest.mock import patch
import product_api_cases as existing

class FinalRetentionAPICases(unittest.TestCase):
    setUpClass=classmethod(existing.ProductAPICases.setUpClass.__func__)
    setUp=existing.ProductAPICases.setUp
    tearDown=existing.ProductAPICases.tearDown
    call=existing.ProductAPICases.call
    data=existing.ProductAPICases.data
    fortune=existing.ProductAPICases.fortune
    def proof(self):
        return dict(purchase_number='P-001',organization_id=self.org,purchased_on='2026-01-01',email='student@example.test',payment_confirmed=True,review_on='2028-12-31',user_id=self.ids['student'])
    def test_operator_register_and_list_minimal_proofs(self):
        self.data('POST','/api/operations/purchases',self.proof(),'admin')
        value=self.data('GET','/api/operations/purchases',who='admin')
        self.assertEqual(value[0]['purchase_number'],'P-001')
        for field in ['purchaser_digest','student@example.test','PRIVATE-CONTENT','password_hash']:self.assertNotIn(field,str(value))
    def test_teacher_and_student_all_retention_endpoints_denied(self):
        owner=self.ids['student']
        for who in ['teacher','student','other','b2c']:
            for method,path,payload in [('GET','/api/operations/purchases',None),('POST','/api/operations/purchases',self.proof()),('POST','/api/operations/purchases/P-001/recontract',{}),('GET',f'/api/operations/users/{owner}/retention',None),('POST',f'/api/operations/users/{owner}/b2c-retention',{'state':'inactive'}),('GET','/api/operations/retention-reviews',None),('POST','/api/operations/retention-reviews/purchase/P-001',{})]:
                self.assertEqual(self.call(method,path,payload,who)[0],403,(who,path))
    def test_csrf_and_spoofed_operator_ids_denied(self):
        self.assertEqual(self.call('POST','/api/operations/purchases',self.proof(),'admin',origin='https://evil.test')[0],403)
        self.assertEqual(self.call('POST','/api/operations/purchases',self.proof(),headers={'X-Operator-ID':self.ids['admin']})[0],403)
    def test_user_dryrun_content_free_b2c_protected(self):
        owner=self.ids['student'];path=f'/api/operations/users/{owner}'
        self.data('POST',path+'/b2c-retention',{'state':'inactive'},'admin')
        value=self.data('GET',path+'/retention',who='admin')
        self.assertIn('b2c_readings',value['blockers']);self.assertFalse(value['can_delete'])
        self.assertNotIn('PRIVATE-CONTENT',str(value));self.assertFalse(value['automatic_actions_enabled'])
    def test_review_and_registration_are_audited(self):
        self.data('POST','/api/operations/purchases',self.proof(),'admin')
        self.data('POST','/api/operations/retention-reviews/purchase/P-001',{'review_on':'2029-12-31','basis':'purchase proof'},'admin')
        value=self.data('GET','/api/operations/audit',who='admin')
        self.assertIn('purchase-proof-register',str(value));self.assertIn('retention-review-purchase',str(value))
    def test_recontract_waives_same_initial_fee_only_and_mail_disabled(self):
        self.data('POST','/api/operations/purchases',self.proof(),'admin')
        owner=self.ids['student'];admin=self.ids['admin']
        now=datetime(2026,10,20,tzinfo=timezone.utc)
        self.ops.services.activate(admin,self.org,owner,now);self.ops.services.cancel(owner,self.org,now)
        body={'organization_id':self.org,'email':'student@example.test','display_name':'synthetic','identity_verified':True,'monthly_payment_confirmed':True,'paid_through':'2027-01-31'}
        with patch('retention_repository.utc',side_effect=lambda v=None:v or datetime(2026,12,1,tzinfo=timezone.utc)):
            value=self.data('POST','/api/operations/purchases/P-001/recontract',body,'admin')
        self.assertFalse(value['initial_fee_required']);self.assertFalse(value['deleted_history_restorable']);self.assertEqual(value['mail_delivery'],'disabled')
    def test_invalid_org_cannot_claim_purchase(self):
        self.data('POST','/api/operations/purchases',self.proof(),'admin')
        body={'organization_id':self.second,'email':'student@example.test','display_name':'x','identity_verified':True,'monthly_payment_confirmed':True,'paid_through':'2027-01-31'}
        self.assertEqual(self.call('POST','/api/operations/purchases/P-001/recontract',body,'admin')[0],409)
    def test_no_physical_purge_api(self):
        self.assertEqual(self.call('POST',f"/api/operations/users/{self.ids['student']}/retention/purge",{},'admin')[0],404)

if __name__=='__main__':unittest.main()
