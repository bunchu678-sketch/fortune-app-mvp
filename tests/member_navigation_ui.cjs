// Real localhost navigation/auth tests. Synthetic users and a new DB only; no SMTP.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),net=require('node:net');
const {spawn,spawnSync}=require('node:child_process'),{randomBytes}=require('node:crypto');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:3000';
const folder=fs.mkdtempSync(path.join(os.tmpdir(),'fortune-member-navigation-'));
const env={...process.env,PYTHONDONTWRITEBYTECODE:'1',PYTHONIOENCODING:'utf-8',FORTUNE_ENV:'development',
 FORTUNE_HISTORY_DEV_USER_ID:'',FORTUNE_HISTORY_DB_PATH:path.join(folder,'synthetic.sqlite3'),
 FORTUNE_PUBLIC_ORIGIN:base,FORTUNE_PDF_CONVERTER:'disabled',FORTUNE_TEST_PRODUCTION:'0',
 FORTUNE_PROXY_HEADERS:'0',FORTUNE_LOGIN_IP_LIMIT:'1000',FORTUNE_LOGIN_ACCOUNT_LIMIT:'100'};
const children=[],python=path.join(root,'.venv','Scripts','python.exe');
const password=randomBytes(24).toString('base64url');
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
 "ids={k:a.create_user('phase10.'+k+'@example.test',v['password'])['id'] for k in ('admin','teacher','b2c','runner','multi','mixed','paused','unpaid','suspended')}",
 "o.bootstrap(ids['admin']);org=o.create_organization(ids['admin'],'合成確認教室','synthetic-review')['id']",
 "o.assign(ids['admin'],org,ids['teacher'],'teacher')",
 "other=o.create_organization(ids['admin'],'合成教室二','navigation-two')['id']",
 "for k in ('multi','mixed'):o.assign(ids['admin'],org,ids[k],'teacher')",
 "o.assign(ids['admin'],other,ids['multi'],'teacher');o.assign(ids['admin'],other,ids['mixed'],'student',True,2000)",
 "for k in ('paused','suspended'):o.assign(ids['admin'],org,ids[k],'student',True,2000)",
 "o.assign(ids['admin'],org,ids['unpaid'],'student',False,2000)",
 "o.services.suspend(ids['admin'],org,ids['paused']);o.transition(ids['admin'],ids['suspended'],'suspend')",
 "student=o.issue_account(ids['admin'],org,'phase10.student@example.test','合成確認生徒',True)['id']",
 "resets=PasswordResetRepository(a);issued=resets.issue('phase10.student@example.test',datetime.now(JST).timestamp());resets.complete(issued[1],v['password'],datetime.now(JST).timestamp());ids['student']=student",
 "history=HistoryService(o.product.history);rows={}",
 "for role in ('b2c','student'):",
 " for year in (2026,2027):",
 "  form={**FORM,'surname':'合成確認','givenName':str(year),'name':'合成確認'+str(year),'readingDate':str(year)+'-09-30'}",
 "  row=history.create(ids[role],{'input_snapshot':{'form':form,'manualChoices':{},'boundarySelections':{}},'result_snapshot':calculate_fortune(form),'memo':'合成の自由記入メモ','link':{'mode':'new_person'}},organization_id=org if role=='student' else None)",
 "  rows[role+'_'+str(year)]=row['id']",
 "cookie=a.login('phase10.runner@example.test',v['password'])[1]",
 "print(json.dumps({'org':org,'other':other,'ids':ids,'rows':rows,'cookie':cookie,'review_cookie':a.login('phase10.student@example.test',v['password'])[1]}))"
 ].join('\n')],{cwd:root,env,windowsHide:true,encoding:'utf8',input:JSON.stringify({password})});
 assert.equal(setup.status,0,'Synthetic fixture setup failed');const fixture=JSON.parse(setup.stdout);
 start(python,['-B','fortune-next-app/backend/server.py'],root);await ready('http://127.0.0.1:8765/health');
 start(process.execPath,['node_modules/next/dist/bin/next','start','-H','127.0.0.1','-p','3000'],path.join(root,'fortune-next-app'));await ready(base);

 const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');let passed=0;const errors=[];
 const browser=await chromium.launch({channel:'msedge',headless:true});
 async function check(label,fn){await fn();passed++;console.log(label+' PASS');}
 try{for(const width of [1280,390,320]){
  const context=await browser.newContext({viewport:{width,height:900}}),page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  const f=fixture,overflow=async()=>assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow');
  const login=async(role,destination,next=null)=>{
   await page.goto(base+'/login'+(next===null?'':'?next='+encodeURIComponent(next)),{waitUntil:'networkidle'});
   await page.getByLabel('メールアドレス',{exact:true}).fill('phase10.'+role+'@example.test');await page.getByLabel('パスワード',{exact:true}).fill(password);
   await page.getByRole('button',{name:'ログイン',exact:true}).click();await page.waitForURL(base+destination);await page.waitForLoadState('networkidle');
   try { await page.getByText('phase10.'+role+'@example.test でログイン中',{exact:true}).waitFor(); } catch (error) { console.error(JSON.stringify({route:new URL(page.url()).pathname,meStatus:(await page.request.get(base+'/api/auth/me')).status(),dom:await page.evaluate(()=>document.body.innerText.slice(0,300)),errors}));throw error; } await overflow();
  };
  const logout=async()=>{await page.getByRole('button',{name:'ログアウト',exact:true}).click();await page.waitForURL(base+'/login');await page.getByLabel('メールアドレス',{exact:true}).waitFor();};
  await check(width+' anonymous B2C and specific-date input',async()=>{await page.goto(base,{waitUntil:'networkidle'});await page.getByRole('button',{name:'鑑定結果を表示する',exact:true}).waitFor();assert.equal(await page.getByLabel('特定の日時について占う').count(),1);await overflow();});
  await check(width+' anonymous login form',async()=>{await page.goto(base+'/login',{waitUntil:'networkidle'});await page.getByLabel('パスワード',{exact:true}).waitFor();});
  for(const route of ['/mypage','/history','/operations','/teacher/'+f.org,'/b2b/'+f.org])await check(width+' anonymous guarded '+route.split('/')[1],async()=>{await page.goto(base+route,{waitUntil:'networkidle'});await page.getByRole('link',{name:'ログインへ',exact:true}).waitFor();assert.equal(await page.locator('.memberStartButton').count(),0);});
  await check(width+' invalid login stays and displays error',async()=>{
   await page.goto(base+'/login',{waitUntil:'networkidle'});await page.getByLabel('メールアドレス',{exact:true}).fill('phase10.b2c@example.test');await page.getByLabel('パスワード',{exact:true}).fill(randomBytes(20).toString('hex'));await page.getByRole('button',{name:'ログイン',exact:true}).click();await page.getByRole('alert').filter({hasText:'メールアドレスまたはパスワードが正しくありません'}).waitFor();assert.equal(page.url(),base+'/login');assert.equal(await page.getByLabel('パスワード',{exact:true}).inputValue(),'');await overflow();
  });
  for(const [role,destination,count] of [['b2c','/mypage',1],['student','/mypage',2],['teacher','/teacher/'+f.org,1],['multi','/mypage',3],['mixed','/mypage',3],['admin','/operations',1],['paused','/mypage',1],['unpaid','/mypage',1]]){
   await check(width+' '+role+' role entrance and accessible start buttons',async()=>{
    await login(role,destination);await page.waitForFunction(()=>document.querySelector('.memberStart') && !document.querySelector('.memberStart [role=status]'));assert.equal(await page.locator('.memberStartButton').count(),count);
    for(const button of await page.locator('.memberStartButton').all()){const box=await button.boundingBox();assert(box.height>=44);await button.focus();assert(await button.evaluate(e=>e===document.activeElement));}
    if(role==='multi'||role==='mixed'){await page.getByText('利用する所属先を選んでください。',{exact:true}).waitFor();assert.equal(await page.locator('a[href="/b2b/'+f.org+'"]').count(),1);assert.equal(await page.locator('a[href="/b2b/'+f.other+'"]').count(),1);}
    if(role==='admin')assert.equal(await page.locator('a[href^="/b2b/"]').count(),0);
    if(role==='paused'||role==='unpaid'){assert.equal(await page.locator('a[href^="/b2b/"]').count(),0);assert.equal((await page.request.get(base+'/api/b2b/organizations/'+f.org+'/me')).status(),403);assert.equal((await page.request.post(base+'/api/b2b/organizations/'+f.org+'/fortune',{headers:{Origin:base},data:{}})).status(),403);}
    await overflow();await page.screenshot({path:path.join(folder,width+'-'+role+'.png'),fullPage:true});
   });
   if(['b2c','student','teacher','multi'].includes(role))await check(width+' '+role+' start button uses authorized existing screen',async()=>{
    const button=role==='b2c'?page.locator('.memberStartButton[href="/"]'):page.locator('.memberStartButton[href="/b2b/'+f.org+'"]');await button.focus();await page.keyboard.press('Enter');await page.waitForURL(base+(role==='b2c'?'/':'/b2b/'+f.org));await page.getByRole('button',{name:'鑑定結果を表示する',exact:true}).waitFor();assert.equal(await page.getByLabel('特定の日時について占う').count(),role==='b2c'?1:0);await overflow();
   });
   await check(width+' '+role+' logout to login and revoked session',async()=>{await logout();assert.equal((await page.request.get(base+'/api/auth/me')).status(),401);assert.equal((await page.request.get(base+'/api/history')).status(),401);});
  }
  await check(width+' suspended account login denied',async()=>{
   await page.goto(base+'/login',{waitUntil:'networkidle'});await page.getByLabel('メールアドレス',{exact:true}).fill('phase10.suspended@example.test');await page.getByLabel('パスワード',{exact:true}).fill(password);await page.getByRole('button',{name:'ログイン',exact:true}).click();await page.getByRole('alert').waitFor();assert.equal(page.url(),base+'/login');
  });
  await check(width+' logout failure preserves screen/session and shows error',async()=>{
   await login('b2c','/mypage');await page.route('**/api/auth/logout',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({ok:false,error:'合成ログアウト失敗'})}));await page.getByRole('button',{name:'ログアウト',exact:true}).click();await page.getByRole('alert').filter({hasText:'合成ログアウト失敗'}).waitFor();assert.equal(page.url(),base+'/mypage');assert.equal((await page.request.get(base+'/api/auth/me')).status(),200);await overflow();await page.unroute('**/api/auth/logout');await logout();
  });
  await check(width+' back after logout cannot show protected data',async()=>{
   await login('b2c','/mypage');await page.getByRole('link',{name:'自分の鑑定履歴',exact:true}).click();await page.waitForURL(base+'/history');await page.locator(width<760?'.historyMobile':'.historyDesktop').getByText('合成確認2026',{exact:true}).waitFor();await logout();await page.goBack({waitUntil:'networkidle'});await page.getByRole('link',{name:'ログインへ',exact:true}).waitFor();assert.equal(await page.getByText('合成確認2026',{exact:true}).count(),0);assert.equal(await page.getByText('phase10.b2c@example.test でログイン中',{exact:true}).count(),0);assert.equal(await page.locator('.memberStartButton').count(),0);
  });
  await check(width+' logout clears entered personal information',async()=>{
   await login('b2c','/mypage');await page.locator('.memberStartButton[href="/"]').click();await page.getByLabel('姓',{exact:true}).fill('合成未保存氏名');await logout();await page.goto(base);assert.equal(await page.getByLabel('姓',{exact:true}).inputValue(),'');
  });
  await check(width+' pagehide removes authenticated DOM before BFCache and pageshow rechecks',async()=>{
   await login('b2c','/mypage');let hold,signal;const pending=new Promise(r=>signal=r);await page.route('**/api/auth/me',async route=>{const response=await route.fetch();hold=()=>route.fulfill({response});signal();});await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await pending;await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true})));assert.equal(await page.getByText('phase10.b2c@example.test でログイン中',{exact:true}).count(),0);assert.equal(await page.locator('.memberStartButton').count(),0);
   await page.request.post(base+'/api/auth/logout',{headers:{Origin:base},data:{}});await hold();await page.unroute('**/api/auth/me');await sleep(200);assert.equal(await page.locator('.memberStartButton').count(),0);assert.equal(await page.getByText('phase10.b2c@example.test でログイン中',{exact:true}).count(),0);await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));await page.getByRole('link',{name:'ログインへ',exact:true}).waitFor();assert.equal((await page.request.get(base+'/api/auth/me')).status(),401);
  });
  for(const [role,next,expected] of [
   ['b2c','/history','/history'],['b2c','/history/'+f.rows.b2c_2026,'/history/'+f.rows.b2c_2026],['b2c','/','/'],
   ['student','/b2b/'+f.org,'/b2b/'+f.org],['teacher','/teacher/'+f.org,'/teacher/'+f.org],
   ['admin','/operations/organizations/'+f.org,'/operations/organizations/'+f.org],['admin','/operations/users/'+f.ids.student,'/operations/users/'+f.ids.student],
   ['student','/teacher/'+f.org,'/mypage'],['student','/operations','/mypage'],['student','/b2b/'+f.other,'/mypage'],['student','/history/'+f.rows.b2c_2026,'/mypage'],['paused','/b2b/'+f.org,'/mypage'],
   ['b2c','https://outside.test','/mypage'],['b2c','//outside.test','/mypage'],['b2c','/\\outside.test','/mypage'],['b2c','/operations/../login','/mypage'],
  ])await check(width+' checked next '+role+' '+next.split('/')[1],async()=>{await login(role,expected,next);if(role==='student'){assert.equal((await page.request.get(base+'/api/b2b/organizations/'+f.other+'/me')).status(),404);assert.equal((await page.request.get(base+'/api/history/'+f.rows.b2c_2026)).status(),404);}await logout();});
  await check(width+' unavailable role metadata falls back to mypage',async()=>{
   await page.route('**/api/account/summary',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({ok:false,error:'合成情報取得失敗'})}));await login('teacher','/mypage');await page.getByRole('alert').filter({hasText:'合成情報取得失敗'}).waitFor();await page.unroute('**/api/account/summary');await logout();
  });
  await check(width+' delayed login destination cannot override logout',async()=>{
   await page.goto(base+'/login',{waitUntil:'networkidle'});let hold,signal;const pending=new Promise(r=>signal=r);
   await page.route('**/api/account/summary',async route=>{const response=await route.fetch();hold=()=>route.fulfill({response});signal();});
   await page.getByLabel('メールアドレス',{exact:true}).fill('phase10.teacher@example.test');await page.getByLabel('パスワード',{exact:true}).fill(password);await page.getByRole('button',{name:'ログイン',exact:true}).click();await pending;await logout();await hold();await page.unroute('**/api/account/summary');await sleep(200);assert.equal(page.url(),base+'/login');assert.equal((await page.request.get(base+'/api/auth/me')).status(),401);
  });
  await check(width+' late membership response cannot restore logged-out controls',async()=>{
   await login('student','/mypage');let hold,signal;const pending=new Promise(r=>signal=r);await page.route('**/api/b2b/organizations/'+f.org+'/me',async route=>{const response=await route.fetch();hold=()=>route.fulfill({response});signal();});await page.reload();await pending;await logout();await hold();await page.unroute('**/api/b2b/organizations/'+f.org+'/me');await sleep(200);assert.equal(page.url(),base+'/login');assert.equal(await page.locator('.memberStartButton').count(),0);
  });
  await context.close();
 }}finally{await browser.close();}
 assert.deepEqual(errors,[]);console.log('Member navigation real UI: '+passed+' PASS; screenshots: '+folder);
}finally{stop();}})().catch(e=>{console.error(e.stack);process.exitCode=1;});
