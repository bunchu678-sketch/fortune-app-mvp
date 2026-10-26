// Local UI only: all auth/history replies mocked, no real database or mail service.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),net=require('node:net');
const web=path.resolve(__dirname,'../fortune-next-app'),base='http://127.0.0.1:3110';
const generated=path.join(web,'next-env.d.ts'),before=fs.readFileSync(generated);
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let server,browser,passed=0;
async function check(label,fn){await fn();passed++;console.log(label+' PASS');}
(async()=>{try{
 await new Promise((resolve,reject)=>{const s=net.createServer();s.once('error',reject);s.listen(3110,'127.0.0.1',()=>s.close(resolve));});
 server=spawn(process.execPath,['node_modules/next/dist/bin/next','dev','-H','127.0.0.1','-p','3110'],{cwd:web,windowsHide:true,stdio:['ignore','ignore','ignore']});
 let ready=false;for(let i=0;i<100;i++){if(server.exitCode!==null)throw new Error('Local server exited');try{if((await fetch(base+'/login')).ok){ready=true;break;}}catch{}await sleep(300);}assert(ready);
 browser=await chromium.launch({channel:'msedge',headless:true});
 for(const width of [1280,375]){
  const context=await browser.newContext({viewport:{width,height:900}}),page=await context.newPage();
  let authenticated=false,deleted=true,expired=false,restoreCalls=0;
  await page.route('**/api/auth/**',route=>route.fulfill({status:authenticated?200:401,contentType:'application/json',body:JSON.stringify(authenticated?{ok:true,data:{user:{id:'synthetic-owner',email:'owner@example.test'}}}:{ok:false})}));
  await page.route('**/api/history**',route=>{
   const url=new URL(route.request().url());
   if(url.pathname.endsWith('/restore')){restoreCalls++;if(!expired)deleted=false;return route.fulfill({status:expired?404:200,contentType:'application/json',body:JSON.stringify(expired?{ok:false,error:'復旧可能な鑑定履歴が見つかりません。'}:{ok:true,data:{restored:true}})});}
   return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,data:deleted?[{id:'synthetic-reading',name:'検査用利用者',birth_date:'1988-08-12',reading_date:'2026-10-01',deleted_at:'2026-10-02T00:00:00+00:00',restore_until:'2026-11-01T00:00:00+00:00'}]:[]})});
  });
  await page.goto(base+'/history/deleted');await check(width+' anonymous guard',()=>page.getByRole('link',{name:'ログインへ',exact:true}).waitFor());
  authenticated=true;await page.reload();
  await check(width+' owned deleted list',()=>page.getByRole('heading',{name:'検査用利用者',exact:true}).waitFor());
  await check(width+' recovery deadline',()=>page.getByText('復旧期限：',{exact:false}).waitFor());
  await check(width+' responsive layout',async()=>assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)));
  expired=true;await page.getByRole('button',{name:'復旧する',exact:true}).click();
  await check(width+' expired error retained',()=>page.getByRole('alert').filter({hasText:'復旧可能な鑑定履歴が見つかりません'}).waitFor());
  expired=false;await page.getByRole('button',{name:'復旧する',exact:true}).click();
  await check(width+' restored entry disappears',()=>page.getByText('復旧できる鑑定履歴はありません。',{exact:true}).waitFor());
  await check(width+' explicit POST only',async()=>assert.equal(restoreCalls,2));
  await check(width+' return history link',async()=>{await page.getByRole('link',{name:'鑑定履歴へ戻る',exact:true}).click();await page.waitForURL(base+'/history');});
  await context.close();
 }
 console.log('History recovery UI: '+passed+'/16 PASS');
}catch(error){console.error('History recovery UI failure: '+error.message);process.exitCode=1;}
finally{if(browser)await browser.close();if(server){server.kill();await Promise.race([new Promise(resolve=>server.once('exit',resolve)),sleep(3000)]);}if(!fs.readFileSync(generated).equals(before))fs.writeFileSync(generated,before);}})();
