// Optional local UI/API smoke test; requires existing Playwright + Edge, no installs.
// Start the local W frontend/API first. Not part of Python Tier A.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const assert = require("node:assert/strict");

(async () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "fortune-toggle-ui-"));
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  const errors = [];
  try {
    for (const [name, width, height] of [["desktop",1280,900],["mobile",390,844],["small-mobile",320,740]]) {
      const page = await browser.newPage({ viewport: { width, height } });
      page.on("pageerror", error => errors.push(error.message));
      await page.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });
      const toggle = page.getByLabel("鑑定年の影響を五行計算に反映する", { exact: true });
      assert.equal(await toggle.isChecked(), true);
      const layout = await toggle.evaluate(element => {
        const label = element.closest("label").getBoundingClientRect();
        const checkbox = element.getBoundingClientRect();
        return { documentWidth: document.documentElement.scrollWidth,
          labelX: label.x, labelWidth: label.width, labelHeight: label.height, checkboxWidth: checkbox.width };
      });
      assert.ok(layout.documentWidth <= width && layout.labelX >= 0 && layout.labelX + layout.labelWidth <= width);
      assert.ok(layout.checkboxWidth >= 12);
      const screenshot = path.join(directory, name + ".png");
      await page.screenshot({ path: screenshot, fullPage: true });
      await page.getByLabel("鑑定日", { exact: true }).fill("2020-09-08");
      // Existing wrapping labels include select option text in their accessible name.
      await page.getByLabel("出生地").selectOption("東京都");
      await page.getByLabel("性別").selectOption("男性");
      const outputs = [];
      for (const enabled of [true, false]) {
        await toggle.setChecked(enabled);
        const pending = page.waitForResponse(response => response.url().endsWith("/api/fortune") && response.request().method() === "POST");
        await page.getByRole("button", { name: "鑑定結果を表示する", exact: true }).click();
        const response = await pending;
        const request = response.request().postDataJSON();
        const result = await response.json();
        assert.equal(response.status(), 200);
        assert.equal(request.includeKanteiYearGogyoEffects, enabled);
        assert.equal(result.gogyo.include_kantei_year_gogyo_effects, enabled);
        // Same independent arithmetic as the formal service/API test.
        const expected = enabled ? { 木:0,火:0,土:3,金:1,水:8 } : { 木:0,火:0,土:4,金:4,水:1 };
        assert.deepEqual(result.gogyo.scores, expected);
        await page.locator(".gogyoGrid").waitFor();
        const shown = await page.locator(".gogyoRow").evaluateAll(rows => Object.fromEntries(rows.map(row => [
          row.querySelector(".gogyoLabel").textContent, Number(row.querySelector(".gogyoValue").textContent)
        ])));
        assert.deepEqual(shown, expected);
        const { gogyo, special_meishiki, ...other } = result;
        outputs.push({ enabled, scores: gogyo.scores, other });
      }
      assert.deepEqual(outputs[0].other, outputs[1].other);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth) <= width);
      // Existing visuallyHidden reset text is not exposed as an accessible name.
      await page.locator("form .ghostButton").click();
      assert.equal(await toggle.isChecked(), true);
      assert.equal(await page.locator(".gogyoGrid").count(), 0);
      console.log(JSON.stringify({ name, width, layout, screenshot,
        outputs: outputs.map(({ other, ...summary }) => summary), reset: "PASS" }));
      await page.close();
    }
    assert.deepEqual(errors, []);
    console.log("UI E2E PASS; pageerrors=0; screenshots=" + directory);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
