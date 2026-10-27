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
from unittest.mock import patch


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

    def token(self, mail, index=-1):
        return mail.messages[index].body.split('#token=')[1].split()[0]

    def test_failed_invitation_can_resend_without_duplicate_account_or_early_billing(self):
        class OnceBroken(MemoryMailTransport):
            first = True
            def send(self, message):
                if self.first:
                    self.first = False
                    raise RuntimeError('synthetic SMTP detail')
                super().send(message)
        mail = OnceBroken()
        with self.assertLogs('password_reset_service', level='ERROR'):
            result = self.invite(mail)
        self.now += 1
        resent = self.data('POST', f"/api/operations/users/{result['id']}/setup-mail", {}, 'admin')
        self.assertEqual(resent, {'mail_status': 'queued'})
        self.assertEqual(len(mail.messages), 1)
        with self.auth.connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM users WHERE normalized_email='new@example.test'").fetchone()[0], 1)
            terms = db.execute('SELECT activated_at,awaiting_initial_setup FROM service_contract_terms WHERE user_id=?', (result['id'],)).fetchone()
            self.assertIsNone(terms[0]); self.assertEqual(terms[1], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM manual_dues WHERE user_id=?', (result['id'],)).fetchone()[0], 0)
        self.service.complete(self.token(mail), api.PASSWORD)
        self.assertEqual(self.auth.login('new@example.test', api.PASSWORD)[0]['id'], result['id'])

    def test_resend_invalidates_previous_token_and_completed_link_is_single_use(self):
        mail = MemoryMailTransport(); result = self.invite(mail)
        old = self.token(mail); self.now += 1
        self.data('POST', f"/api/operations/users/{result['id']}/setup-mail", {}, 'admin')
        current = self.token(mail)
        self.assertNotEqual(old, current)
        with self.assertRaises(AuthError): self.service.complete(old, api.PASSWORD)
        self.service.complete(current, api.PASSWORD)
        with self.auth.connection() as db:
            before = tuple(db.execute('SELECT * FROM service_contract_terms WHERE user_id=?', (result['id'],)).fetchone())
            self.assertEqual(db.execute('SELECT count(*) FROM password_reset_tokens WHERE user_id=? AND used_at IS NULL', (result['id'],)).fetchone()[0], 0)
        with self.assertRaises(AuthError): self.service.complete(current, api.PASSWORD)
        with self.auth.connection() as db:
            self.assertEqual(tuple(db.execute('SELECT * FROM service_contract_terms WHERE user_id=?', (result['id'],)).fetchone()), before)

    def test_link_just_before_expiry_activates_once_and_setup_resend_then_refused(self):
        mail = MemoryMailTransport(); result = self.invite(mail)
        self.now += RESET_TTL_SECONDS - .001
        self.service.complete(self.token(mail), api.PASSWORD)
        with self.auth.connection() as db:
            terms = db.execute('SELECT activated_at,awaiting_initial_setup FROM service_contract_terms WHERE user_id=?', (result['id'],)).fetchone()
            self.assertIsNotNone(terms[0]); self.assertEqual(terms[1], 0)
        self.assertEqual(self.call('POST', f"/api/operations/users/{result['id']}/setup-mail", {}, 'admin')[0], 409)
        self.assertEqual(len(mail.messages), 1)

    def test_resend_failure_invalidates_both_old_and_new_link_and_stays_pending(self):
        mail = MemoryMailTransport(); result = self.invite(mail); old = self.token(mail)
        self.now += 1
        with patch.object(mail, 'send', side_effect=RuntimeError('synthetic credential detail')):
            with self.assertLogs('password_reset_service', level='ERROR') as logs:
                response = self.data('POST', f"/api/operations/users/{result['id']}/setup-mail", {}, 'admin')
        self.assertEqual(response['mail_status'], 'queued')
        self.assertNotIn('synthetic credential detail', str(logs.output))
        with self.assertRaises(AuthError): self.service.complete(old, api.PASSWORD)
        with self.auth.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM password_reset_tokens WHERE user_id=? AND used_at IS NULL', (result['id'],)).fetchone()[0], 0)
            row = db.execute('SELECT activated_at,awaiting_initial_setup FROM service_contract_terms WHERE user_id=?', (result['id'],)).fetchone()
            self.assertIsNone(row[0]); self.assertEqual(row[1], 1)

    def test_queued_response_is_not_delivery_confirmation(self):
        mail = MemoryMailTransport()
        # ASGI drains background tasks before returning; a queued API status still
        # has no promise of SMTP acceptance, recipient delivery or inbox arrival.
        with patch.object(PasswordResetService, 'deliver') as delivery:
            result = self.invite(mail)
        self.assertEqual(result['mail_status'], 'queued')
        delivery.assert_called_once_with('new@example.test')
        self.assertEqual(mail.messages, [])
        with self.assertRaises(AuthError): self.auth.login('new@example.test', api.PASSWORD)


if __name__ == '__main__': unittest.main()
