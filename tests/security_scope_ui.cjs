// Built Next.js + synthetic API and header proxy. No real users, DB or SMTP.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),http=require('node:http'),net=require('node:net');
const {spawn}=require('node:child_process'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),web=path.join(root,'fortune-next-app');
const nextPort=13427,proxyPort=13428,parentPort=13429,base=`http://127.0.0.1:${proxyPort}`;
const output=process.env.FORTUNE_SECURITY_UI_OUTPUT;assert(output,'Explicit private output directory required');
const fixture=JSON.parse(fs.readFileSync(path.join(output,'fixture.json'),'utf8')),xlsx=fs.readFileSync(path.join(output,'fixture.xlsx'));
const snippet=fs.readFileSync(path.join(root,'deployment/security/fortune-security-teacher.conf'),'utf8');
const headers={};for(const match of snippet.matchAll(/^add_header (\S+) "([^"]*)" always;/gm))headers[match[1]]=match[2];
assert.equal(Object.keys(headers).length,5);
let child,browser,proxy,parent,passed=0;const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const free=p=>new Promise((resolve,reject)=>{const s=net.createServer();s.once('error',reject);s.listen(p,'127.0.0.1',()=>s.close(resolve));});
const check=label=>{passed++;console.log(label+' PASS');};
(async()=>{try{
 for(const p of [nextPort,proxyPort,parentPort])await free(p);
 child=spawn(process.execPath,['node_modules/next/dist/bin/next','start','-H','127.0.0.1','-p',String(nextPort)],{cwd:web,windowsHide:true,stdio:'ignore'});
 let ready=false;for(let i=0;i<100;i++){try{if((await fetch(`http://127.0.0.1:${nextPort}/login`)).ok){ready=true;break;}}catch{}assert.equal(child.exitCode,null);await sleep(200);}assert(ready);
 proxy=http.createServer((req,res)=>{const upstream=http.request({host:'127.0.0.1',port:nextPort,path:req.url,method:req.method,headers:req.headers},r=>{
   const clean={...r.headers};for(const key of ['x-powered-by',...Object.keys(headers).map(k=>k.toLowerCase())])delete clean[key];
   res.writeHead(r.statusCode,{...clean,...headers});r.pipe(res);
 });upstream.on('error',()=>{res.writeHead(502);res.end();});req.pipe(upstream);});
 await new Promise(r=>proxy.listen(proxyPort,'127.0.0.1',r));
 parent=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html');res.end(`<html><body><iframe src="${base}/operations" title="blocked management"></iframe></body></html>`);});
 await new Promise(r=>parent.listen(parentPort,'127.0.0.1',r));
 browser=await chromium.launch({channel:'msedge',headless:true});
 for(const width of [1280,375]){
  const context=await browser.newContext({viewport:{width,height:1000},acceptDownloads:true}),page=await context.newPage();
  let scoped=0,candidates=0,saved=0,unscoped=0;
  await page.route('**/api/**',async route=>{
   const req=route.request(),p=new URL(req.url()).pathname;
   const send=data=>route.fulfill({status:200,contentType:'application/json',headers:{'Cache-Control':'no-store'},body:JSON.stringify({ok:true,data})});
   if(p==='/api/auth/me')return send({user:{id:'synthetic-student',email:'synthetic@example.test'}});
   if(p==='/api/account/summary')return send({email:'synthetic@example.test',is_operator:false,memberships:[{organization_id:'synthetic-org',display_name:'合成確認教室',role:'student'}]});
   if(p==='/api/b2b/organizations/synthetic-org/me')return send({role:'student',organization_id:'synthetic-org',branding:{display_name:'合成確認教室'}});
   if(p==='/api/history/candidates'){assert.equal(req.postDataJSON().organization_id,'synthetic-org');candidates++;return send([]);}
   if(p==='/api/fortune'){unscoped++;return route.fulfill({status:404,body:'{"ok":false}'});}
   if(p==='/api/b2b/organizations/synthetic-org/fortune'){
    assert(req.headers()['idempotency-key']);scoped++;return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({...fixture.result,excel_export_token:'synthetic-export-reference'})});
   }
   if(p==='/api/history'&&req.method()==='POST'){
    const payload=req.postDataJSON();assert.equal(payload.organization_id,'synthetic-org');saved++;
    return send({id:'synthetic-reading',saved_at:'2026-10-28T00:00:00+00:00',updated_at:'2026-10-28T00:00:00+00:00',memo:'',input_snapshot:payload.input_snapshot,result_snapshot:payload.result_snapshot});
   }
   if(p==='/api/export-capabilities')return send({pdf_available:false});
   if(p==='/api/export/excel')return route.fulfill({status:200,headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','Content-Disposition':'attachment; filename="synthetic.xlsx"','Cache-Control':'no-store'},body:xlsx});
   return send([]);
  });
  const response=await page.goto(base+'/b2b/synthetic-org');assert.equal(response.headers()['content-security-policy'],headers['Content-Security-Policy']);
  await page.getByLabel('姓',{exact:true}).fill('合成確認');await page.getByLabel('名',{exact:true}).fill('太郎');
  await page.getByLabel('生年月日',{exact:true}).fill('1988-08-12');await page.getByLabel('出生時刻',{exact:true}).fill('09:00');
  await page.getByLabel('鑑定日',{exact:true}).fill('2026-10-05');await page.getByLabel('出生地').selectOption('東京都');await page.getByLabel('性別').selectOption('男性');
  await page.getByRole('button',{name:'鑑定結果を表示する',exact:true}).click();
  await page.waitForURL('**/result');await page.locator('.gogyoFigure').first().waitFor();
  assert.equal(unscoped,0);assert(scoped>0);check(width+' scoped calculation with CSP');
  assert(candidates>0);check(width+' candidate search carries selected class');
  await page.getByRole('button',{name:'鑑定結果を保存',exact:true}).click();await page.getByRole('status').filter({hasText:'保存済み'}).waitFor();assert.equal(saved,1);check(width+' scoped history save');
  await page.getByRole('button',{name:'鑑定書を出力',exact:true}).click();const pending=page.waitForEvent('download');
  await page.getByRole('button',{name:'Excelで出力',exact:true}).click();const download=await pending;
  const target=path.join(output,`download-${width}.xlsx`);await download.saveAs(target);assert.deepEqual(fs.readFileSync(target),xlsx);check(width+' Excel download remains functional');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));check(width+' viewport no horizontal overflow');
  await page.screenshot({path:path.join(output,`scope-${width}.png`),fullPage:true});await context.close();
 }
 const page=await browser.newPage(),blocked=[];page.on('console',m=>{if(/frame-ancestors|refused to (frame|display)/i.test(m.text()))blocked.push(m.text());});
 await page.goto(`http://127.0.0.1:${parentPort}/`);await page.waitForTimeout(500);
 assert(blocked.length>0,'Browser must report blocked embedding');check('browser refuses cross-origin iframe');
 await page.screenshot({path:path.join(output,'iframe-blocked.png')});
 fs.writeFileSync(path.join(output,'summary.json'),JSON.stringify({passed,production:false,synthetic_api:true,header_proxy:true,actual_nginx_test_is_separate:true}));
 console.log(JSON.stringify({passed,production:false,synthetic_api:true}));
}catch(e){console.error(e.stack);process.exitCode=1;}finally{
 if(browser)await browser.close();if(proxy)await new Promise(r=>proxy.close(r));if(parent)await new Promise(r=>parent.close(r));
 if(child){child.kill();await Promise.race([new Promise(r=>child.once('exit',r)),sleep(3000)]);}
}})();
