// Built frontend + synthetic intercepted API. No real users, DB, SMTP or tokens.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),net=require('node:net');
const root=path.resolve(__dirname,'..'),web=path.join(root,'fortune-next-app');
const port=Number(process.env.FORTUNE_INVITE_UI_PORT||13424),base=`http://127.0.0.1:${port}`;
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let server,browser,passed=0;
async function check(label,fn){await fn();passed++;console.log(label+' PASS');}
(async()=>{
try{
 await new Promise((resolve,reject)=>{const probe=net.createServer();probe.once('error',reject);probe.listen(port,'127.0.0.1',()=>probe.close(resolve));});
 server=spawn(process.execPath,['node_modules/next/dist/bin/next','start','-H','127.0.0.1','-p',String(port)],{cwd:web,windowsHide:true,stdio:'ignore'});
 let ready=false;for(let i=0;i<80;i++){if(server.exitCode!==null)throw new Error('Owned web server exited');try{if((await fetch(base+'/login')).ok){ready=true;break;}}catch{}await sleep(300);}
 assert(ready,'Owned frontend readiness');
 browser=await chromium.launch({channel:'msedge',headless:true});
 for(const width of [1280,375]){
  const context=await browser.newContext({viewport:{width,height:1000}}),page=await context.newPage();
  let role='operator',invitations=[],sent=0,cancelled=0;
  page.on('dialog',dialog=>dialog.accept());
  await page.route('**/api/**',async route=>{
   const request=route.request(),url=new URL(request.url()),p=url.pathname;
   const fulfill=(data,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(status===200?{ok:true,data}:{ok:false,error:'運営権限がありません。'})});
   if(p==='/api/auth/me')return fulfill({user:{id:'synthetic-'+role,email:role+'@example.test'}});
   if(p.startsWith('/api/operations/')&&role!=='operator')return fulfill(null,403);
   if(p==='/api/operations/organizations')return fulfill([{id:'synthetic-org',display_name:'合成先生教室',slug:'synthetic',students:0,executions_this_month:0,executions_total:0}]);
   if(p==='/api/operations/invitations'&&request.method()==='POST'){
    const body=request.postDataJSON();assert.equal(body.recipient_confirmed,true);assert.equal(body.free_trial_confirmed,true);assert.equal(body.organization_id,'synthetic-org');
    assert(!('password' in body));assert.equal(body.alias,sent===0?'teacher-custom-42':'合成 生徒 2026');assert.equal(body.role,sent===0?'teacher':'student');sent++;
    invitations.push({id:'invite-'+sent,organization_id:body.organization_id,alias:body.alias,role:body.role,email:body.email,delivery_state:'provider_accepted',setup_state:'pending',expires_at:null,mailbox_delivery_confirmed:false});
    return fulfill({id:'invite-'+sent,delivery_state:'queued'});
   }
   if(p==='/api/operations/invitations')return fulfill(invitations);
   if(p.endsWith('/resend')){assert.equal(request.postDataJSON().recipient_confirmed,true);sent++;return fulfill({delivery_state:'queued'});}
   if(p.endsWith('/cancel')){cancelled++;invitations[0].setup_state='cancelled';return fulfill(null);}
   if(p==='/api/account/summary')return fulfill({is_operator:role==='operator',memberships:[]});
   return fulfill([]);
  });
  await page.goto(base+'/operations');
  const panel=page.getByRole('region',{name:'ユーザー招待'});
  await panel.getByRole('heading',{name:'ユーザー招待',exact:true}).waitFor();
  await check(width+' no name/address precreated',async()=>{assert.equal(await panel.getByLabel('招待対象の名前').inputValue(),'');assert.equal(await panel.getByLabel('メールアドレス',{exact:true}).inputValue(),'');assert.equal(sent,0);});
  await panel.getByLabel('招待対象の名前').fill('teacher-custom-42');
  await panel.getByLabel('所属する教室・講師名').selectOption('synthetic-org');
  await panel.getByLabel('メールアドレス',{exact:true}).fill('teacher.synthetic@example.test');
  await panel.getByRole('checkbox').check();
  await panel.getByRole('button',{name:'招待メールを送信',exact:true}).click();
  await check(width+' teacher invitation accepted honestly',()=>panel.getByText('メール：送信受付済み（到達未確認）／設定：初回設定待ち').waitFor());
  await panel.getByLabel('招待対象の名前').fill('合成 生徒 2026');
  await check(width+' changing free name clears recipient and confirmation',async()=>{assert.equal(await panel.getByLabel('メールアドレス',{exact:true}).inputValue(),'');assert.equal(await panel.getByRole('checkbox').isChecked(),false);});
  await panel.getByLabel('利用者の役割').selectOption('student');
  await panel.getByLabel('メールアドレス',{exact:true}).fill('student.synthetic@example.test');
  await panel.getByRole('checkbox').check();
  await panel.getByRole('button',{name:'招待メールを送信',exact:true}).click();
  await check(width+' student invitation',()=>panel.getByText('student.synthetic@example.test',{exact:false}).last().waitFor());
  await panel.getByRole('button',{name:'招待を再送信',exact:true}).first().click();
  await check(width+' resend',async()=>assert.equal(sent,3));
  await panel.getByRole('button',{name:'招待を取消し',exact:true}).first().click();
  await check(width+' cancel',async()=>{await panel.getByText(/設定：招待取消し済み/).waitFor();assert.equal(cancelled,1);});
  await check(width+' mobile layout',async()=>assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)));
  if(process.env.FORTUNE_INVITE_UI_OUTPUT){fs.mkdirSync(process.env.FORTUNE_INVITE_UI_OUTPUT,{recursive:true});await page.screenshot({path:path.join(process.env.FORTUNE_INVITE_UI_OUTPUT,`invitation-${width}.png`),fullPage:true});}
  for(const next of ['teacher','student']){
   role=next;await page.goto(base+'/operations');
   await check(width+' '+next+' cannot see invitations',async()=>{await page.getByRole('alert').filter({hasText:'運営権限'}).first().waitFor();assert.equal(await page.getByRole('button',{name:'招待メールを送信',exact:true}).count(),0);});
  }
  await context.close();
 }
 console.log(JSON.stringify({passed,mock_api:true,real_smtp:false,live_accounts:false}));
}catch(error){console.error('Invitation UI failed: '+error.message);process.exitCode=1;}
finally{if(browser)await browser.close();if(server){server.kill();await Promise.race([new Promise(resolve=>server.once('exit',resolve)),sleep(3000)]);}}
})();
