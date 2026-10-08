// Local W browser coverage. All auth/product/history responses are synthetic mocks.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),{spawn,spawnSync}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),net=require('node:net');
const snapshots=fs.mkdtempSync(path.join(require('node:os').tmpdir(),'fortune-phase9-ui-'));
const root=path.resolve(__dirname,'..'),web=path.join(root,'fortune-next-app');
const base='http://127.0.0.1:3112',org='11111111-1111-4111-8111-111111111111',other='22222222-2222-4222-8222-222222222222',student='33333333-3333-4333-8333-333333333333';
const ids={student,teacher:'44444444-4444-4444-8444-444444444444',admin:'55555555-5555-4555-8555-555555555555'};
const generated=path.join(web,'next-env.d.ts'),before=fs.readFileSync(generated);
let server,browser,passed=0;const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function check(label,fn){await fn();passed++;console.log(label+' PASS');}
const python=path.join(root,'.venv','Scripts','python.exe');
const calc=spawnSync(python,['-X','utf8','-B','-c',"import sys,json;sys.path.insert(0,'tests');from report_export_cases import FORM;from fortune_service import calculate_fortune;print(json.dumps(calculate_fortune(FORM),ensure_ascii=False))"],{cwd:root,encoding:'utf8',windowsHide:true});
if(calc.status!==0)throw new Error('Synthetic fortune fixture unavailable');
const fortune=JSON.parse(calc.stdout);
(async()=>{try{
 await new Promise((resolve,reject)=>{const s=net.createServer();s.once('error',reject);s.listen(3112,'127.0.0.1',()=>s.close(resolve));});
 server=spawn(process.execPath,['node_modules/next/dist/bin/next','dev','-H','127.0.0.1','-p','3112'],{cwd:web,windowsHide:true,stdio:['ignore','ignore','ignore']});
 let ready=false;for(let i=0;i<150;i++){if(server.exitCode!==null)throw new Error('Local UI server exited');try{if((await fetch(base+'/login')).ok){ready=true;break;}}catch{}await sleep(300);}assert(ready);
 browser=await chromium.launch({channel:'msedge',headless:true});
 for(const width of [1280,375]){
  const context=await browser.newContext({viewport:{width,height:950}});const page=await context.newPage();
  let who='student',suspended=false,unpaid=true,issued=false,organizationName='教室一',created=0,contractEnded=false,abortFortune=true;const executionKeys=[],savedBodies=[],writes=[];
  const totals={executions_this_month:17,executions_total:48,month_timezone:'Asia/Tokyo'};
  const organizations=()=>[{id:org,display_name:organizationName,slug:'one',students:1,...totals}];
  const members=()=>[{user_id:student,display_name:'合成生徒',email:'student@example.test',role:'student',account_state:suspended?'suspended':'active'}];
  const userDetail=()=>({id:student,email:'student@example.test',display_name:'合成生徒',account_state:suspended?'suspended':'active',setup_pending:true,last_login_at:'2026-10-08T00:00:00+00:00',last_execution_at:'2026-10-08T01:00:00+00:00',executions_this_month:7,executions_total:21,saved_histories_current:3,memberships:[{organization_id:org,display_name:organizationName,role:'student',monthly_fee:2000,contract_state:suspended?'suspended':'active',minimum_term_until:null}],dues:[{id:'due-one',organization_id:org,due_date:'2026-08-01',amount:2000,settled_at:unpaid?null:'2026-10-08T00:00:00+00:00'}]});
  await page.route('**/api/**',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname,method=req.method();let data={};
   const send=(value,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(value)});
   const ok=value=>send({ok:true,data:value});
   if(p==='/api/auth/me')return ok({authenticated:true,user:{id:ids[who],email:who+'@example.test'}});
   if(p==='/api/account/summary')return ok({email:who+'@example.test',is_operator:who==='admin',memberships:[{organization_id:org,display_name:organizationName,role:who==='teacher'?'teacher':'student'}],executions_this_month:7,executions_total:21,saved_histories_current:3,saved_histories_total:4,deleted_histories:1,month_timezone:'Asia/Tokyo'});
   if(p===`/api/b2b/organizations/${other}/teacher`||p===`/api/b2b/organizations/${other}/me`)return send({ok:false,error:'所属先を利用できません。'},403);
   if(p===`/api/b2b/organizations/${org}/teacher`)return who==='teacher'?ok({organization_id:org,display_name:organizationName,students:[{display_name:'合成生徒',account_state:'active'}],...totals}):send({ok:false,error:'先生権限がありません。'},403);
   if(p===`/api/b2b/organizations/${org}/me`)return ok({role:'student',branding:{display_name:organizationName}});
   if(p===`/api/b2b/organizations/${org}/fortune`){executionKeys.push(req.headers()['idempotency-key']);if(abortFortune){abortFortune=false;return route.abort('failed');}return send(fortune);}
   if(p==='/api/export-capabilities')return ok({pdf_available:false});
   if(p==='/api/history/candidates')return ok([]);
   if(p==='/api/history'&&method==='POST'){
    const body=req.postDataJSON();savedBodies.push(body);return ok({id:'66666666-6666-4666-8666-666666666666',person_id:'p',group_id:'g',reading_date:body.input_snapshot.form.readingDate,saved_at:'2026-10-08T00:00:00+00:00',updated_at:'2026-10-08T00:00:00+00:00',memo:'',input_snapshot:body.input_snapshot,result_snapshot:body.result_snapshot});
   }
   if(p.startsWith('/api/operations/')){
    if(who!=='admin')return send({ok:false,error:'運営権限がありません。'},403);
    if(method==='GET'){
     if(p==='/api/operations/organizations')return ok(organizations());
     if(p===`/api/operations/organizations/${org}`)return ok({...organizations()[0],logo_reference:null,members:members(),teacher_contracts:[{id:'contract-one',state:contractEnded?'terminated':'active'}]});
     if(p==='/api/operations/users')return ok([userDetail()]);
     if(p===`/api/operations/users/${student}`)return ok(userDetail());
     if(p==='/api/operations/audit')return ok([{id:'audit-one',action:'account-issue',actor_user_id:ids.admin,target_id:student,occurred_at:'2026-10-08T00:00:00+00:00'}]);
    }
    const body=req.postDataJSON();writes.push({p,body});
    if(p==='/api/operations/organizations'){created++;return ok({id:other,display_name:body.display_name,slug:body.slug});}
    if(p===`/api/operations/organizations/${org}`){organizationName=body.display_name;return ok(null);}
    if(p==='/api/operations/users'){assert.equal(body.initial_payment_confirmed,true);assert(!Object.hasOwn(body,'password'));issued=true;return ok({id:'new-user',setup_pending:true,mail_status:'disabled'});}
    if(p.endsWith('/teacher-contract')){contractEnded=true;return ok({id:'contract-one',state:'terminated'});}
    if(p.endsWith('/suspend')){suspended=true;return ok(null);}
    if(p.endsWith('/resume')){if(unpaid)return send({ok:false,error:'未納分の全額精算を確認してから再開してください。'},409);suspended=false;return ok(null);}
    if(p.endsWith('/settle')){unpaid=false;return ok(null);}
    if(p.endsWith('/setup-mail'))return ok({mail_status:'disabled'});
    return ok(null);
   }
   return ok([]);
  });
  page.on('dialog',dialog=>dialog.accept());
  await page.goto(base+'/mypage');
  await check(width+' personal execution distinct from saves',async()=>{await page.getByRole('heading',{name:'自分の利用状況'}).waitFor();const dl=page.locator('dl');assert((await dl.innerText()).includes('21件'));assert((await dl.innerText()).includes('3件'));});
  await check(width+' existing owner-history links reused',async()=>{assert.equal(await page.getByRole('link',{name:'自分の鑑定履歴'}).getAttribute('href'),'/history');assert.equal(await page.getByRole('link',{name:'削除した履歴を復旧',exact:true}).getAttribute('href'),'/history/deleted');});
  await check(width+' minimum account settings',async()=>{await page.getByRole('heading',{name:'アカウント設定'}).waitFor();assert.equal(await page.getByRole('link',{name:'パスワードを再設定'}).getAttribute('href'),'/forgot-password');});
  await page.screenshot({path:path.join(snapshots,width+'-mypage.png'),fullPage:true});
  who='teacher';await page.goto(base+'/teacher/'+org);await page.getByRole('heading',{name:'生徒一覧'}).waitFor();
  await check(width+' teacher aggregate includes own executions',async()=>assert((await page.locator('dl').innerText()).includes('48件')));
  await check(width+' teacher student names and states only',async()=>{const content=await page.locator('main').innerText();assert(content.includes('合成生徒'));for(const prohibited of ['最終login','最終鑑定','student@example.test','21件'])assert(!content.includes(prohibited));});
  await check(width+' teacher cannot issue or suspend users',async()=>{assert.equal(await page.getByRole('button',{name:/発行|停止|再開/}).count(),0);assert.equal(await page.locator('input').count(),0);});
  await page.screenshot({path:path.join(snapshots,width+'-teacher.png'),fullPage:true});
  await page.goto(base+'/teacher/'+other);
  await check(width+' unauthorized organization fails closed',()=>page.getByRole('alert').filter({hasText:'所属先を利用できません'}).waitFor());
  await page.goto(base+'/operations');
  await check(width+' teacher operator screen denied',async()=>{await page.getByRole('alert').filter({hasText:'運営権限'}).waitFor();assert.equal(await page.getByRole('button',{name:'作成する'}).count(),0);});
  who='admin';await page.goto(base+'/operations');await page.getByRole('heading',{name:'Organization作成'}).waitFor();
  await check(width+' operator organization and student totals',async()=>{const content=await page.locator('main').innerText();assert(content.includes('生徒1名'));assert(content.includes('今月17件'));});
  await page.getByLabel('名称',{exact:true}).fill('新教室');await page.getByLabel('識別名',{exact:true}).fill('new-class');await page.getByRole('button',{name:'作成する'}).click();
  await check(width+' operator organization create',async()=>{await page.getByRole('status').filter({hasText:'保存しました'}).waitFor();assert.equal(created,1);});
  await check(width+' management audit visible',()=>page.getByRole('heading',{name:'最近の管理操作'}).waitFor());
  await page.goto(base+'/operations/organizations/'+org);await page.getByRole('heading',{name:'Organization設定'}).waitFor();
  await page.getByLabel('表示名',{exact:true}).fill('更新教室');await page.getByRole('button',{name:'設定を保存'}).click();
  await check(width+' operator organization settings',async()=>{await page.getByRole('heading',{name:'更新教室',exact:true}).waitFor();});
  await page.getByLabel('氏名',{exact:true}).fill('新規生徒');await page.getByLabel('メールアドレス',{exact:true}).fill('new@example.test');await page.getByLabel('契約月額（円）',{exact:true}).fill('2000');
  await check(width+' account creation requires payment confirmation',async()=>assert(await page.getByRole('button',{name:'アカウントを発行'}).isDisabled()));
  await page.getByLabel('入金確認済み',{exact:true}).check();await page.getByRole('button',{name:'アカウントを発行'}).click();
  await check(width+' no password field and mail remains disabled',async()=>{await page.getByRole('status').filter({hasText:'未送信'}).waitFor();assert(issued);assert.equal(await page.locator('input[type=password]').count(),0);});
  await page.getByRole('button',{name:'提携終了を記録'}).click();
  await check(width+' teacher contract end keeps student list',async()=>{await page.getByText('契約：terminated',{exact:false}).waitFor();assert((await page.locator('main').innerText()).includes('合成生徒'));});
  await page.goto(base+'/operations/users/'+student);await page.getByRole('heading',{name:'利用停止・再開'}).waitFor();
  await check(width+' operator user metrics without private reading',async()=>{const content=await page.locator('main').innerText();assert(content.includes('最終login'));assert(content.includes('21件'));assert(!content.includes('PRIVATE-CONTENT'));assert.equal(await page.locator(`a[href='/history/${student}']`).count(),0);});
  await page.screenshot({path:path.join(snapshots,width+'-operator-user.png'),fullPage:true});
  await page.getByRole('button',{name:'利用を停止',exact:true}).click();
  await check(width+' stop transition reflected',async()=>{await page.waitForFunction(()=>document.querySelector('dd')?.textContent==='停止中');});
  await page.getByRole('button',{name:'利用を再開',exact:true}).click();
  await check(width+' unpaid resume refused',()=>page.getByRole('alert').filter({hasText:'全額精算'}).waitFor());
  await page.getByRole('button',{name:'全額精算を記録'}).click();await page.getByText(/精算済み/).waitFor();await page.getByRole('button',{name:'利用を再開',exact:true}).click();
  await check(width+' settlement then resume',async()=>{await page.waitForFunction(()=>document.querySelector('dd')?.textContent==='利用中');});
  await page.getByRole('button',{name:'初回設定メールを再送'}).click();
  await check(width+' setup mail disabled message',()=>page.getByRole('status').filter({hasText:'未送信'}).waitFor());
  await check(width+' management responsive layout',async()=>assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)));
  who='student';await page.goto(base+'/b2b/'+org);await page.getByRole('heading',{name:'更新教室',exact:true}).waitFor();
  await check(width+' B2B reuses canonical W input',async()=>{assert.equal(await page.getByRole('button',{name:'鑑定結果を表示する',exact:true}).count(),1);assert.equal(await page.getByLabel('特定の日時について占う').count(),0);assert((await page.locator('main').innerText()).includes('Powered by 博士の占いらぼ'));});
  await page.getByRole('button',{name:'鑑定結果を表示する',exact:true}).click();await page.locator('.formError').waitFor();await page.getByRole('button',{name:'鑑定結果を表示する',exact:true}).click();await page.waitForURL(base+'/result');
  await check(width+' network retry retains execution ID',async()=>{assert.equal(executionKeys.length,2);assert.equal(executionKeys[0],executionKeys[1]);assert.match(executionKeys[0],/^[a-f0-9-]{36}$/);});
  await page.getByRole('button',{name:'鑑定結果を保存',exact:true}).click();
  await check(width+' B2B save carries validated organization',async()=>{await page.getByRole('status').filter({hasText:'保存済み'}).waitFor();assert.equal(savedBodies[0].organization_id,org);});
  await check(width+' B2B result responsive layout',async()=>assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)));
  await page.screenshot({path:path.join(snapshots,width+'-b2b-result.png'),fullPage:true});
  await context.close();
 }
 console.log('Phase 9 management UI: '+passed+' PASS');console.log('Screenshots: '+snapshots);
}catch(error){console.error('Phase 9 UI failure: '+error.stack);process.exitCode=1;}
finally{if(browser)await browser.close();if(server){server.kill();await Promise.race([new Promise(r=>server.once('exit',r)),sleep(3000)]);}if(!fs.readFileSync(generated).equals(before))fs.writeFileSync(generated,before);}
})();
