// Browser check for the run page (Playwright, Edge). CI does not run this file.
//
//   1. Start the page:  python -m teamsim serve
//   2. PW_PATH=<path to the playwright package> node tests/browser/run_page.mjs <page url> <screenshot dir>
//
// PW_PATH points at an installed `playwright` module folder (it is not a repo dependency).
// Exits 1 when any assertion fails.
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import path from "node:path";

const pwPath = process.env.PW_PATH;
const base = process.argv[2];
const outDir = process.argv[3];
if (!pwPath || !base || !outDir) {
  console.error("usage: PW_PATH=<playwright dir> node run_page.mjs <url> <screenshot dir>");
  process.exit(2);
}
mkdirSync(outDir, { recursive: true });
const { chromium } = createRequire(import.meta.url)(pwPath);

let failures = 0;
function check(ok, label) {
  console.log((ok ? "ok   " : "FAIL ") + label);
  if (!ok) failures += 1;
}

async function smallControls(page) {
  return page.evaluate(() => {
    const bad = [];
    for (const node of document.querySelectorAll("button, select, summary")) {
      const r = node.getBoundingClientRect(), s = getComputedStyle(node);
      if (s.display === "none" || s.visibility === "hidden" || r.width === 0 || r.height === 0) continue;
      if (r.height < 39.5) bad.push((node.id || node.textContent.trim().slice(0, 20) || node.tagName) + "=" + Math.round(r.height));
    }
    return bad;
  });
}

async function inFirstViewport(page, text) {
  return page.evaluate((t) => {
    for (const node of document.querySelectorAll(".strip .count")) {
      if (node.textContent.trim() !== t) continue;
      const r = node.getBoundingClientRect();
      return r.top >= 0 && r.bottom <= window.innerHeight;
    }
    return false;
  }, text);
}

const scrollWidth = (page) => page.evaluate(() => document.documentElement.scrollWidth);

