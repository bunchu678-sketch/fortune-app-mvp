// Local frontend only; every auth/reset request is mocked. No API/DB/SMTP server is started.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),net=require('node:net');
const root=path.resolve(__dirname,'..'), web=path.join(root,'fortune-next-app');
const base='http://127.0.0.1:3109', token='t'.repeat(43);
const generated=path.join(web,'next-env.d.ts'), before=fs.readFileSync(generated);
let server,browser,passed=0;
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function check(label,fn){await fn();passed++;console.log(label+' PASS');}
(async()=>{
 try {
  await new Promise((resolve,reject)=>{const s=net.createServer();s.once('error',reject);s.listen(3109,'127.0.0.1',()=>s.close(resolve));});
  server=spawn(process.execPath,['node_modules/next/dist/bin/next','dev','-H','127.0.0.1','-p','3109'],{cwd:web,windowsHide:true,stdio:['ignore','ignore','ignore']});
  let ready=false;for(let i=0;i<100;i++){if(server.exitCode!==null)throw new Error('Local test server exited');try{if((await fetch(base+'/login')).ok){ready=true;break;}}catch{}await sleep(300);}
  assert(ready,'Local test server readiness');
  browser=await chromium.launch({channel:'msedge',headless:true});
  for(const width of [1280,375]){
   const context=await browser.newContext({viewport:{width,height:900}});const page=await context.newPage();
   let mode='accepted', completions=0;
   await page.route('**/api/auth/**',async route=>{
    const url=new URL(route.request().url());
    if(url.pathname==='/api/auth/password-reset/request')return route.fulfill({status:mode==='unavailable'?503:202,contentType:'application/json',body:JSON.stringify(mode==='unavailable'?{ok:false,error:'Unavailable'}:{ok:true,message:'Generic accepted'})});
    if(url.pathname==='/api/auth/password-reset/complete'){
     completions++;const payload=route.request().postDataJSON();assert.equal(payload.token,token);
     return route.fulfill({status:mode==='expired'?400:200,contentType:'application/json',body:JSON.stringify(mode==='expired'?{ok:false,error:'再設定リンクが無効または期限切れです。再度申請してください。'}:{ok:true})});
    }
    return route.fulfill({status:401,contentType:'application/json',body:'{"ok":false}'});
   });
   await page.goto(base+'/login');
   await check(width+' login link',async()=>{await page.getByRole('link',{name:'パスワードを忘れた方'}).click();await page.getByRole('heading',{name:'パスワード再設定',exact:true}).waitFor();});
   await page.getByLabel('メールアドレス',{exact:true}).fill('synthetic@example.test');await page.getByRole('button',{name:'再設定を申請'}).click();
   await check(width+' generic request response',()=>page.getByRole('status').filter({hasText:'登録されている場合'}).waitFor());
   mode='unavailable';await page.getByRole('button',{name:'再設定を申請'}).click();
   await check(width+' disabled transport UI',()=>page.getByRole('alert').filter({hasText:'現在、パスワード再設定を利用できません'}).waitFor());
   await page.goto(base+'/reset-password#token=bad');
   await check(width+' invalid link',()=>page.getByRole('alert').filter({hasText:'再設定リンクを確認できません'}).waitFor());
   await page.goto(base+'/reset-password#token='+token);
   await page.getByLabel('新しいパスワード',{exact:true}).waitFor();
   await check(width+' token captured once and stripped',async()=>{assert.equal(page.url(),base+'/reset-password');assert.equal(completions,0);});
   await page.getByLabel('新しいパスワード',{exact:true}).fill('synthetic-password-1234');await page.getByLabel('新しいパスワード（確認）',{exact:true}).fill('different-password-1234');await page.getByRole('button',{name:'パスワードを変更'}).click();
   await check(width+' mismatch no submit',async()=>{await page.getByRole('alert').filter({hasText:'一致しません'}).waitFor();assert.equal(completions,0);});
   await page.getByLabel('新しいパスワード（確認）',{exact:true}).fill('synthetic-password-1234');mode='expired';await page.getByRole('button',{name:'パスワードを変更'}).click();
   await check(width+' expired link message',()=>page.getByRole('alert').filter({hasText:'期限切れ'}).waitFor());
   await check(width+' responsive layout',async()=>assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)));
   mode='accepted';await page.getByRole('button',{name:'パスワードを変更'}).click();
   await check(width+' completion and login redirect',async()=>{await page.waitForURL(base+'/login?reset=done');await page.getByRole('status').filter({hasText:'パスワードを変更しました'}).waitFor();});
   await check(width+' secret absent from URL',async()=>assert(!page.url().includes(token)));
   await context.close();
  }
  console.log('Password reset UI: '+passed+'/20 PASS');
 }catch(error){console.error('Password reset UI failure: '+error.message);process.exitCode=1;}
 finally{if(browser)await browser.close();if(server){server.kill();await Promise.race([new Promise(resolve=>server.once('exit',resolve)),sleep(3000)]);}if(!fs.readFileSync(generated).equals(before))fs.writeFileSync(generated,before);}
})();
