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
        self.environment=patch.dict(os.environ,{'FORTUNE_ENV':'production','FORTUNE_PUBLIC_ORIGIN':'https://teacher.example.test','FORTUNE_HISTORY_DB_PATH':str(self.root/'synthetic.sqlite3')})
        self.environment.start();self.addCleanup(self.environment.stop)
    def build(self,**options):
        self.path.write_text(json.dumps(self.config))
        # Production Linux ownership checks are separate; fixtures are Windows
        # temp files and contain disposable credentials only.
        with patch('password_reset_configuration.private_file',side_effect=lambda value:Path(value)):
            return configured_service(self.path,auth=object(),**options)
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

    def test_admin_reset_and_explicit_teacher_invitation_have_distinct_origins(self):
        os.environ['FORTUNE_PUBLIC_ORIGIN']='https://admin.example.test'
        with self.assertRaises(AuthError):self.build()
        invitation=self.build(expected_origin='https://teacher.example.test')
        self.assertTrue(invitation.message('student@example.test','synthetic',initial=True).body.startswith('30分以内'))
        self.assertIn('https://teacher.example.test/reset-password#token=',invitation.message('student@example.test','synthetic').body)
        self.config['public_origin']='https://admin.example.test'
        administrator=self.build()
        self.assertIn('https://admin.example.test/reset-password#token=',administrator.message('admin@example.test','synthetic').body)
        with self.assertRaises(AuthError):self.build(expected_origin='http://teacher.example.test')

    def test_server_loads_separate_explicit_services_without_smtp_connection(self):
        from tier_b import api_app
        api_app.cache_clear();self.addCleanup(api_app.cache_clear)
        invitation=self.root/'invitation.json';invitation.write_text(json.dumps(self.config))
        self.config['public_origin']='https://admin.example.test';self.path.write_text(json.dumps(self.config))
        with patch.dict(os.environ,{'FORTUNE_PUBLIC_ORIGIN':'https://admin.example.test','FORTUNE_DEPLOYMENT_SURFACE':'admin',
            'FORTUNE_RESET_MAIL_CONFIG':str(self.path),'FORTUNE_INVITATION_MAIL_CONFIG':str(invitation),
            'FORTUNE_INVITATION_PUBLIC_ORIGIN':'https://teacher.example.test'}),patch('password_reset_configuration.private_file',side_effect=lambda value:Path(value)),patch('smtplib.SMTP_SSL') as transport:
            app=api_app()
            self.assertEqual(app.state.password_reset_service.public_origin,'https://admin.example.test')
            self.assertEqual(app.state.invitation_service.public_origin,'https://teacher.example.test')
            self.assertEqual(app.state.invitation_service.repository.auth.path,self.root/'synthetic.sqlite3')
            transport.assert_not_called()


if __name__=='__main__':unittest.main()
