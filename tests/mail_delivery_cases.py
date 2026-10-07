"""SMTP is mocked in all tests. Never connects to an external mail server."""
import sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import Mock
from mail_delivery import SMTPConfig,SMTPMailTransport,TextMail,MailDeliveryError,MemoryMailTransport,DisabledMailTransport

class MailCases(unittest.TestCase):
    def config(self,**kw): return SMTPConfig(**({"host":"smtp.example.test","port":587,"username":"test-user","password":"synthetic-password"}|kw))
    def fake(self):
        connection=Mock(); connection.send_message.return_value={}
        factory=Mock(); factory.return_value.__enter__=Mock(return_value=connection); factory.return_value.__exit__=Mock(return_value=False)
        return factory,connection
    def test_starttls_before_auth_and_delivery(self):
        factory,connection=self.fake()
        SMTPMailTransport(self.config(),factory).send(TextMail("recipient@example.test","再設定","synthetic body"))
        names=[c[0] for c in connection.method_calls]
        self.assertEqual(names,["ehlo","starttls","ehlo","login","send_message"])
        self.assertTrue(connection.starttls.call_args.kwargs["context"].check_hostname)
        mail=connection.send_message.call_args.args[0]
        self.assertEqual(mail["From"],"no-reply@hakase-uranai.jp")
        self.assertEqual(mail.get_content().strip(),"synthetic body")
    def test_ssl_no_plain_connection(self):
        factory,connection=self.fake()
        SMTPMailTransport(self.config(security="ssl",port=465),factory).send(TextMail("recipient@example.test","Reset","body"))
        self.assertIn("context",factory.call_args.kwargs); connection.starttls.assert_not_called()
    def test_no_plaintext_transport(self):
        for security in ("none","plain","unknown"):
            with self.assertRaises(MailDeliveryError): SMTPMailTransport(self.config(security=security))
    def test_secret_not_in_repr(self):
        self.assertNotIn("synthetic-password",repr(self.config()))
        self.assertNotIn("raw-reset-token",repr(TextMail("a@example.test","Reset","raw-reset-token")))
    def test_server_error_is_sanitized(self):
        factory,connection=self.fake(); connection.login.side_effect=RuntimeError("synthetic-password leaked")
        with self.assertRaises(MailDeliveryError) as caught: SMTPMailTransport(self.config(),factory).send(TextMail("a@example.test","Reset","body"))
        self.assertEqual(str(caught.exception),"Mail delivery failed")
        connection.send_message.assert_not_called()
    def test_header_injection_rejected_before_connection(self):
        for recipient,subject in [("a@example.test\r\nBcc:evil@example.test","Reset"),("a@example.test","Reset\nBcc:evil")]:
            factory,connection=self.fake()
            with self.assertRaises(MailDeliveryError): SMTPMailTransport(self.config(),factory).send(TextMail(recipient,subject,"body"))
            factory.assert_not_called()
    def test_partial_refusal_is_failure(self):
        factory,connection=self.fake(); connection.send_message.return_value={"a@example.test":(550,b"no")}
        with self.assertRaises(MailDeliveryError): SMTPMailTransport(self.config(),factory).send(TextMail("a@example.test","Reset","body"))
    def test_memory_and_disabled(self):
        memory=MemoryMailTransport(); message=TextMail("a@example.test","Reset","body"); memory.send(message)
        self.assertEqual(memory.messages,[message])
        with self.assertRaises(MailDeliveryError): DisabledMailTransport().send(message)
    def test_config_validation(self):
        for change in [{"host":""},{"port":0},{"username":""},{"password":""},{"timeout":100},{"sender":"bad"}]:
            with self.assertRaises(MailDeliveryError): SMTPMailTransport(self.config(**change))

if __name__=="__main__": unittest.main(verbosity=2)
