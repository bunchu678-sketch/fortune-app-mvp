"""Bounded related regression runner; each suite has its own synthetic temp environment."""
from pathlib import Path
import concurrent.futures,json,os,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
PATTERNS=('product_api_cases.py','password_reset_cases.py','invitation_cases.py','invitation_configuration_cases.py',
 'initial_setup_delivery_cases.py','admin_domain_cases.py','auth_cases.py','history_cases.py','history_recovery_cases.py',
 'report_export_cases.py','report_pdf_cases.py','billing_api_cases.py','billing_retention_cases.py','operations_cases.py',
 'execution_cases.py','product_foundation_cases.py','usage_cases.py','account_lifecycle_cases.py',
 'final_retention_cases.py','final_retention_api_cases.py','security_scope_cases.py','certbot_hook_cases.py')
def main():
 out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=True);workers=int(sys.argv[2]) if len(sys.argv)>2 else 1
 def run(name):
  folder=out/name.removesuffix('.py');folder.mkdir(exist_ok=True)
  env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8','TEMP':str(folder),'TMP':str(folder),'TMPDIR':str(folder)}
  for key in ('FORTUNE_DEPLOYMENT_SURFACE','FORTUNE_RESET_MAIL_CONFIG','FORTUNE_INVITATION_MAIL_CONFIG','FORTUNE_INVITATION_PUBLIC_ORIGIN','FORTUNE_HISTORY_DB_PATH'):env.pop(key,None)
  with (out/(name+'.log')).open('wb') as log:
   r=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-p',name,'-v'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=400)
  text=(out/(name+'.log')).read_text(encoding='utf-8',errors='replace');match=re.search(r'Ran (\d+) tests?',text)
  skipped=re.search(r'OK \(skipped=(\d+)\)',text)
  return name,{'exit':r.returncode,'cases':int(match[1]) if match else 0,'skipped':int(skipped[1]) if skipped else 0}
 with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:results=dict(pool.map(run,PATTERNS))
 result={'suites':results,'cases':sum(r['cases'] for r in results.values()),'skipped':sum(r['skipped'] for r in results.values()),'all_passed':all(r['exit']==0 and r['cases'] for r in results.values()),'synthetic_only':True}
 (out/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
 return 0 if result['all_passed'] else 1
if __name__=='__main__':raise SystemExit(main())
