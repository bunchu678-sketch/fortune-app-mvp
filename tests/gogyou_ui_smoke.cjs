// Adopted A/B/C UI contract. Synthetic API responses are produced by the real
// calculator; independent numerical/boundary expectations remain in Tier A.
// Own localhost frontend; no DB, SMTP, external origins, or existing servers.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),net=require('node:net');
const {spawn,spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:3116';
const output=fs.mkdtempSync(path.join(os.tmpdir(),'fortune-abc-ui-'));
const generated=spawnSync(path.join(root,'.venv','Scripts','python.exe'),['-X','utf8','-B','-c',[
 "import sys,json;sys.path.insert(0,'tests')",
 "from report_export_cases import FORM",
 "from fortune_service import calculate_fortune",
 "from calendar_reference import get_calendar_context_for_birth_year",
 "boundary=get_calendar_context_for_birth_year(2020)['risshun_datetime'].isoformat()",
 "forms={'normal':FORM,'no-daiun':{**FORM,'gender':'未選択'},'pending':{**FORM,'readingDate':'2020-02-04','productAutoBoundary':False,'includeKanteiYearGogyoEffects':False}}",
 "forms.update({c:{**FORM,'readingDate':'2020-02-04','productAutoBoundary':False,'boundarySelections':{'reading':{'boundary_datetime':boundary,'choice':c}}} for c in ('before','after')})",
 "print(json.dumps({k:{'form':v,'result':calculate_fortune(v)} for k,v in forms.items()},ensure_ascii=False))"
].join('\n')],{cwd:root,windowsHide:true,encoding:'utf8'});
assert.equal(generated.status,0,generated.stderr);const fixtures=JSON.parse(generated.stdout);
let server,browser,passed=0;
async function check(label,fn){await fn();passed++;console.log(label+' PASS');}
(async()=>{try{
 await new Promise((resolve,reject)=>{const s=net.createServer();s.once('error',reject);s.listen(3116,'127.0.0.1',()=>s.close(resolve));});
 server=spawn(process.execPath,['node_modules/next/dist/bin/next','start','-H','127.0.0.1','-p','3116'],{cwd:path.join(root,'fortune-next-app'),windowsHide:true,stdio:'ignore'});
 for(let i=0;i<100;i++){try{if((await fetch(base)).ok)break;}catch{}if(i===99)throw Error('Frontend not ready');await new Promise(r=>setTimeout(r,300));}
 browser=await chromium.launch({channel:'msedge',headless:true});
 for(const width of [1280,390,320])for(const [name,item] of Object.entries(fixtures)){
  const context=await browser.newContext({viewport:{width,height:950}}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>{
   const url=new URL(route.request().url());if(url.origin!==base)return route.abort();
   if(!url.pathname.startsWith('/api/'))return route.continue();
   const send=data=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
   if(url.pathname==='/api/fortune')return send(item.result);
   if(url.pathname==='/api/auth/me')return send({ok:true,data:{authenticated:false}});
   if(url.pathname==='/api/export-capabilities')return send({ok:true,data:{pdf_available:false}});
   return route.fulfill({status:401,contentType:'application/json',body:'{"ok":false}'});
  });
  await page.goto(base,{waitUntil:'networkidle'});
  for(const [label,key] of [['生年月日','birthDate'],['出生時刻','birthTime'],['鑑定日','readingDate']])await page.getByLabel(label,{exact:true}).fill(item.form[key]);
  await page.getByLabel('出生地').selectOption('東京都');await page.getByLabel('性別').selectOption(item.form.gender);
  await page.getByRole('button',{name:'鑑定結果を表示する',exact:true}).click();
  await page.waitForURL('**/result');await page.locator('#gogyo').waitFor();
  const label=width+' '+name,variants=item.result.gogyo_variants;
  await check(label+' A/B/C labels',async()=>{
   assert.equal(await page.locator('.gogyoVariant').count(),3);
   assert.deepEqual(await page.locator('.gogyoVariant h3').allTextContents(),['A. 元命式のみ','B. 元命式＋鑑定年','C. 元命式＋鑑定年＋大運']);
  });
  for(const [i,code] of ['A','B','C'].entries())await check(label+' '+code+' values/state',async()=>{
   const article=page.locator('.gogyoVariant').nth(i),v=variants[code];
   const expectedState=name==='pending'&&code!=='A'?'boundary_pending':name==='no-daiun'&&code==='C'?'unavailable':'available';
   assert.equal(v.status,expectedState);
   if(v.status==='available'){
    const expected=v.gogyo.chart_order.map(e=>e+String(Number(Number(v.gogyo.scores[e]).toFixed(1))));
    assert.deepEqual(await article.locator('.gogyoElement').allTextContents(),expected);
    assert.equal(await article.locator('svg[role="img"]').count(),1);
    if(code==='B'){const y=v.gogyo.kantei_year;assert((await article.innerText()).includes('鑑定年：'+y.tenkan+y.chishi));}
    if(code==='C')assert((await article.innerText()).includes('対象大運：'+v.daiun.name+' '+v.daiun.kanshi));
   }else{
    assert.equal(await article.locator('svg').count(),0);
    assert.equal(await article.getByRole('status').innerText(),v.status==='boundary_pending'?'節入りの確認後に算出します。':'大運を取得できないため算出できません。');
   }
  });
  if(['before','after'].includes(name))await check(label+' adopted boundary year',async()=>{
   const y=variants.B.gogyo.kantei_year;assert.equal(y.tenkan+y.chishi,name==='before'?'己亥':'庚子');
  });
  await check(label+' layout/runtime',async()=>{
   assert.deepEqual(errors,[]);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=width);
   for(const figure of await page.locator('.gogyoFigure').all()){const box=await figure.boundingBox();assert.ok(box.x>=0&&box.x+box.width<=width);}
  });
  await page.screenshot({path:path.join(output,width+'-'+name+'.png'),fullPage:true});await context.close();
 }
 console.log(JSON.stringify({passed,failed:0,output}));
}finally{if(browser)await browser.close();if(server?.pid)spawnSync('taskkill',['/PID',String(server.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});}})().catch(e=>{console.error(e);process.exitCode=1;});
