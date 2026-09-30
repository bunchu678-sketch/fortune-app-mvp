// Disposable DB only. Exercises empty names and distinct birth/reading boundary corrections.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||"playwright");
const assert=require("node:assert/strict");
const base=process.env.FORTUNE_UI_URL||"http://127.0.0.1:3000";
(async()=>{
 const browser=await chromium.launch({channel:"msedge",headless:true});
 try {
  const page=await browser.newPage({viewport:{width:375,height:812}});
  await page.goto(base,{waitUntil:"networkidle"});
  await page.getByLabel("生年月日",{exact:true}).fill("2020-02-04");
  await page.getByLabel("出生時刻",{exact:true}).fill("18:03");
  await page.getByLabel("性別").selectOption("男性");
  await page.getByLabel("鑑定日",{exact:true}).fill("2020-02-04");
  await page.getByRole("button",{name:"鑑定結果を表示する",exact:true}).click();
  await page.getByRole("group",{name:"節入り・万年暦確認",exact:true}).waitFor();
  await page.getByLabel("万年暦の確認結果で判定を修正する").check();
  await page.getByLabel("節入り前として鑑定",{exact:true}).check();
  await page.getByLabel("立春後として鑑定",{exact:true}).check();
  const final=page.waitForResponse(r=>r.url().endsWith("/api/fortune") && r.request().postDataJSON()?.boundarySelections?.reading?.choice==="after");
  await page.getByRole("button",{name:"選択して鑑定を続ける",exact:true}).click();
  const result=await (await final).json();assert.equal(result.ok,true);
  await page.waitForURL("**/result");await page.locator(".gogyoFigure").first().waitFor();
  assert.ok((await page.locator("#basic").textContent()).includes("無記名"));
  assert.equal(await page.locator(".gogyoVariant").nth(1).locator(".gogyoVariantContext").textContent(),"鑑定年：庚子");
  const created=page.waitForResponse(r=>r.url().endsWith("/api/history") && r.request().method()==="POST");
  await page.getByRole("button",{name:"鑑定結果を保存",exact:true}).click();
  const initial=(await (await created).json()).data;
  assert.deepEqual(initial.input_snapshot.manualChoices,{birth:"before",reading:"after"});
  await page.waitForFunction(()=>document.querySelector(".historyControls [role=status]")?.textContent.startsWith("保存済み"));
  await page.getByRole("button",{name:"この人を再鑑定",exact:true}).click();
  await page.getByRole("button",{name:"過去履歴を引き継がず新規鑑定",exact:true}).click();
  await page.waitForURL(base+"/");
  assert.ok((await page.locator("form").textContent()).includes("出生日時の手動補正：節入り前"));
  const today=new Intl.DateTimeFormat("sv-SE",{timeZone:"Asia/Tokyo"}).format(new Date());
  assert.equal(await page.getByLabel("鑑定日",{exact:true}).inputValue(),today);
  const automatic=page.waitForResponse(r=>r.url().endsWith("/api/fortune") && r.request().method()==="POST");
  await page.getByRole("button",{name:"鑑定結果を表示する",exact:true}).click();
  let rerun=await (await automatic).json();
  if (rerun.calendar?.auto_boundaries?.length) {
    const formal=page.waitForResponse(r=>r.url().endsWith("/api/fortune") && r.request().method()==="POST");
    await page.getByRole("button",{name:"アプリ判定で鑑定結果へ",exact:true}).click();
    rerun=await (await formal).json();
  }
  await page.waitForURL("**/result");
  assert.deepEqual(rerun.meishiki,result.meishiki);
  assert.equal(rerun.gogyo_variants.B.gogyo.kantei_year.tenkan+rerun.gogyo_variants.B.gogyo.kantei_year.chishi,"丙午");
  assert.equal((await page.locator("#basic").textContent()).includes("鑑定日の節入り判定"),false);
  const saved=page.waitForResponse(r=>r.url().endsWith("/api/history") && r.request().method()==="POST");
  await page.getByRole("button",{name:"鑑定結果を保存",exact:true}).click();
  const next=(await (await saved).json()).data;
  assert.deepEqual(next.input_snapshot.manualChoices,{birth:"before"});
  assert.equal(next.person_id,initial.person_id);assert.notEqual(next.group_id,initial.group_id);
  console.log("Boundary UI PASS: unnamed, birth override retained, reading override cleared, fresh year calculated.");
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
