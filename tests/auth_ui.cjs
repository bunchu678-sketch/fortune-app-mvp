// Starts only its own test servers, with a new disposable DB and in-memory synthetic credentials.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const {randomBytes} = require('node:crypto');
const {spawn, spawnSync} = require('node:child_process');
const net = require('node:net');
const root = path.resolve(__dirname,'..');
const production = process.env.FORTUNE_TEST_PRODUCTION === '1';
const base = production ? 'https://app.hakase-uranai.jp' : 'http://127.0.0.1:3000';
const python = process.env.FORTUNE_TEST_PYTHON || path.join(root,'.venv','Scripts','python.exe');
const out = process.env.FORTUNE_AUTH_UI_OUTPUT || fs.mkdtempSync(path.join(os.tmpdir(),'fortune-auth-ui-'));
fs.mkdirSync(out,{recursive:true});
const disposable = fs.mkdtempSync(path.join(out,'test-db-'));
const env = {...process.env, PYTHONDONTWRITEBYTECODE:'1', PYTHONIOENCODING:'utf-8',
 FORTUNE_ENV:production?'production':'development', FORTUNE_HISTORY_DEV_USER_ID:'', FORTUNE_HISTORY_DB_PATH:path.join(disposable,'test-auth.sqlite3'),
 FORTUNE_PUBLIC_ORIGIN:base, FORTUNE_PROXY_HEADERS:production?'1':'0', FORTUNE_TRUSTED_PROXY_IPS:'127.0.0.1', FORTUNE_PDF_CONVERTER:process.env.FORTUNE_TEST_PDF_CONVERTER || 'windows_excel'};
const children = [], results = [], errors = [];
// APIRequestContext and route.fetch do not use Chromium host-resolver rules.
// Production-mode auxiliary calls therefore use browser fetch or a hardcoded localhost transport.
async function localTls(url,options={}) {
 assert.equal(new URL(url).origin,base);
 const https=require('node:https');
 return new Promise((resolve,reject)=>{
  const req=https.request({hostname:'127.0.0.1',port:443,path:new URL(url).pathname+new URL(url).search,
   method:options.method||'GET',headers:{...options.headers,Host:'app.hakase-uranai.jp'},rejectUnauthorized:false},res=>{
   const chunks=[];res.on('data',c=>chunks.push(c));res.on('end',()=>resolve({status:res.statusCode,headers:res.headers,body:Buffer.concat(chunks)}));
  });req.on('error',reject);if(options.body)req.write(options.body);req.end();
 });
}

const sleep = ms => new Promise(resolve=>setTimeout(resolve,ms));
async function freePort(port) {
 await new Promise((resolve,reject)=>{
  const server = net.createServer(); server.once('error',()=>reject(new Error('Test port already in use: '+port)));
  server.listen(port,'127.0.0.1',()=>server.close(resolve));
 });
}
function start(executable,args,cwd) {
 const child = spawn(executable,args,{cwd,env,windowsHide:true,stdio:['ignore','pipe','pipe']});
 children.push(child);
 // Deliberately do not persist request logs or process streams as test artifacts.
 child.stdout.on('data',()=>{}); child.stderr.on('data',()=>{});
 child.on('error',()=>errors.push('Test server process failed to start'));
 return child;
}
async function ready(url) {
 for(let i=0;i<90;i++) {
  if(children.some(c=>c.exitCode!==null))throw new Error('Test server exited before becoming ready');
  try {const response=await fetch(url);if(response.ok)return;}catch{}
  await sleep(500);
 }
 throw new Error('Test server readiness timeout');
}
function record(device,flow) { results.push({device,flow,passed:true}); console.log(device+': '+flow+' PASS'); }

