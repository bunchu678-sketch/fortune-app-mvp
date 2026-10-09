// Existing live UI suites on an explicitly new disposable DB. --review leaves
// only these owned localhost servers running for human inspection. No SMTP.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),net=require('node:net');
const {spawn,spawnSync}=require('node:child_process'),{randomBytes}=require('node:crypto');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:3000';
const folder=fs.mkdtempSync(path.join(os.tmpdir(),'fortune-phase10-local-'));
const env={...process.env,PYTHONDONTWRITEBYTECODE:'1',PYTHONIOENCODING:'utf-8',FORTUNE_ENV:'development',
 FORTUNE_HISTORY_DEV_USER_ID:'',FORTUNE_HISTORY_DB_PATH:path.join(folder,'synthetic.sqlite3'),
 FORTUNE_PUBLIC_ORIGIN:base,FORTUNE_PDF_CONVERTER:'windows_excel',FORTUNE_TEST_PRODUCTION:'0',
 FORTUNE_PROXY_HEADERS:'0',FORTUNE_LOGIN_IP_LIMIT:'1000',FORTUNE_LOGIN_ACCOUNT_LIMIT:'100'};
const children=[],python=path.join(root,'.venv','Scripts','python.exe');
const review=process.argv.includes('--review'),password=randomBytes(24).toString('base64url');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function free(port){await new Promise((resolve,reject)=>{const s=net.createServer();s.once('error',()=>reject(Error('Local test port occupied: '+port)));s.listen(port,'127.0.0.1',()=>s.close(resolve));});}
function start(exe,args,cwd){const p=spawn(exe,args,{cwd,env,windowsHide:true,stdio:'ignore'});children.push(p);p.on('error',()=>{});return p;}
async function ready(url){for(let i=0;i<120;i++){if(children.some(p=>p.exitCode!==null))throw Error('Owned server failed');try{if((await fetch(url)).ok)return;}catch{}await sleep(400);}throw Error('Readiness timeout');}
function stop(){for(const p of children)if(p.pid)spawnSync('taskkill',['/PID',String(p.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});}
(async()=>{try{
 await free(8765);await free(3000);
 const setup=spawnSync(python,['-X','utf8','-B','-c',[
 "import sys,json,os;sys.path.insert(0,'tests')",
 "from operations_repository import OperationsRepository",
 "from history_service import HistoryService",
 "from password_reset_service import PasswordResetRepository",
 "from report_export_cases import FORM",
 "from fortune_service import calculate_fortune",
 "from datetime import datetime",
 "from billing_policy import JST",
 "v=json.load(sys.stdin);o=OperationsRepository(os.environ['FORTUNE_HISTORY_DB_PATH']);a=o.auth",
 "ids={k:a.create_user('phase10.'+k+'@example.test',v['password'])['id'] for k in ('admin','teacher','b2c','runner')}",
 "o.bootstrap(ids['admin']);org=o.create_organization(ids['admin'],'合成確認教室','synthetic-review')['id']",
 "o.assign(ids['admin'],org,ids['teacher'],'teacher')",
 "student=o.issue_account(ids['admin'],org,'phase10.student@example.test','合成確認生徒',True)['id']",
 "resets=PasswordResetRepository(a);issued=resets.issue('phase10.student@example.test',datetime.now(JST).timestamp());resets.complete(issued[1],v['password'],datetime.now(JST).timestamp());ids['student']=student",
 "history=HistoryService(o.product.history);rows={}",
 "for role in ('b2c','student'):",
 " for year in (2026,2027):",
 "  form={**FORM,'surname':'合成確認','givenName':str(year),'name':'合成確認'+str(year),'readingDate':str(year)+'-09-30'}",
 "  row=history.create(ids[role],{'input_snapshot':{'form':form},'result_snapshot':calculate_fortune(form),'memo':'合成の自由記入メモ','link':{'mode':'new_person'}},organization_id=org if role=='student' else None)",
 "  rows[role+'_'+str(year)]=row['id']",
 "cookie=a.login('phase10.runner@example.test',v['password'])[1]",
 "print(json.dumps({'org':org,'rows':rows,'cookie':cookie,'review_cookie':a.login('phase10.student@example.test',v['password'])[1]}))"
 ].join('\n')],{cwd:root,env,windowsHide:true,encoding:'utf8',input:JSON.stringify({password})});
 assert.equal(setup.status,0,'Synthetic fixture setup failed');const fixture=JSON.parse(setup.stdout);
 start(python,['-B','fortune-next-app/backend/server.py'],root);await ready('http://127.0.0.1:8765/health');
 start(process.execPath,['node_modules/next/dist/bin/next','start','-H','127.0.0.1','-p','3000'],path.join(root,'fortune-next-app'));await ready(base);
 if(review){
  for(const year of [2026,2027])for(const [format,ext] of [['excel','xlsx'],['pdf','pdf']]){
   const response=await fetch(base+'/api/export/'+format,{method:'POST',headers:{'Content-Type':'application/json',Origin:base,Cookie:'fortune_session='+fixture.review_cookie},body:JSON.stringify({reading_id:fixture.rows['student_'+year]})});
   assert.equal(response.status,200,'Human review sample export failed');
   fs.writeFileSync(path.join(folder,'鑑定書-'+year+'.'+ext),Buffer.from(await response.arrayBuffer()));
  }
  const guide=['# Phase 10 本人確認用（合成データのみ・Git対象外）','',
   '完成鑑定書: '+path.join(folder,'鑑定書-2026.xlsx')+' / '+path.join(folder,'鑑定書-2026.pdf')+' / '+path.join(folder,'鑑定書-2027.xlsx')+' / '+path.join(folder,'鑑定書-2027.pdf'),
   '確認URL: '+base+'/login','試験用の各メール: phase10.b2c@example.test / phase10.student@example.test / phase10.teacher@example.test / phase10.admin@example.test',
   '試験専用パスワード: '+password,'',
   '## 1. B2C・生徒（それぞれログイン）',
   'B2C入力: '+base+'/', '生徒入力: '+base+'/b2b/'+fixture.org,
   '本人のマイページ: '+base+'/mypage','履歴一覧: '+base+'/history',
   '生徒2026結果: '+base+'/history/'+fixture.rows.student_2026,
   '生徒2027結果: '+base+'/history/'+fixture.rows.student_2027,
   'B2C2026結果: '+base+'/history/'+fixture.rows.b2c_2026,
   'B2C2027結果: '+base+'/history/'+fixture.rows.b2c_2027,
   '1988-08-12 09:00／東京都／男性。年だけ2026/2027-09-30。',
   'A/B/C図、Bの鑑定年、Cの対象大運、メモ折りたたみを確認。2026は正式本文、2027は未登録案内。',
   '2026/2027履歴で「鑑定書を出力」→Excel/PDF。それぞれA4縦2ページ、見切れ・本文・年を確認。',
   '履歴→「この人を再鑑定」で今日へ移り、元履歴を保持することを確認。PCと実スマホは別確認。',
   '## 2. 先生（ログアウトして先生でログイン）',base+'/teacher/'+fixture.org,
   '教室全体の件数・氏名・状態だけ。生徒別本文・個別回数・利用時刻が出ないこと。',
   '## 3. 運営（ログアウトして運営でログイン）',base+'/operations',
   '教室・User・契約の画面が開くこと。通常の鑑定本文は表示しないこと。',
   '', '本番・既存ローカルDBとは別。メール送信はdisabled。個人情報を入力しない。',
   'このlocalhostは同じPC専用。実スマホ確認の公開/ネットワーク設定は未実施。',
   '終了はCodexへ「Phase 10確認用ローカルサーバーを終了」と伝える。'];
  fs.writeFileSync(path.join(folder,'本人確認手順.md'),guide.join('\n'),'utf8');
  fs.writeFileSync(path.join(folder,'owned-processes.json'),JSON.stringify({pids:children.map(p=>p.pid),db:env.FORTUNE_HISTORY_DB_PATH,base}),'utf8');
  console.log('Human review ready; guide='+path.join(folder,'本人確認手順.md'));
  // Stay alive so callers can terminate this owned test environment cleanly.
  await new Promise(resolve=>{process.once('SIGINT',resolve);process.once('SIGTERM',resolve);});
 }else{
  env.FORTUNE_SYNTHETIC_COOKIE=fixture.cookie;
  const preload=path.join(folder,'authenticated-playwright.cjs');
  fs.writeFileSync(preload,`const pw=require(process.env.PLAYWRIGHT_MODULE);const launch=pw.chromium.launch.bind(pw.chromium);pw.chromium.launch=async(...args)=>{const b=await launch(...args),newPage=b.newPage.bind(b);b.newPage=(options={})=>newPage({...options,storageState:{cookies:[{name:'fortune_session',value:process.env.FORTUNE_SYNTHETIC_COOKIE,domain:'127.0.0.1',path:'/',expires:-1,httpOnly:true,secure:false,sameSite:'Lax'}],origins:[]}});return b;};`);
  for(const test of ['history_ui_smoke.cjs','history_boundary_ui.cjs','report_export_ui.cjs']){
   const status=await new Promise((resolve,reject)=>{const p=spawn(process.execPath,['--require',preload,path.join(root,'tests',test)],{cwd:root,env,windowsHide:true,stdio:'inherit'});p.once('error',reject);p.once('exit',resolve);});
   assert.equal(status,0,test+' failed');console.log(test+' PASS');
  }
 }
}finally{stop();}})().catch(e=>{console.error(e.message);process.exitCode=1;});
