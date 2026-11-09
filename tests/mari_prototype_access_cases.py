"""Two-person configuration never bypasses the accepted authorization checks."""
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent),
    str(Path(__file__).resolve().parents[1]/'fortune-next-app/backend')]
import json
import os
import unittest
from unittest.mock import patch
from uuid import uuid4
from auth_service import AuthError
from mari_prototype_access import require_prototype_reader
import reading_only_cases
import reading_only
import importlib.util
spec = importlib.util.spec_from_file_location('prototype_start', Path(__file__).resolve().parents[1]/'deployment/mari-prototype/start_api.py')
prototype_start = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prototype_start)


class PrototypeConfigurationCases(unittest.TestCase):
    def setUp(self):
        self.ids = [str(uuid4()), str(uuid4())]
        self.env = patch.dict(os.environ, {'FORTUNE_DEPLOYMENT_SURFACE': 'teacher',
            'FORTUNE_READING_ACCESS_PROFILE': 'two-person-prototype',
            'FORTUNE_READING_ALLOWED_USER_IDS': json.dumps(self.ids)})
        self.env.start(); self.addCleanup(self.env.stop)

    def test_exactly_two_selected_users_allowed(self):
        for user in self.ids:
            require_prototype_reader(user)
        with self.assertRaises(AuthError) as error:
            require_prototype_reader(str(uuid4()))
        self.assertEqual(error.exception.status, 403)

    def test_invalid_or_expanded_configuration_fails_closed(self):
        for value in ('', 'null', '{}', '[]', json.dumps(self.ids[:1]),
                json.dumps(self.ids + [str(uuid4())]), json.dumps([self.ids[0]]*2),
                '["*"]', json.dumps(['not-a-user', self.ids[0]]), json.dumps([1,2])):
            with self.subTest(value_kind=type(value).__name__), patch.dict(os.environ, {'FORTUNE_READING_ALLOWED_USER_IDS': value}):
                with self.assertRaises(AuthError) as error: require_prototype_reader(self.ids[0])
                self.assertEqual(error.exception.status, 503)

    def test_unknown_profile_fails_closed(self):
        with patch.dict(os.environ, {'FORTUNE_READING_ACCESS_PROFILE': 'unknown'}):
            with self.assertRaises(AuthError) as error: require_prototype_reader(self.ids[0])
            self.assertEqual(error.exception.status, 503)

    def test_admin_and_combined_are_unchanged(self):
        for surface in ('admin', 'combined'):
            with patch.dict(os.environ, {'FORTUNE_DEPLOYMENT_SURFACE': surface,
                    'FORTUNE_READING_ALLOWED_USER_IDS': 'invalid'}):
                require_prototype_reader(str(uuid4()))

    def test_unselected_profile_retains_accepted_default(self):
        with patch.dict(os.environ, {'FORTUNE_READING_ACCESS_PROFILE': ''}):
            require_prototype_reader(str(uuid4()))


class PrototypeAuthorizationCases(reading_only_cases.ReadingOnlyCases):
    def setUp(self):
        super().setUp()
        self.prototype = patch.dict(os.environ, {'FORTUNE_READING_ACCESS_PROFILE': 'two-person-prototype',
            'FORTUNE_READING_ALLOWED_USER_IDS': json.dumps([self.ids['teacher'], self.ids['student']])})
        self.prototype.start(); self.addCleanup(self.prototype.stop)

    def tearDown(self):
        self.prototype.stop()
        super().tearDown()

    def test_selected_pair_still_uses_membership_and_existing_access_checks(self):
        # Existing parent tests cover suspension, sessions, CSRF, DB preservation,
        # old API denial and unchanged calculations with this profile enabled.
        with patch.object(reading_only, 'identity', return_value={'id': 'not-allowed'}), \
                patch.object(reading_only, 'repositories') as repository:
            with self.assertRaises(AuthError) as error: reading_only.context(object())
            self.assertEqual(error.exception.status, 403)
            repository.assert_not_called()

    def test_dedicated_entry_point_requires_pair_and_reads_existing_memberships(self):
        prototype_start.validate_configuration()
        with patch.dict(os.environ, {'FORTUNE_READING_ACCESS_PROFILE': ''}):
            with self.assertRaises(ValueError): prototype_start.validate_configuration()
        with patch.dict(os.environ, {'FORTUNE_READING_ALLOWED_USER_IDS': json.dumps([self.ids['student'], self.ids['other']])}):
            with self.assertRaises(ValueError): prototype_start.validate_configuration()
        self.ops.transition(self.ids['admin'], self.ids['teacher'], 'suspend')
        with self.assertRaises(ValueError): prototype_start.validate_configuration()


if __name__ == '__main__': unittest.main()