(async()=>{
 let browser;
 try {
  await freePort(8765); await freePort(3000); if(production)await freePort(443);
  const password = randomBytes(24).toString('base64url');
  const users = ['pc-a','pc-b','mobile-a','mobile-b'].map(name=>({email:'phase7a.'+name+'@example.test',password}));
  const setup = spawnSync(python,['-B','-c',"import json,sys; from auth_service import AuthRepository; r=AuthRepository(); print(json.dumps([r.create_user(u['email'],u['password']) for u in json.load(sys.stdin)]))"],
   {cwd:root,env,windowsHide:true,encoding:'utf8',input:JSON.stringify(users)});
  if(setup.status!==0)throw new Error('Disposable test account creation failed');
  const identities = JSON.parse(setup.stdout);
  start(python,['-B','fortune-next-app/backend/server.py'],root);
  await ready('http://127.0.0.1:8765/health');
  start(process.execPath,['node_modules/next/dist/bin/next','start','-H','127.0.0.1','-p','3000'],path.join(root,'fortune-next-app'));
  await ready('http://127.0.0.1:3000');
  if(production) {
   env.FORTUNE_TEST_TLS_KEY=path.join(disposable,'test-only-key.pem');env.FORTUNE_TEST_TLS_CERT=path.join(disposable,'test-only-cert.pem');
   const certificate=spawnSync(process.env.FORTUNE_TEST_CERT_PYTHON,['-B','-c',[
    'import os,datetime,ipaddress',
    'from pathlib import Path',
    'from cryptography import x509',
    'from cryptography.hazmat.primitives import hashes,serialization',
    'from cryptography.hazmat.primitives.asymmetric import rsa',
    'from cryptography.x509.oid import NameOID',
    'key=rsa.generate_private_key(public_exponent=65537,key_size=2048)',
    'name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,"app.hakase-uranai.jp")])',
    'now=datetime.datetime.now(datetime.timezone.utc)',
    'cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=5)).not_valid_after(now+datetime.timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName("app.hakase-uranai.jp"),x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),critical=False).sign(key,hashes.SHA256())',
    'Path(os.environ["FORTUNE_TEST_TLS_KEY"]).write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))',
    'Path(os.environ["FORTUNE_TEST_TLS_CERT"]).write_bytes(cert.public_bytes(serialization.Encoding.PEM))'
   ].join('\n')],{env,windowsHide:true,encoding:'utf8'});
   if(certificate.status!==0)throw new Error('Local test certificate generation failed');
   start(process.execPath,['tests/local_https_proxy.cjs'],root);
   for(let i=0;i<60;i++){try{if((await localTls(base+'/')).status===200)break;}catch{} if(i===59)throw new Error('Local TLS readiness timeout');await sleep(500);}
  }
  browser = await chromium.launch({channel:'msedge',headless:true,args:production?['--host-resolver-rules=MAP app.hakase-uranai.jp 127.0.0.1','--no-proxy-server']:[]});
  for(const [device,width,height,index] of [['PC',1280,900,0],['mobile',375,812,2]]) {
   const context = await browser.newContext({viewport:{width,height},acceptDownloads:true,ignoreHTTPSErrors:production});
   if(production)await context.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());
   const page = await context.newPage(); page.on('pageerror',()=>errors.push(device+': browser runtime error'));
   const call = async(method,url,options={})=>{
    if(!production)return page.request[method.toLowerCase()](url,options);
    assert.equal(new URL(url).origin,base);
    const result=await page.evaluate(async({url,method,options})=>{
     const response=await fetch(url,{method,credentials:'same-origin',headers:{'Content-Type':'application/json',...options.headers},...(options.data?{body:JSON.stringify(options.data)}:{})});
     return {status:response.status,text:await response.text()};
    },{url,method,options});
    return {status:()=>result.status,json:async()=>JSON.parse(result.text)};
   };
   const request={get:(url,options)=>call('GET',url,options),post:(url,options)=>call('POST',url,options)};
   const checkWidth = async()=>assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=width,'horizontal overflow');
   const calculate = async()=>{
    await page.goto(base,{waitUntil:'networkidle'});
    for(const [label,value] of [['姓','認証試験'+device],['名','太郎'],['生年月日','1988-08-12'],['出生時刻','09:00'],['鑑定日','2026-10-05']])await page.getByLabel(label,{exact:true}).fill(value);
    await page.getByLabel('出生地').selectOption('東京都'); await page.getByLabel('性別').selectOption('男性');
    const pending = page.waitForResponse(r=>r.url().endsWith('/api/fortune'));
    await page.getByRole('button',{name:'鑑定結果を表示する',exact:true}).click();
    const response = await pending; assert.equal(response.status(),200);
    const result = await response.json(); assert.equal(result.ok,true);
    await page.waitForURL('**/result'); await page.locator('.gogyoFigure').first().waitFor();
    await checkWidth(); return result;
   };
   const login = async who=>{
    await page.goto(base+'/login',{waitUntil:'networkidle'});
    await page.getByLabel('メールアドレス',{exact:true}).fill(users[who].email);
    await page.getByLabel('パスワード',{exact:true}).fill(password);
    await page.getByRole('button',{name:'ログイン',exact:true}).click();
    await page.waitForURL(base+'/'); await page.getByText(users[who].email+' でログイン中',{exact:true}).waitFor();
   };
   const logout = async()=>{
    await page.getByRole('button',{name:'ログアウト',exact:true}).click();
    await page.waitForURL(base+'/'); await page.getByRole('link',{name:'ログイン',exact:true}).waitFor();
   };
   const anonymous = await calculate();
   assert.equal(anonymous.excel_export_token,undefined);
   assert.equal(await page.getByRole('button',{name:'鑑定書を出力',exact:true}).count(),0);
   assert.equal(await page.getByRole('button',{name:'鑑定結果を保存',exact:true}).count(),0);
   await page.getByRole('link',{name:'ログインへ',exact:true}).first().waitFor();
   await page.screenshot({path:path.join(out,device+'_anonymous.png')}); record(device,'anonymous fortune and login guidance');
   await page.goto(base+'/history',{waitUntil:'networkidle'}); await page.getByRole('link',{name:'ログインへ',exact:true}).waitFor();
   assert.equal((await request.get(base+'/api/history')).status(),401); record(device,'anonymous history denied');
   await page.goto(base+'/login',{waitUntil:'networkidle'});
   await page.getByLabel('メールアドレス',{exact:true}).fill(users[index].email);
   await page.getByLabel('パスワード',{exact:true}).fill(randomBytes(20).toString('base64url'));
   await page.getByRole('button',{name:'ログイン',exact:true}).click();
   await page.getByRole('alert').filter({hasText:'メールアドレスまたはパスワードが正しくありません'}).waitFor();
   await checkWidth(); await page.screenshot({path:path.join(out,device+'_login_error.png')}); record(device,'login error and responsive form');
   await login(index); await checkWidth(); record(device,'A login and logged-in display');
   const cookies = await context.cookies(); const session = cookies.find(c=>c.name==='fortune_session');
   assert.ok(session.httpOnly); assert.equal(session.sameSite,'Lax'); assert.equal(session.secure,production);
   assert.equal(await page.evaluate(()=>document.cookie.includes('fortune_session')),false);
   const current = await request.get(base+'/api/auth/me'); assert.equal((await current.json()).data.user.id,identities[index].id);
   const calculated = await calculate(); assert.ok(calculated.excel_export_token);
   const exportReport = async (format,label)=>{
    await page.getByRole('button',{name:'鑑定書を出力',exact:true}).click();
    const capability = await request.get(base+'/api/export-capabilities');
    assert.equal(capability.status(),200);
    assert.equal((await capability.json()).data.pdf_available,env.FORTUNE_PDF_CONVERTER==='windows_excel');
    if(format==='pdf' && env.FORTUNE_PDF_CONVERTER==='disabled') {
     const pdf = page.getByRole('button',{name:'PDF（現在利用できません）',exact:true});
     await pdf.waitFor(); assert.equal(await pdf.isDisabled(),true);
     assert.equal(await page.getByRole('button',{name:'Excelで出力',exact:true}).isEnabled(),true);
     await checkWidth(); await page.screenshot({path:path.join(out,device+'_'+label+'_pdf_disabled.png')});
     await page.getByRole('button',{name:'鑑定書を出力',exact:true}).click();
     record(device,label+' PDF disabled and Excel enabled'); return;
    }
    const pending = page.waitForEvent('download',{timeout:150000});
    await page.getByRole('button',{name:(format==='excel'?'Excel':'PDF')+'で出力',exact:true}).click();
    const download = await pending;
    const filename = path.join(out,device+'_'+label+'.'+(format==='excel'?'xlsx':'pdf'));
    await download.saveAs(filename);
    assert.equal(fs.readFileSync(filename).subarray(0,format==='excel'?2:5).toString(),format==='excel'?'PK':'%PDF-');
    await checkWidth(); record(device,label+' '+format+' actual download');
   };
   await exportReport('excel','unsaved'); await exportReport('pdf','unsaved');
   const saveResponse = page.waitForResponse(r=>r.url().endsWith('/api/history')&&r.request().method()==='POST');
   await page.getByRole('button',{name:'鑑定結果を保存',exact:true}).click();
   const savedResponse = await saveResponse; assert.equal(savedResponse.status(),200);
   const reading = (await savedResponse.json()).data;
   await page.getByText('保存済み',{exact:false}).first().waitFor(); record(device,'A reading saved');
   await page.goto(base+'/history',{waitUntil:'networkidle'});
   await page.locator(width<760?'.historyMobile':'.historyDesktop').getByText('認証試験'+device+'太郎',{exact:true}).waitFor(); await checkWidth();
   await page.screenshot({path:path.join(out,device+'_history.png')}); record(device,'A history list');
   await page.goto(base+'/history/'+reading.id,{waitUntil:'networkidle'}); await page.locator('.gogyoFigure').first().waitFor();
   await exportReport('excel','saved'); await exportReport('pdf','saved');
   await page.screenshot({path:path.join(out,device+'_result.png')});
   await page.locator('#memo').evaluate(e=>{e.open=true;});
   await page.getByLabel('鑑定者用メモの自由記入欄').fill(device+' predeploy memo');
   const memoResponse=page.waitForResponse(r=>r.url().endsWith('/memo')&&r.request().method()==='PATCH');
   await page.getByRole('button',{name:'メモの変更を保存',exact:true}).click();
   assert.equal((await (await memoResponse).json()).data.memo,device+' predeploy memo');
   await page.reload({waitUntil:'networkidle'});await page.locator('#memo').evaluate(e=>{e.open=true;});
   assert.equal(await page.getByLabel('鑑定者用メモの自由記入欄').inputValue(),device+' predeploy memo');record(device,'memo persists');
   await page.getByRole('button',{name:'この人を再鑑定',exact:true}).click();
   await page.getByRole('button',{name:'過去履歴を引き継いで再鑑定',exact:true}).click();await page.waitForURL(base+'/');
   await page.getByLabel('鑑定日',{exact:true}).fill('2026-10-06');
   await page.getByRole('button',{name:'鑑定結果を表示する',exact:true}).click();await page.waitForURL('**/result');
   const rerunSave=page.waitForResponse(r=>r.url().endsWith('/api/history')&&r.request().method()==='POST');
   await page.getByRole('button',{name:'鑑定結果を保存',exact:true}).click();const second=(await (await rerunSave).json()).data;
   assert.equal(second.group_id,reading.group_id);assert.notEqual(second.id,reading.id);record(device,'re-reading and save');
   await page.goto(base+'/history',{waitUntil:'networkidle'});
   const entry=page.locator(width<760?'.historyMobile .historyCard':'.historyDesktop tbody tr').filter({has:page.locator('a[href="/history/'+second.id+'"]')});
   await entry.getByRole('button',{name:/のメニュー/}).click();await entry.getByRole('button',{name:'削除',exact:true}).click();
   const deletion=page.waitForResponse(r=>r.url().endsWith('/'+second.id)&&r.request().method()==='DELETE');
   await page.getByRole('dialog').getByRole('button',{name:'削除する',exact:true}).click();assert.equal((await deletion).status(),200);
   assert.equal((await request.get(base+'/api/history/'+second.id)).status(),404);assert.equal((await request.get(base+'/api/history/'+reading.id)).status(),200);record(device,'soft delete preserves other reading');
   // Delayed A responses must not repopulate shared React state after logout.
   await page.goto(base,{waitUntil:'networkidle'});
   await page.getByLabel('姓',{exact:true}).fill('遅延試験'+device);
   await page.getByLabel('生年月日',{exact:true}).fill('1988-08-12');
   await page.getByLabel('出生時刻',{exact:true}).fill('09:00');
   await page.getByLabel('鑑定日',{exact:true}).fill('2026-10-05');
   let delayedRoute, delayedResponse, notify;
   const intercepted = new Promise(resolve=>{notify=resolve;});
   await page.route('**/api/fortune',async route=>{delayedRoute=route;delayedResponse=production?await localTls(route.request().url(),{method:'POST',headers:await route.request().allHeaders(),body:route.request().postData()}):await route.fetch();notify();});
   await page.getByRole('button',{name:'鑑定結果を表示する',exact:true}).click();
   await intercepted;
   await logout(); assert.equal((await request.get(base+'/api/auth/me')).status(),401); record(device,'logout and session revocation');
   await delayedRoute.fulfill(production?delayedResponse:{response:delayedResponse}); await page.unroute('**/api/fortune');
   await sleep(500); assert.equal(page.url(),base+'/'); record(device,'late A response discarded after logout');
   await login(index+1); record(device,'B login');
   await page.goto(base+'/history',{waitUntil:'networkidle'}); await page.getByText('該当する鑑定履歴はありません。',{exact:true}).waitFor();
   assert.equal(await page.getByText('認証試験'+device+'太郎',{exact:true}).count(),0);
   const direct = await request.get(base+'/api/history/'+reading.id); assert.equal(direct.status(),404);
   for(const format of ['excel','pdf']) {
    for(const source of [{reading_id:reading.id},{export_token:calculated.excel_export_token}]) {
     const response = await request.post(base+'/api/export/'+format,{data:source,headers:{Origin:base}});
     assert.equal(response.status(),404);
    }
   }
   await page.goto(base+'/history/'+reading.id,{waitUntil:'networkidle'});
   await page.getByRole('alert').filter({hasText:'鑑定履歴が見つかりません'}).waitFor(); await checkWidth();
   record(device,'B cannot list/open/export A reading or token');
   await logout(); await context.close();
  }
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'ui_verification.json'),JSON.stringify({passed:results.length,results,errors},null,2));
  console.log('UI/E2E PASS '+results.length+' checks. Artifacts: '+out);
 } finally {
  if(browser)await browser.close();
  for(const child of children.reverse()) {
   if(child.exitCode===null)spawnSync('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});
  }
 }
})().catch(error=>{console.error('UI/E2E FAIL: '+error.message);process.exitCode=1;});
