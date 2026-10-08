// All APIs mocked, localhost only. Billing never sends mail or executes deletion.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),fs=require('node:fs'),path=require('node:path'),net=require('node:net');
const root=path.resolve(__dirname,'..'),web=path.join(root,'fortune-next-app'),base='http://127.0.0.1:3113';
const org='11111111-1111-4111-8111-111111111111',owner='33333333-3333-4333-8333-333333333333';
const generated=path.join(web,'next-env.d.ts'),before=fs.readFileSync(generated),shots=fs.mkdtempSync(path.join(require('node:os').tmpdir(),'fortune-billing-ui-'));
let server,browser,passed=0;const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function check(name,fn){await fn();passed++;console.log(name+' PASS');}
(async()=>{try{
 await new Promise((resolve,reject)=>{const s=net.createServer();s.once('error',reject);s.listen(3113,'127.0.0.1',()=>s.close(resolve));});
 server=spawn(process.execPath,['node_modules/next/dist/bin/next','dev','-H','127.0.0.1','-p','3113'],{cwd:web,windowsHide:true,stdio:'ignore'});
 let ready=false;for(let i=0;i<150;i++){if(server.exitCode!==null)throw new Error('UI server exited');try{if((await fetch(base+'/login')).ok){ready=true;break;}}catch{}await sleep(300);}assert(ready);
 browser=await chromium.launch({channel:'msedge',headless:true});
 for(const width of [1280,375]){
  const context=await browser.newContext({viewport:{width,height:950}}),page=await context.newPage();
  let who='student',state='active',requested=false,recovered=false,activated=false,paid='2026-10-31',unpaid=true;
  const writes=[],totals={executions_this_month:7,executions_total:21,month_timezone:'Asia/Tokyo'};
  const contract=()=>({state,activated_at:activated?'2026-10-20T01:00:00Z':null,monthly_fee:2000,first_billing_date:activated?'2026-11-01':null,next_billing_date:state==='active'&&!requested?(paid==='2026-11-30'?'2026-12-01':'2026-11-01'):null,paid_through:paid,suspended_at:state==='suspended'?'2026-10-20T01:00:00Z':null,cancellation_requested_at:requested?'2026-10-20T01:00:00Z':null,access_ends_at:requested?'2026-10-31T15:00:00Z':null,deletion_due_at:requested?'2026-11-30T15:00:00Z':null,recovered_at:recovered?'2026-11-01T15:00:00Z':null,deletion_hold:recovered,cancellation_needs_review:false,arrears:{suspension_due:false,reminder_due:false},deletion_plan:{reading_ids:['reading-one'],can_delete:false,blocked_dependencies:[]}});
  const member={organization_id:org,display_name:'合成教室',role:'student',monthly_fee:2000,contract_state:'active',minimum_term_until:null};
  await page.route('**/api/**',async route=>{
   const req=route.request(),p=new URL(req.url()).pathname,method=req.method();
   const send=(data,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(status===200?{ok:true,data}:{ok:false,error:data})});
   if(p==='/api/auth/me')return send({authenticated:true,user:{id:owner,email:who+'@example.test'}});
   if(p==='/api/account/summary')return send({email:'student@example.test',memberships:[member],is_operator:who==='admin',...totals,saved_histories_current:3});
   if(p.includes('/contract')||p.startsWith('/api/account/organizations/')){
    if(method==='GET')return send(contract());
    const body=req.postDataJSON();writes.push({p,body});
    if(p.endsWith('/activate'))activated=true;
    if(p.endsWith('/paid-period'))paid=body.paid_through;
    if(p.endsWith('/suspend'))state='suspended';
    if(p.endsWith('/resume')){if(unpaid)return send('未納分の全額精算を確認してから再開してください。',409);state='active';}
    if(p.endsWith('/cancellation'))requested=true;
    if(p.endsWith('/data-recovery'))recovered=true;
    return send(contract());
   }
   if(p==='/api/operations/users/'+owner)return send({id:owner,email:'student@example.test',display_name:'合成生徒',account_state:'active',setup_pending:false,last_login_at:null,last_execution_at:null,...totals,saved_histories_current:3,memberships:[member],dues:[]});
   if(p==='/api/operations/organizations')return send([{id:org,display_name:'合成教室',slug:'one',students:1,...totals}]);
   if(p==='/api/operations/users'||p==='/api/operations/audit')return send([]);
   return send([]);
  });
  page.on('dialog',dialog=>dialog.accept());
  await page.goto(base+'/mypage');const panel=page.locator('.serviceContract');await panel.getByRole('heading',{name:'自分の利用契約'}).waitFor();
  await check(width+' own contractual dates and no invoice history',async()=>{assert((await panel.innerText()).includes('2000円'));assert.equal(await panel.locator('input').count(),0);});
  await check(width+' cancellation uses own authenticated endpoint',async()=>{await panel.getByRole('button',{name:'正式解約を申請',exact:true}).click();await panel.getByRole('button',{name:'正式解約を申請',exact:true}).isDisabled().then(assert);assert(writes.at(-1).p===`/api/account/organizations/${org}/cancellation`);assert.deepEqual(writes.at(-1).body,{});});
  state='terminated';await page.reload();await panel.getByText('利用終了',{exact:true}).waitFor();
  await check(width+' recover data does not resume service',async()=>{await panel.getByRole('button',{name:'解約データの復旧を申請'}).click();await panel.getByText('データを復旧しました。アプリの利用は再開していません。').waitFor();assert.equal(state,'terminated');assert.equal(await panel.getByRole('button',{name:/この契約を再開/}).count(),0);});
  await page.screenshot({path:path.join(shots,width+'-student.png'),fullPage:true});
  who='admin';state='active';requested=false;recovered=false;await page.goto(base+'/operations/users/'+owner);await panel.getByRole('heading',{name:'利用契約・請求・保持'}).waitFor();
  await check(width+' explicit activation records actual eligibility',async()=>{await panel.getByRole('button',{name:'利用開始を確認'}).click();await panel.getByRole('button',{name:'利用開始を確認'}).isDisabled().then(assert);await panel.getByText('2026-11-01',{exact:true}).first().waitFor();});
  await check(width+' confirm paid period by existing operator API',async()=>{await panel.getByLabel('確認した支払済み期間末日').fill('2026-11-30');await panel.getByRole('button',{name:'支払済み期間を記録'}).click();await panel.getByText('2026-11-30',{exact:true}).waitFor();await panel.getByText('2026-12-01',{exact:true}).waitFor();assert.equal(writes.at(-1).body.paid_through,'2026-11-30');});
  await check(width+' suspension only selected organization',async()=>{await panel.getByRole('button',{name:'この契約を休止'}).click();await panel.getByText('停止中',{exact:true}).waitFor();assert(writes.at(-1).p.includes('/organizations/'+org+'/contract/suspend'));});
  await check(width+' unpaid resume rejected visibly',async()=>{await panel.getByRole('button',{name:'この契約を再開'}).click();await panel.getByRole('alert').filter({hasText:'全額精算'}).waitFor();assert.equal(state,'suspended');});
  unpaid=false;await panel.getByRole('button',{name:'この契約を再開'}).click();await panel.getByText('利用中',{exact:true}).waitFor();
  await check(width+' dry run no physical deletion or mail actions',async()=>{assert((await panel.innerText()).includes('削除ドライラン：対象履歴1件'));assert.equal(await panel.getByRole('button',{name:/物理削除|請求実行|督促送信/}).count(),0);});
  await check(width+' responsive fields no overflow',async()=>assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)));
  await page.screenshot({path:path.join(shots,width+'-operator.png'),fullPage:true});await context.close();
 }
 console.log('Billing UI checks '+passed+' PASS; screenshots '+shots);
}finally{if(browser)await browser.close();if(server&&server.exitCode===null){server.kill();await new Promise(r=>server.once('exit',r));}fs.writeFileSync(generated,before);}})().catch(e=>{console.error(e);process.exitCode=1;});
