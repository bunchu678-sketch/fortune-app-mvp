// K01/K03 rendered UI: localhost, synthetic responses, no existing DB or external service.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const {spawn,spawnSync}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),net=require('node:net');
const root=path.resolve(__dirname,'..'), web=path.join(root,'fortune-next-app');
const base='http://127.0.0.1:3115',org='11111111-1111-4111-8111-111111111111';
const output=fs.mkdtempSync(path.join(os.tmpdir(),'fortune-k01-k03-ui-'));
const fixture=spawnSync(path.join(root,'.venv','Scripts','python.exe'),['-X','utf8','-B','-c',"import sys,json;sys.path.insert(0,'tests');from history_cases import FORM;from fortune_service import calculate_fortune;print(json.dumps({str(y):{'form':{**FORM,'readingDate':str(y)+'-09-30'},'result':calculate_fortune({**FORM,'readingDate':str(y)+'-09-30'})} for y in (2026,2027)},ensure_ascii=False))"],{cwd:root,encoding:'utf8',windowsHide:true});
assert.equal(fixture.status,0);const fixtures=JSON.parse(fixture.stdout);
let server,browser,lastPage,lastLabel,passed=0;const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function check(label,fn){await fn();passed++;console.log(label+' PASS');}
(async()=>{try{
 await new Promise((resolve,reject)=>{const s=net.createServer();s.once('error',reject);s.listen(3115,'127.0.0.1',()=>s.close(resolve));});
 server=spawn(process.execPath,['node_modules/next/dist/bin/next','start','-H','127.0.0.1','-p','3115'],{cwd:web,windowsHide:true,stdio:'ignore'});
 for(let i=0;i<90;i++){try{if((await fetch(base+'/')).ok)break;}catch{}if(i===89)throw Error('Server not ready');await sleep(300);}
 browser=await chromium.launch({channel:'msedge',headless:true});
 for(const width of [1280,375]) for(const mode of ['b2c','b2b','prototype','history']) for(const year of [2026,2027]){
  const context=await browser.newContext({viewport:{width,height:950}}),page=await context.newPage();const item=fixtures[year];
  lastPage=page;lastLabel=width+' '+mode+' '+year;
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());if(url.origin!==base)return route.abort();
   if(!url.pathname.startsWith('/api/'))return route.continue();
   const send=body=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)}),ok=data=>send({ok:true,data});
   if(url.pathname==='/api/auth/me')return ok({authenticated:true,user:{id:'synthetic',email:'synthetic@example.test'}});
   if(url.pathname==='/api/history/candidates')return ok([]);
   if(url.pathname==='/api/export-capabilities')return ok({pdf_available:false});
   if(url.pathname.endsWith('/me'))return ok({role:'student',branding:{display_name:'合成教室'}});
   if(url.pathname==='/api/account/summary')return ok({memberships:[]});
   if(url.pathname.endsWith('/fortune'))return send(item.result);
   if(url.pathname==='/api/history/synthetic')return ok({id:'synthetic',person_id:'synthetic-person',group_id:'synthetic-group',reading_date:year+'-09-30',saved_at:'2026-10-09T00:00:00Z',input_snapshot:{form:item.form,manualChoices:{}},result_snapshot:item.result,memo:'合成自由メモ',updated_at:'2026-10-09T00:00:00Z',past_memos:[{id:'previous',reading_date:'2026-09-01',memo:'合成過去メモ',saved_at:'2026-09-01'}]});
   return route.fulfill({status:404,contentType:'application/json',body:'{"ok":false}'});
  });
  if(mode==='history')await page.goto(base+'/history/synthetic',{waitUntil:'networkidle'});
  else{
   await page.goto(base+(mode==='prototype'?'/product':mode==='b2b'?'/b2b/'+org:''),{waitUntil:'networkidle'});
   await page.getByLabel('鑑定日',{exact:true}).fill(year+'-09-30');
   await page.getByRole('button',{name:mode==='prototype'?'鑑定する':'鑑定結果を表示する',exact:true}).click();
   await page.waitForURL(mode==='prototype'?'**/product/result':'**/result');
  }
  const section=page.locator('#overall');await section.waitFor();
  const label=width+' '+mode+' '+year;
  await check(label+' annual text',async()=>{
   assert((await section.innerText()).includes(year+'年'));
   assert((await section.innerText()).includes(item.result.yearly_overall.year_kanchi));
   if(year===2026)assert((await section.innerText()).includes(item.result.yearly_overall.comment));
   else{assert((await section.innerText()).includes('この年の正式解説は未登録です'));assert(!(await section.innerText()).includes('2026年行動アドバイス'));assert(!(await section.innerText()).includes('テーマ：'));}
  });
  await check(label+' memo retained',async()=>{
   if(mode==='prototype'){assert((await page.locator('#memo').innerText()).includes('未設定'));return;}
   await page.locator('#memo summary').click();assert((await page.locator('#memo').innerText()).includes('未設定'));
   const memo=page.getByLabel('鑑定者用メモの自由記入欄');await memo.fill('合成追記メモ');assert.equal(await memo.inputValue(),'合成追記メモ');
   if(mode==='history')assert((await page.locator('#memo').innerText()).includes('合成過去メモ'));
  });
  await check(label+' runtime/width',async()=>{assert.deepEqual(errors,[]);assert((await page.evaluate(()=>document.documentElement.scrollWidth))<=width);});
  await section.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,label.replaceAll(' ','_')+'.png')});await context.close();
 }
 console.log('K01/K03 UI: '+passed+'/48 PASS; screenshots: '+output);
}catch(e){console.error('K01/K03 UI FAIL '+lastLabel+': '+e.message);if(lastPage){console.error((await lastPage.locator('body').innerText()).slice(0,1600));await lastPage.screenshot({path:path.join(output,'failure.png')});}process.exitCode=1;}
finally{if(browser)await browser.close();if(server&&server.exitCode===null){spawnSync('taskkill',['/PID',String(server.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});}}
})();
