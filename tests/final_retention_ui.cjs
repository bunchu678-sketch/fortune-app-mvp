// Mock APIs, local dev server, synthetic users only. No mail/deletion execution.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),fs=require('node:fs'),path=require('node:path'),net=require('node:net');
const root=path.resolve(__dirname,'..'),web=path.join(root,'fortune-next-app'),base='http://127.0.0.1:3114';
const generated=path.join(web,'next-env.d.ts'),before=fs.readFileSync(generated),shots=fs.mkdtempSync(path.join(require('node:os').tmpdir(),'fortune-final-retention-'));
const org='11111111-1111-4111-8111-111111111111',owner='33333333-3333-4333-8333-333333333333';
let server,browser,passed=0;const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function check(name,fn){await fn();passed++;console.log(name+' PASS');}
(async()=>{try{
 await new Promise((resolve,reject)=>{const s=net.createServer();s.once('error',reject);s.listen(3114,'127.0.0.1',()=>s.close(resolve));});
 server=spawn(process.execPath,['node_modules/next/dist/bin/next','dev','-H','127.0.0.1','-p','3114'],{cwd:web,windowsHide:true,stdio:'ignore'});
 let ready=false;for(let i=0;i<150;i++){if(server.exitCode!==null)throw new Error('UI server exited');try{if((await fetch(base+'/login')).ok){ready=true;break;}}catch{}await sleep(300);}assert(ready);
 browser=await chromium.launch({channel:'msedge',headless:true});
 for(const width of [1280,375]){
  const context=await browser.newContext({viewport:{width,height:950}}),page=await context.newPage();let who='admin',proofs=[];const writes=[];
  await page.route('**/api/**',async route=>{
   const req=route.request(),p=new URL(req.url()).pathname,method=req.method();
   const send=(data,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(status===200?{ok:true,data}:{ok:false,error:data})});
   if(p==='/api/auth/me')return send({authenticated:true,user:{id:'admin',email:'admin@example.test'}});
   if(p.startsWith('/api/operations/')&&who!=='admin')return send('運営権限がありません。',403);
   if(method==='POST')writes.push({p,body:req.postDataJSON()});
   if(p==='/api/operations/purchases'){if(method==='POST'){proofs=[req.postDataJSON()];return send({purchase_number:'P-001'});}return send(proofs);}
   if(p.endsWith('/recontract'))return send({setup_pending:true,mail_delivery:'disabled',initial_fee_required:false,deleted_history_restorable:false});
   if(p==='/api/account/summary')return send({email:'admin@example.test',is_operator:who==='admin',memberships:[],executions_total:0,executions_this_month:0,saved_histories_current:0});
   if(p==='/api/operations/organizations')return send([{id:org,display_name:'合成教室',students:1,executions_total:2,executions_this_month:1}]);
   if(p==='/api/operations/users/'+owner)return send({id:owner,email:'student@example.test',display_name:'合成生徒',account_state:'active',last_login_at:null,last_execution_at:null,memberships:[],dues:[],executions_total:1,executions_this_month:1,saved_histories_current:0});
   if(p.endsWith('/retention'))return send({can_delete:false,blockers:['b2c_active_or_unknown'],automatic_actions_enabled:false});
   if(p.endsWith('/b2c-retention'))return send(null);
   return send([]);
  });page.on('dialog',d=>d.accept());
  await page.goto(base+'/operations');const section=page.locator('section').filter({has:page.getByRole('heading',{name:'初期購入証明・再契約',exact:true})});await section.waitFor();
  await check(width+' no erased-history recovery claim',async()=>{assert((await section.innerText()).includes('削除済み鑑定履歴は復元できません'));assert.equal(await page.getByRole('button',{name:'物理削除',exact:true}).count(),0);});
  await section.getByText('手動確認済みの購入証明を登録',{exact:true}).click();
  await check(width+' proof registration requires review and payment',async()=>{
   await section.getByLabel('購入番号',{exact:true}).fill('P-001');await section.getByLabel('購入した先生版アプリ').selectOption(org);
   await section.getByLabel('購入日',{exact:true}).fill('2026-01-01');await section.getByLabel('購入者確認メール').fill('student@example.test');
   await section.getByLabel('購入証明の保持見直し日').fill('2028-12-31');await section.getByLabel('初期購入費用の入金確認済み').check();
   await section.getByRole('button',{name:'購入証明を登録',exact:true}).click();await section.getByText('記録しました。',{exact:true}).waitFor();
   assert.equal(writes.at(-1).body.payment_confirmed,true);assert.equal(writes.at(-1).body.review_on,'2028-12-31');assert.equal(writes.at(-1).body.user_id,null);
  });
  await section.getByText('購入証明・本人確認後の再契約',{exact:true}).click();
  await check(width+' recontract explicit identity and monthly confirmation',async()=>{
   await section.getByLabel('再契約の購入番号').fill('P-001');await section.getByLabel('再契約する先生版アプリ').selectOption(org);
   await section.getByLabel('本人確認したメール').fill('student@example.test');await section.getByLabel('再契約者氏名').fill('合成利用者');
   await section.getByLabel('再契約の支払済み期間末日').fill('2027-01-31');await section.getByLabel('購入証明と本人確認済み').check();await section.getByLabel('月額料金の入金確認済み').check();
   await section.getByRole('button',{name:'再契約を記録',exact:true}).click();await section.getByText(/初回設定メールは未送信です/).waitFor();
   assert.equal(writes.at(-1).body.identity_verified,true);assert.equal(writes.at(-1).body.monthly_payment_confirmed,true);assert(writes.at(-1).p.endsWith('/P-001/recontract'));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2));
   await page.screenshot({path:path.join(shots,width+'-purchase.png'),fullPage:true});
  });
  await check(width+' account retention conservative dry run',async()=>{
   await page.goto(base+'/operations/users/'+owner);await page.getByRole('heading',{name:'User保持の確認'}).waitFor();await page.getByText(/B2C利用中または未確認/).waitFor();
   await page.getByLabel('本人確認済みB2C利用状況').selectOption('inactive');await page.getByRole('button',{name:'B2C利用状況を記録'}).click();await page.getByText('利用状況の確認を記録しました。').waitFor();assert.deepEqual(writes.at(-1).body,{state:'inactive'});
  });
  await check(width+' mobile/PC no horizontal overflow',async()=>{assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2));});
  await page.screenshot({path:path.join(shots,width+'-retention.png'),fullPage:true});
  await check(width+' teacher cannot see purchase controls',async()=>{who='teacher';await page.goto(base+'/operations');await page.getByText('運営権限がありません。').first().waitFor();assert.equal(await page.getByRole('heading',{name:'初期購入証明・再契約'}).count(),0);});
  await context.close();
 }
 console.log('Browser checks '+passed+'/'+passed);console.log('Screenshots '+shots);
}finally{if(browser)await browser.close();if(server&&server.exitCode===null){server.kill();await new Promise(r=>server.once('exit',r));}fs.writeFileSync(generated,before);}})().catch(e=>{console.error(e);process.exitCode=1;});