const browser = await chromium.launch({ channel: "msedge" });
for (const [name, width, height] of [["desktop", 1440, 900], ["phone", 390, 844]]) {
  console.log("--- " + name + " " + width + "x" + height);
  const context = await browser.newContext({ viewport: { width, height }, colorScheme: "light" });
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: new URL(base).origin }).catch(() => {});
  const page = await context.newPage();
  const problems = [];
  page.on("console", (m) => { if (m.type() === "error") problems.push("console: " + m.text()); });
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message));
  page.on("response", (r) => { if (r.status() >= 400) problems.push(r.status() + " " + r.url()); });

  await page.goto(base + "?pack=team-ten&subject=naive_bot");
  await page.waitForSelector("#strip .strip-empty");
  check((await page.locator("#strip").innerText()).includes("Run a bot to score the checks."), "empty state before a run");
  await page.screenshot({ path: path.join(outDir, name + "-1-empty.png") });

  await page.click("#run");
  await page.waitForSelector(".strip .count");
  check((await page.locator(".strip .count").first().innerText()) === "8 failed", "8 failed shown first");
  check(await inFirstViewport(page, "8 failed"), "8 failed in the first viewport");
  check(await inFirstViewport(page, "6 passed"), "6 passed in the first viewport");
  const firstVerdict = await page.locator(".result-row").first().locator(".verdict").getAttribute("class");
  check(firstVerdict.includes("fail"), "first list row is a failed check");
  check((await page.locator(".result-row[aria-pressed=true]").count()) === 1, "one row selected");

  const body = await page.evaluate(() => document.body.innerText);
  check(!body.includes(".."), "no '..' in body text");
  check(!/\b1 (users|days)\b/.test(body), "no '1 users' or '1 days'");
  const words = body.split(/\s+/).filter(Boolean).length;
  check(words < 600, "visible words on the Checks tab " + words + " < 600");
  check((await scrollWidth(page)) === width, "scrollWidth equals " + width);
  const small = await smallControls(page);
  check(small.length === 0, "controls >= 40px tall" + (small.length ? " (" + small.join(", ") + ")" : ""));
  await page.screenshot({ path: path.join(outDir, name + "-2-checks.png") });

  await page.click('.result-row:has(.key:text-is("venue-room"))');
  const evidence = await page.locator("#evidence").innerText();
  check(evidence.includes("room-2210 → room-3045 → room-1180"), "venue-room shows the full chain");
  const evidenceAfterRow = await page.evaluate(() => {
    const prev = document.querySelector("#evidence").previousElementSibling;
    return !!prev && prev.matches(".result-row[aria-pressed=true]");
  });
  check(evidenceAfterRow === (width < 760), width < 760 ? "evidence opens under the tapped row" : "evidence stays in the right column");
  check((await page.locator("#timeline .tag", { hasText: /^bot$/ }).count()) === 0, "bot rows do not repeat 'bot' as a tag");
  await page.screenshot({ path: path.join(outDir, name + "-3-venue-room.png"), fullPage: true });

  await page.click("text=Show in timeline");
  await page.waitForSelector(".event.hit");
  check((await page.locator(".event.hit").count()) >= 2, ">= 2 highlighted timeline rows");
  check((await page.evaluate(() => location.hash)) === "#timeline", "timeline tab in the URL hash");
  await page.waitForTimeout(300);
  const hitBox = await page.locator(".event.hit").first().boundingBox();
  check(hitBox !== null && hitBox.y >= 0 && hitBox.y + hitBox.height <= height, "first highlight scrolled into view");
  check(await page.evaluate(() => { const t = document.querySelector("#timeline"); return t.scrollHeight <= t.clientHeight + 1; }), "timeline has no inner scroll");
  await page.screenshot({ path: path.join(outDir, name + "-4-timeline.png") });

  await page.click("#tab-controls");
  await page.waitForFunction(() => document.body.innerText.includes("Every control matches the ledger."), null, { timeout: 60000 });
  check(true, "Controls tab shows 'Every control matches the ledger.'");
  check((await scrollWidth(page)) === width, "controls tab scrollWidth equals " + width);
  await page.screenshot({ path: path.join(outDir, name + "-5-controls.png") });
  await page.reload();
  await page.waitForSelector("#strip .strip-empty");
  check((await page.locator("#tab-controls").getAttribute("aria-selected")) === "true", "reload keeps the selected tab");
  await page.waitForFunction(() => document.body.innerText.includes("Every control matches the ledger."), null, { timeout: 60000 });

  await page.click("#tab-users");
  check((await scrollWidth(page)) === width, "users tab scrollWidth equals " + width);
  await page.screenshot({ path: path.join(outDir, name + "-6-users.png") });

  await page.click("#tab-checks");
  await page.waitForSelector("#run:not([disabled])", { timeout: 60000 });
  await page.selectOption("#subject", "careful_bot");
  await page.click("#run");
  await page.waitForFunction(() => document.querySelector(".strip .count") && document.querySelector("#run").textContent === "Run");
  check((await page.locator(".strip .count").first().innerText()) === "0 failed", "careful_bot: 0 failed");
  await page.screenshot({ path: path.join(outDir, name + "-7-careful.png") });
  await page.click(".strip .text-button");
  await page.waitForFunction(() => document.querySelector(".strip .text-button")?.textContent === "Copied", null, { timeout: 3000 }).then(
    () => check(true, "Copy button reads Copied"), () => check(false, "Copy button reads Copied"));
  await page.selectOption("#subject", "naive_bot");
  for (let i = 0; i < 2; i++) {
    await page.click("#run");
    await page.waitForFunction((n) => document.querySelector(".strip .count")?.textContent === "8 failed" && document.querySelector("#run").textContent === "Run", i);
  }
  check((await page.locator("#strip").innerText()).includes("same as last run"), "rerun of naive_bot reads 'same as last run'");

  check(problems.length === 0, "no console errors or failed requests" + (problems.length ? ": " + problems.join(" | ") : ""));
  await context.close();
}
await browser.close();
console.log(failures ? failures + " assertion(s) failed" : "all assertions passed");
process.exit(failures ? 1 : 0);
