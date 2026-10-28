"""Explicit SMTP configuration; all transports are constructed without sending."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json,os,tempfile,unittest
from unittest.mock import patch
from auth_service import AuthError
from password_reset_configuration import configured_service,private_file


class InvitationConfigurationCases(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.secret=self.root/'secret';self.secret.write_text('synthetic-credential-only')
        self.path=self.root/'config.json'
        self.config={'public_origin':'https://teacher.example.test','host':'smtp.example.test','port':465,
          'security':'ssl','username':'synthetic','sender':'operator@example.test','password_file':str(self.secret)}
        self.environment=patch.dict(os.environ,{'FORTUNE_ENV':'production','FORTUNE_PUBLIC_ORIGIN':'https://teacher.example.test'})
        self.environment.start();self.addCleanup(self.environment.stop)
    def build(self):
        self.path.write_text(json.dumps(self.config))
        # Production Linux ownership checks are separate; fixtures are Windows
        # temp files and contain disposable credentials only.
        with patch('password_reset_configuration.private_file',side_effect=lambda value:Path(value)):
            return configured_service(self.path,auth=object())
    def test_explicit_tls_and_sender_construct_transport_without_connection(self):
        with patch('smtplib.SMTP_SSL') as transport:
            service=self.build()
            self.assertEqual(service.public_origin,'https://teacher.example.test')
            self.assertEqual(service.mailer.config.sender,'operator@example.test')
            self.assertNotIn('synthetic-credential-only',repr(service.mailer.config))
            transport.assert_not_called()
    def test_mismatched_origin_and_missing_sender_refused(self):
        self.config['public_origin']='https://other.example.test'
        with self.assertRaises(AuthError):self.build()
        self.config['public_origin']='https://teacher.example.test';del self.config['sender']
        with self.assertRaises(AuthError):self.build()
    def test_plain_http_and_untrusted_file_paths_refused_without_secret_output(self):
        self.config['public_origin']='http://teacher.example.test'
        with self.assertRaises(AuthError) as error:self.build()
        self.assertNotIn('synthetic-credential-only',str(error.exception))
        with self.assertRaises(AuthError):private_file('relative-secret')


if __name__=='__main__':unittest.main()
