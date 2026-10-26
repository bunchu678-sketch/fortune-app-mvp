"""Initial invitation failure/expiry through real ASGI; in-memory mail only."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import time
import unittest
import product_api_cases as api
from auth_service import AuthError
from fortune_service import calculate_fortune
from mail_delivery import MemoryMailTransport
from password_reset_service import PasswordResetService, RESET_TTL_SECONDS


class InitialSetupDeliveryCases(unittest.TestCase):
    setUp = api.ProductAPICases.setUp
    tearDown = api.ProductAPICases.tearDown
    call = api.ProductAPICases.call
    data = api.ProductAPICases.data

    @classmethod
    def setUpClass(cls): cls.result = calculate_fortune(api.FORM)

    def invite(self, mail):
        self.now = time.time()
        self.service = PasswordResetService(self.auth, mail, 'https://app.example.test', clock=lambda: self.now)
        self.app.state.password_reset_service = self.service
        return self.data('POST', '/api/operations/users', {'organization_id': self.org,
            'email': 'new@example.test', 'display_name': '合成初回設定', 'initial_payment_confirmed': True}, 'admin')

    def test_failed_initial_delivery_revokes_token_and_keeps_setup_pending(self):
        class BrokenMail:
            def send(self, message): raise RuntimeError('synthetic transport detail')
        with self.assertLogs('password_reset_service', level='ERROR') as logs:
            result = self.invite(BrokenMail())
        self.assertEqual(result['mail_status'], 'queued')
        self.assertTrue(result['setup_pending'])
        self.assertNotIn('token', str(result)); self.assertNotIn('password', str(result))
        self.assertNotIn('synthetic transport detail', str(logs.output))
        with self.auth.connection() as db:
            self.assertIsNone(db.execute('SELECT completed_at FROM user_initial_setup WHERE user_id=?', (result['id'],)).fetchone()[0])
            self.assertEqual(db.execute('SELECT count(*) FROM password_reset_tokens WHERE user_id=? AND used_at IS NULL', (result['id'],)).fetchone()[0], 0)
        with self.assertRaises(AuthError): self.auth.login('new@example.test', api.PASSWORD)

    def test_expired_initial_link_cannot_activate_account_or_billing(self):
        mail = MemoryMailTransport(); result = self.invite(mail)
        token = mail.messages[0].body.split('#token=')[1].split()[0]
        self.now += RESET_TTL_SECONDS
        with self.assertRaises(AuthError): self.service.complete(token, api.PASSWORD)
        with self.auth.connection() as db:
            self.assertIsNone(db.execute('SELECT completed_at FROM user_initial_setup WHERE user_id=?', (result['id'],)).fetchone()[0])
            terms = db.execute('SELECT activated_at,awaiting_initial_setup FROM service_contract_terms WHERE user_id=?', (result['id'],)).fetchone()
            self.assertIsNone(terms[0]); self.assertEqual(terms[1], 1)
        with self.assertRaises(AuthError): self.auth.login('new@example.test', api.PASSWORD)


if __name__ == '__main__': unittest.main()
