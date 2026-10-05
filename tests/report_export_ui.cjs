// Requires an explicitly configured disposable history DB; never use a real customer DB.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const base=process.env.FORTUNE_UI_URL||'http://127.0.0.1:3000';
(async()=>{
 const out=process.env.FORTUNE_EXPORT_UI_OUTPUT||fs.mkdtempSync(path.join(os.tmpdir(),'fortune-export-ui-'));
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const results=[],errors=[];
 try {
  for(const [device,width,height] of [['PC',1280,900],['mobile',375,812]]){
   const page=await browser.newPage({viewport:{width,height},acceptDownloads:true});
   page.on('pageerror',error=>errors.push(error.message));
   let calculations=0;page.on('request',request=>{if(request.url().endsWith('/api/fortune'))calculations++;});
   await page.goto(base,{waitUntil:'networkidle',timeout:60000});
   for(const [label,value] of [['姓','出力試験'+device],['名','太郎'],['生年月日','1988-08-12'],['出生時刻','09:00'],['鑑定日','2026-10-05']])await page.getByLabel(label,{exact:true}).fill(value);
   await page.getByLabel('出生地').selectOption('東京都');await page.getByLabel('性別').selectOption('男性');
   await page.getByRole('button',{name:'鑑定結果を表示する',exact:true}).click();
   await page.waitForURL('**/result');await page.locator('.gogyoFigure').first().waitFor();
   const checkWidth=async()=>assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=width,'horizontal overflow');
   const exportExcel=async(label)=>{
    const before=calculations;
    await page.getByRole('button',{name:'鑑定書を出力',exact:true}).click();
    const formats=page.getByRole('group',{name:'鑑定書の出力形式'});
    assert.equal(await formats.getByRole('button').count(),1);
    assert.equal(await page.getByRole('button',{name:/PDF/}).count(),0);
    await checkWidth();
    const pending=page.waitForEvent('download');
    await formats.getByRole('button',{name:'Excelで出力',exact:true}).click();
    const download=await pending;
    assert.equal(download.suggestedFilename(),'鑑定書_出力試験'+device+'太郎_2026-10-05.xlsx');
    const target=path.join(out,device+'_'+label+'.xlsx');await download.saveAs(target);
    assert.equal(fs.readFileSync(target).subarray(0,2).toString(),'PK');
    assert.equal(calculations,before,'export recalculated the reading');
    await checkWidth();results.push({device,flow:label,download:target,filename:download.suggestedFilename()});
   };
   await exportExcel('unsaved');
   await page.locator('#memo').evaluate(element=>element.open=true);
   await page.getByLabel('鑑定者用メモの自由記入欄').fill('EXCEL_NEVER_EXPORT_'+device);
   const pending=page.waitForResponse(response=>response.url().endsWith('/api/history')&&response.request().method()==='POST');
   await page.getByRole('button',{name:'鑑定結果を保存',exact:true}).click();
   const response=await pending;assert.equal(response.status(),200);
   const record=(await response.json()).data;
   await page.goto(base+'/history/'+record.id,{waitUntil:'networkidle'});
   await page.locator('.gogyoFigure').first().waitFor();
   await exportExcel('saved');
   await page.getByRole('button',{name:'鑑定書を出力',exact:true}).click();
   await page.screenshot({path:path.join(out,device+'_export.png'),fullPage:false});
   await page.route('**/api/export/excel',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({ok:false,error:'出力試験：利用できません。'})}));
   await page.getByRole('button',{name:'Excelで出力',exact:true}).click();
   await page.getByRole('alert').filter({hasText:'出力試験：利用できません。'}).waitFor();
   assert.ok(await page.getByRole('button',{name:'Excelで出力',exact:true}).isEnabled());
   await checkWidth();results.push({device,flow:'error recovery',passed:true});
   await page.close();
  }
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'ui_verification.json'),JSON.stringify({passed:results.length,results,errors},null,2));
  console.log(JSON.stringify({passed:results.length,results,errors}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
