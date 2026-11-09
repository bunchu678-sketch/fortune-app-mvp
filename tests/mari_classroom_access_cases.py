"""Classroom authorization has no numerical or UUID allowlist limit."""
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]
import os,unittest,importlib.util
from unittest.mock import patch
import reading_only_cases as base
from report_export_cases import FORM

spec=importlib.util.spec_from_file_location('reading_start',Path(__file__).resolve().parents[1]/'deployment/mari-prototype/start_api.py')
start=importlib.util.module_from_spec(spec);spec.loader.exec_module(start)

class ClassroomAccessCases(base.ReadingOnlyCases):
    def test_three_then_ten_valid_members_are_allowed_without_runtime_id_configuration(self):
        # Existing teacher/student plus another eight independently authenticated students.
        for index in range(8):
            email=f'classroom-{index}@example.test';password='synthetic-password-only-2026'
            owner=self.auth.create_user(email,password)['id']
            self.ops.assign(self.ids['admin'],self.org,owner,'student',True,2000,activate_new=True)
            self.cookies['additional']=self.auth.login(email,password)[1]
            self.assertEqual(self.call('POST','/api/reading/fortune',FORM,'additional')[0],200)
            self.assertEqual(self.call('POST','/api/reading/theme',{'theme_key':'blue'},'additional')[0],200)
        self.assertEqual(self.call('POST','/api/reading/fortune',FORM,'teacher')[0],200)
        self.assertEqual(self.call('POST','/api/reading/fortune',FORM,'student')[0],200)
        start.validate_configuration()

    def test_existing_db_and_target_classroom_required_without_a_headcount_check(self):
        start.validate_configuration()
        with patch.dict(os.environ,{'FORTUNE_READING_ORGANIZATION_SLUG':'not-the-target'}):
            with self.assertRaises(ValueError):start.validate_configuration()
        with patch.dict(os.environ,{'FORTUNE_DEPLOYMENT_SURFACE':'admin'}):
            with self.assertRaises(ValueError):start.validate_configuration()
        # An empty classroom is valid configuration, but gives nobody access.
        empty=self.ops.create_organization(self.ids['admin'],'合成空教室','empty-classroom')
        with patch.dict(os.environ,{'FORTUNE_READING_ORGANIZATION_SLUG':'empty-classroom'}):
            start.validate_configuration()
            self.assertEqual(self.call('POST','/api/reading/fortune',FORM,'student')[0],403)

if __name__=='__main__':unittest.main()
