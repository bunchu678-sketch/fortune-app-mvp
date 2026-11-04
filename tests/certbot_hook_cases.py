"""POSIX hook tests. Commands are replaced only in a private test copy."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json,os,shutil,subprocess,tempfile,unittest


@unittest.skipUnless(os.name=='posix','POSIX sh hook is executed in the isolated Linux stage')
class CertbotHookCases(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        source=(Path(__file__).resolve().parents[1]/'deployment/security/reload-nginx.sh').read_text()
        for name,original in (('nginx','/usr/sbin/nginx'),('systemctl','/usr/bin/systemctl'),('logger','/usr/bin/logger')):
            stub=self.root/name
            stub.write_text('#!/usr/bin/python3\nimport os,sys,json\nwith open(os.environ["HOOK_TRACE"],"a") as f:f.write(json.dumps(["'+name+'",*sys.argv[1:]])+"\\n")\nif os.environ.get("FAIL_'+name.upper()+'"):\n print("synthetic-sensitive-detail",file=sys.stderr);sys.exit(1)\n')
            stub.chmod(0o700);self.assertIn(original,source);source=source.replace(original,str(stub))
        self.script=self.root/'hook.sh';self.script.write_text(source)
        self.trace=self.root/'trace.jsonl'
    def run_hook(self,lineage='/etc/letsencrypt/live/admin.hakase-uranai.jp',**extra):
        env={**os.environ,'RENEWED_LINEAGE':lineage,'HOOK_TRACE':str(self.trace),**extra}
        r=subprocess.run(['/bin/sh',str(self.script)],env=env,capture_output=True,text=True)
        rows=[json.loads(v) for v in self.trace.read_text().splitlines()] if self.trace.exists() else []
        return r,rows
    def test_shell_syntax(self):self.assertEqual(subprocess.run(['/bin/sh','-n',str(self.script)],capture_output=True).returncode,0)
    def test_success_validates_then_reloads_no_restart(self):
        r,rows=self.run_hook();self.assertEqual(r.returncode,0)
        self.assertEqual(rows[:2],[['nginx','-t'],['systemctl','reload','nginx.service']]);self.assertNotIn('restart',str(rows))
    def test_teacher_lineage_also_runs(self):
        r,rows=self.run_hook('/etc/letsencrypt/live/mari-mutsuro.hakase-uranai.jp');self.assertEqual(r.returncode,0);self.assertEqual(rows[1][1],'reload')
    def test_syntax_failure_skips_reload_and_reports_stage(self):
        r,rows=self.run_hook(FAIL_NGINX='1');self.assertEqual(r.returncode,1);self.assertFalse(any(v[0]=='systemctl' for v in rows));self.assertIn('syntax validation failed',r.stderr);self.assertNotIn('synthetic-sensitive-detail',r.stderr)
    def test_reload_failure_nonzero_and_no_raw_output(self):
        r,rows=self.run_hook(FAIL_SYSTEMCTL='1');self.assertEqual(r.returncode,1);self.assertIn('reload failed',r.stderr);self.assertNotIn('synthetic-sensitive-detail',r.stderr)
    def test_b2c_installer_is_not_duplicated(self):
        r,rows=self.run_hook('/etc/letsencrypt/live/app.hakase-uranai.jp');self.assertEqual((r.returncode,rows),(0,[]))
    def test_other_projects_are_untouched(self):
        r,rows=self.run_hook('/etc/letsencrypt/live/other.example.test');self.assertEqual((r.returncode,rows),(0,[]))
    def test_missing_context_fails_without_running_commands(self):
        r,rows=self.run_hook('');self.assertEqual((r.returncode,rows),(64,[]))

if __name__=='__main__':unittest.main()
