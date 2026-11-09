"""Dedicated deployment identity survives env omission and direct ASGI import."""
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1])]
import json,os,subprocess,tempfile,unittest
from unittest.mock import patch
import mari_runtime as runtime

ROOT=Path(__file__).resolve().parents[1]
GOOD={'FORTUNE_DEPLOYMENT_SURFACE':'teacher','FORTUNE_REQUIRED_DEPLOYMENT_SURFACE':'teacher'}

class RuntimeCases(unittest.TestCase):
    def setUp(self):
        self.base_env={k:v for k,v in os.environ.items() if not k.startswith('FORTUNE_')}
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.marker=Path(self.temp.name)/'.mari-reading-release'
        p=patch.object(runtime,'RELEASE_MARKER',self.marker);p.start();self.addCleanup(p.stop)
        e=patch.dict(os.environ,{},clear=True);e.start();self.addCleanup(e.stop)

    def test_ordinary_surfaces_preserved(self):
        self.assertEqual(runtime.runtime_configuration(),'combined')
        for surface in ('admin','combined'):
            with patch.dict(os.environ,{'FORTUNE_DEPLOYMENT_SURFACE':surface}):
                self.assertEqual(runtime.runtime_configuration(),surface)

    def test_each_missing_configuration_is_closed(self):
        self.marker.write_text(runtime.TEACHER_SURFACE+'\n',encoding='utf-8')
        for key in ('FORTUNE_DEPLOYMENT_SURFACE',):
            with patch.dict(os.environ,{k:v for k,v in GOOD.items() if k!=key},clear=True):
                with self.assertRaises(ValueError):runtime.runtime_configuration()
        with self.assertRaises(ValueError):runtime.runtime_configuration()

    def test_marker_overrides_surface_bypass(self):
        self.marker.write_text(runtime.TEACHER_SURFACE+'\n',encoding='utf-8')
        for surface in ('admin','combined','unknown'):
            with patch.dict(os.environ,{**GOOD,'FORTUNE_DEPLOYMENT_SURFACE':surface}):
                with self.assertRaises(ValueError):runtime.runtime_configuration()

    def test_required_surface_and_obsolete_configuration(self):
        with patch.dict(os.environ,GOOD):self.assertEqual(runtime.runtime_configuration(),'teacher')
        for key,value in [('FORTUNE_READING_ALLOWED_USER_IDS','[{},{}]'),('FORTUNE_REQUIRED_DEPLOYMENT_SURFACE','typo'),('FORTUNE_READING_ACCESS_PROFILE','two-person-prototype')]:
            with patch.dict(os.environ,{**GOOD,key:value}):
                with self.assertRaises(ValueError):runtime.runtime_configuration()

    def test_invalid_marker_rejected(self):
        self.marker.write_text('other\n',encoding='utf-8')
        with patch.dict(os.environ,GOOD):
            with self.assertRaises(ValueError):runtime.runtime_configuration()

    def test_direct_asgi_import_rejects_missing_configuration(self):
        # The import must stop before routes, DB construction or uvicorn startup.
        env={**self.base_env,'FORTUNE_REQUIRED_DEPLOYMENT_SURFACE':'teacher'}
        result=subprocess.run([sys.executable,'-B','-c',"import sys;sys.path[:0]=['fortune-next-app/backend','.'];import server"],
            cwd=ROOT,env=env,capture_output=True,timeout=30)
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b'dedicated_reading_configuration_required',result.stderr)

if __name__=='__main__':unittest.main()
