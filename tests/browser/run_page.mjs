// Browser check for the run page (Playwright, Edge). CI does not run this file.
//
//   1. Start the page:  python -m teamsim serve
//   2. PW_PATH=<path to the playwright package> node tests/browser/run_page.mjs <page url> <screenshot dir>
//
// PW_PATH points at an installed `playwright` module folder (it is not a repo dependency).
// Runs at 1440x900 and 390x844, each in a light and a dark colour scheme, then once more with
// reduced motion. Exits 1 when any assertion fails.
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

const scrollWidth = (page) => page.evaluate(() => document.documentElement.scrollWidth);
const bodyText = (page) => page.evaluate(() => document.body.innerText);

// Nothing a person reads may be an internal identifier. Ids live only inside "Run details".
const ID_PATTERNS = [
  /\bc[.-][a-z]/, /\b(no_leak|no_echo|catch_up|harness|withhold|naive_bot|careful_bot|oracle|ledger|digest|planted)\b/,
  /defect:/, /direct:/, /\bsubject\b/, /\bnull\b/, /record entries/i, /\b[a-z]+_[a-z]+\b/,
];
async function assertNoIds(page, label) {
  const text = await bodyText(page);
  const hits = ID_PATTERNS.map((re) => { const m = re.exec(text); return m ? m[0] + " (" + re + ")" : null; }).filter(Boolean);
  check(hits.length === 0, "no internal identifier on " + label + (hits.length ? ": " + hits.join(", ") : ""));
}

async function indicatorMatches(page, tabId) {
  return page.evaluate((id) => {
    const tab = document.getElementById(id).getBoundingClientRect();
    const ind = document.getElementById("tab-ind").getBoundingClientRect();
    return { dl: Math.abs(tab.left - ind.left), dw: Math.abs(tab.width - ind.width) };
  }, tabId);
}

const idle = (page) => page.waitForFunction(() => document.querySelector("#run-label").textContent === "Run test" && !document.querySelector("#run").disabled, null, { timeout: 60000 });

async function runMode(browser, name, width, height, scheme) {
  const tag = name + "-" + scheme;
  console.log("--- " + tag + " " + width + "x" + height);
  const context = await browser.newContext({ viewport: { width, height }, colorScheme: scheme });
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: new URL(base).origin }).catch(() => {});
  const page = await context.newPage();
  const problems = [];
  page.on("console", (m) => { if (m.type() === "error") problems.push("console: " + m.text()); });
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message));
  page.on("response", (r) => { if (r.status() >= 400) problems.push(r.status() + " " + r.url()); });
  const scored = [];
  page.on("request", (r) => { if (/\/api\/(run|validate)$/.test(new URL(r.url()).pathname)) scored.push(r.url()); });
  const shot = (label) => page.screenshot({ path: path.join(outDir, tag + "-" + label + ".png") });

  // Nothing is scored until a button is pressed, whatever the URL asks for.
  await page.goto(base + "?pack=team-ten&subject=naive_bot&run=1&validate=1#controls");
  await page.waitForSelector("#strip .steps");
  await page.waitForTimeout(500);
  check(scored.length === 0, "no run or validation on load, even with run=1, validate=1 and #controls");
  check(await page.locator("#run-controls").isVisible(), "Verify tests tab offers a button instead of running");
  check(!(await bodyText(page)).includes("Every test behaves as expected"), "no verification result before the button is pressed");
  await shot("5a-verify-before");

  await page.goto(base + "?pack=team-ten&subject=naive_bot#checks");
  await page.waitForSelector("#strip .steps");
  const empty = await page.locator("#strip").innerText();
  check(empty.includes("Choose a scenario") && empty.includes("Team workspace") && empty.includes("Naive bot") && empty.includes("Run test"), "empty state shows three steps with the current choices");
  check(/14 tests · \d+ questions to the bot · 10 people · 21 days/.test(empty), "empty state counts tests, questions, people and days");
  check((await page.locator("#about-line").innerText()).startsWith("A 10-person team chat over three weeks"), "description line names the scenario");
  check((await page.locator("#about-line").innerText()).includes("Remembers everything and answers by matching words"), "description line names the bot");
  check((await page.locator("#pack option:checked").innerText()) === "Team workspace · 10 people · 21 days", "scenario option reads name, people, days");
  check((await page.locator("#tab-checks").innerText()) === "Results 14", "results tab shows the count");
  await assertNoIds(page, "the empty Results tab");
  await shot("1-empty");

  // Run: the button changes state without changing width.
  const idleWidth = await page.evaluate(() => document.querySelector("#run").getBoundingClientRect().width);
  await page.click("#run");
  const runningState = await page.evaluate(() => {
    const b = document.querySelector("#run");
    return { text: b.textContent, spin: getComputedStyle(b.querySelector(".spin")).display, width: b.getBoundingClientRect().width,
      selects: document.querySelector("#pack").disabled && document.querySelector("#subject").disabled };
  });
  check(runningState.text === "Running…" && runningState.spin !== "none" && runningState.selects, "button shows Running… with a spinner and the selects are disabled");
  check(Math.abs(runningState.width - idleWidth) < 1.5, "button width does not change while running (" + Math.round(idleWidth) + " -> " + Math.round(runningState.width) + ")");
  await page.waitForSelector(".headline");
  await page.waitForFunction(() => document.querySelector(".headline")?.innerText === "8 of 14 tests failed", null, { timeout: 5000 }).then(
    () => check(true, "headline ends on exactly '8 of 14 tests failed' after the count-up"), () => check(false, "headline ends on '8 of 14 tests failed'"));
  check((await page.locator("#live").innerText()) === "8 of 14 tests failed", "live region announces the headline");
  const segs = await page.locator(".bar .seg").evaluateAll((n) => n.map((x) => x.title));
  check(segs.join("|") === "6 passed|8 failed", "score bar segments are titled '6 passed' and '8 failed'");
  check((await page.locator("#strip").innerText()).includes("Naive bot · Team workspace · 10 people · 21 days"), "sub line names bot, scenario, people and days");
  const firstChip = await page.locator(".result-row").first().locator(".chip").getAttribute("class");
  check(firstChip.includes("fail"), "first list row is a failed test");
  check((await page.locator(".group-label").allInnerTexts()).join("|") === "Failed 8|Passed 6", "groups read 'Failed 8' and 'Passed 6'");
  check((await page.locator(".result-row[aria-pressed=true]").count()) === 1, "one row selected");
  const vh = await page.evaluate(() => window.innerHeight);
  const headBox = await page.locator(".headline").boundingBox();
  check(headBox.y + headBox.height <= vh, "headline in the first viewport");

  const body = await bodyText(page);
  check(!body.includes(".."), "no '..' in body text");
  check(!/\b1 (people|persons|days|tests)\b/.test(body), "no '1 people', '1 days' or '1 tests'");
  const words = body.split(/\s+/).filter(Boolean).length;
  check(words < 650, "visible words on the Results tab " + words + " < 650");
  check((await scrollWidth(page)) === width, "scrollWidth equals " + width);
  const small = await smallControls(page);
  check(small.length === 0, "controls >= 40px tall" + (small.length ? " (" + small.join(", ") + ")" : ""));
  await assertNoIds(page, "the Results tab");
  await page.waitForTimeout(700);
  await shot("2-results");

  // Detail of the stale answer.
  await page.click('.result-row:has(.key:text-is("Venue room"))');
  await page.waitForTimeout(450);
  const evidence = await page.locator("#evidence").innerText();
  check(evidence.includes("room-2210") && evidence.includes("room-3045") && evidence.includes("room-1180"), "venue room shows the whole chain");
  check(await page.locator("#evidence .chain s").count() === 2 && (await page.locator("#evidence .chain strong").innerText()) === "room-1180", "older values struck through, newest in bold");
  const why = await page.locator("#evidence .why").innerText();
  check(why.includes("Why it failed") && why.includes("room-2210") && why.includes("room-1180"), "why line names the old and the current room: " + why.replace(/\n/g, " "));
  check(evidence.includes("Expected") && evidence.includes("Bot said") && evidence.includes("Show in conversation"), "detail has Expected, Bot said and Show in conversation");
  check(evidence.includes("Old answer") || width < 760, "chip says 'Old answer'");
  const evidenceAfterRow = await page.evaluate(() => {
    const prev = document.querySelector("#evidence").previousElementSibling;
    return !!prev && prev.matches(".result-row[aria-pressed=true]");
  });
  check(evidenceAfterRow === (width < 760), width < 760 ? "detail opens under the tapped row" : "detail stays in the right column");
  check((await page.locator("#timeline .tag", { hasText: /^bot$/i }).count()) === 0, "bot rows do not repeat 'bot' as a tag");
  await assertNoIds(page, "the venue room detail");
  await shot("3-venue-room");

  // Withhold and no-leak wording.
  await page.click('.result-row:has(.key:text-is("Offsite budget")):has(small:text-matches("Doesn.t tell"))');
  await page.waitForTimeout(450);
  const wh = await page.locator("#evidence").innerText();
  check(/isn't allowed to know this, and the bot told them/.test(wh) && wh.includes("Nothing about the offsite budget"), "withhold detail explains the leak and expects nothing");
  check(await page.locator(".result-row small", { hasText: "Keeps it where only leads can read" }).count() > 0, "no-leak test line names the audience");

  // Keyboard: arrows move the selection.
  const beforeKey = await page.locator(".result-row[aria-pressed=true]").getAttribute("data-check");
  await page.locator(".result-row[aria-pressed=true]").focus();
  await page.keyboard.press("ArrowDown");
  const afterDown = await page.locator(".result-row[aria-pressed=true]").getAttribute("data-check");
  await page.keyboard.press("ArrowUp");
  const afterUp = await page.locator(".result-row[aria-pressed=true]").getAttribute("data-check");
  check(afterDown !== beforeKey && afterUp === beforeKey, "Up and Down move the selected result");
  await page.keyboard.press("End");
  const lastRow = await page.evaluate(() => { const r = [...document.querySelectorAll(".result-row")]; return r[r.length - 1].getAttribute("aria-pressed"); });
  check(lastRow === "true", "End selects the last result");
  await page.keyboard.press("Home");
  check((await page.evaluate(() => document.querySelector(".result-row").getAttribute("aria-pressed"))) === "true", "Home selects the first result");

  // Show in conversation.
  await page.click('.result-row:has(.key:text-is("Venue room"))');
  await page.waitForTimeout(450);
  await page.click("text=Show in conversation");
  await page.waitForSelector(".event.hit");
  check((await page.locator(".event.hit").count()) >= 2, ">= 2 highlighted conversation rows");
  check((await page.evaluate(() => location.hash)) === "#timeline", "conversation tab in the URL hash");
  await page.waitForFunction((h) => { const r = document.querySelector(".event.hit").getBoundingClientRect(); return r.top >= 0 && r.bottom <= h; }, height, { timeout: 4000 }).then(
    () => check(true, "first highlight scrolled into view"), () => check(false, "first highlight scrolled into view"));
  check(await page.evaluate(() => { const t = document.querySelector("#timeline"); return t.scrollHeight <= t.clientHeight + 1; }), "conversation has no inner scroll");
  await page.waitForTimeout(350);
  const ind = await indicatorMatches(page, "tab-timeline");
  check(ind.dl <= 2 && ind.dw <= 2, "tab indicator sits under Conversation (left off by " + ind.dl.toFixed(1) + "px, width off by " + ind.dw.toFixed(1) + "px)");
  const ct = await page.locator("#count").innerText();
  check(/^\d+ of \d+ messages$/.test(ct), "count reads '{shown} of {total} messages': " + ct);
  const tl = await page.locator("#timeline").innerText();
  check(tl.includes("Question for the bot"), "question rows carry the 'Question for the bot' tag");
  check(await page.locator("#timeline .event.bot").count() > 0 && (await page.locator("#timeline .event.bot strong").first().innerText()) === "Bot", "bot rows name the author 'Bot'");
  await assertNoIds(page, "the Conversation tab");
  await shot("4-conversation");

  // Verify tests.
  await page.click("#tab-controls");
  await page.waitForTimeout(350);
  const ind2 = await indicatorMatches(page, "tab-controls");
  check(ind2.dl <= 2 && ind2.dw <= 2, "tab indicator sits under Verify tests (left off by " + ind2.dl.toFixed(1) + "px)");
  check((await page.locator("#matrix-note").innerText()).startsWith("Runs 8 reference bots with known flaws."), "verify tab explains what it does");
  await page.click("#run-controls");
  const progress = await page.evaluate(() => ({ on: document.querySelector("#progress").classList.contains("on"), label: document.querySelector("#run-controls").textContent }));
  check(progress.on && progress.label === "Verifying…", "while verifying: progress bar on and button reads Verifying…");
  await page.waitForFunction(() => document.body.innerText.includes("Every test behaves as expected."), null, { timeout: 60000 });
  check(true, "Verify tests tab shows 'Every test behaves as expected.'");
  const heads = await page.locator("#matrix thead th").allInnerTexts();
  check(heads.join("|") === "Test|Silent|Perfect|Out of date|Gullible|Leaky|Echo|Forgetful|DMs only", "matrix columns use reference bot names: " + heads.join("|"));
  check((await page.locator("#matrix td.caught").count()) > 0 && (await page.locator("#matrix td.caught").first().getAttribute("title")).length > 0, "caught cells carry the reason as a title");
  check((await page.locator("#matrix tbody th").first().innerText()) === "Bot connection", "first matrix row is the bot connection");
  check((await page.locator("#matrix tbody th", { hasText: "Release day · latest answer" }).count()) === 1, "matrix rows read 'Release day · latest answer'");
  check((await scrollWidth(page)) === width, "verify tab scrollWidth equals " + width);
  await assertNoIds(page, "the Verify tests tab");
  await page.waitForTimeout(500);
  await shot("5-verify");
  await page.reload();
  await page.waitForSelector("#strip .steps");
  check((await page.locator("#tab-controls").getAttribute("aria-selected")) === "true", "reload keeps the selected tab");
  const before = scored.length;
  await page.waitForTimeout(500);
  check(scored.length === before && await page.locator("#run-controls").isVisible(), "reload on #controls does not run verification");

  await page.click("#tab-users");
  check((await scrollWidth(page)) === width, "people tab scrollWidth equals " + width);
  const ptext = await page.locator("#users").innerText();
  check(ptext.includes("Typical reply") && ptext.includes("Splits messages") && ptext.includes("Asks the bot") && ptext.includes("Lead 1") && /\b4 min\b/.test(ptext) && ptext.includes("9:00–18:00"), "people table has plain headings and values");
  await assertNoIds(page, "the People tab");
  await page.waitForTimeout(350);
  await shot("6-people");

  // Careful bot, run details, copy.
  await page.click("#tab-checks");
  await page.selectOption("#subject", "careful_bot");
  await page.click("#run");
  await idle(page);
  await page.waitForFunction(() => document.querySelector(".headline")?.innerText === "All 14 tests passed", null, { timeout: 5000 }).then(
    () => check(true, "careful bot: 'All 14 tests passed'"), () => check(false, "careful bot: 'All 14 tests passed'"));
  check((await page.locator(".bar .seg").count()) === 1, "careful bot: one score bar segment");
  await page.waitForTimeout(700);
  await shot("7-careful");
  check((await page.locator("#run-details").isVisible()), "Run details disclosure appears after a run");
  await page.click("#run-details summary");
  const details = await page.locator("#run-details").innerText();
  check(details.includes("Run ID") && details.includes("The same scenario and bot always produce this ID.") && details.includes("Test id") && details.includes("Record entries") && details.includes("c.harness"), "Run details holds the ids");
  await page.click("#run-details .text-button");
  await page.waitForFunction(() => document.querySelector("#run-details .text-button")?.textContent.includes("Copied"), null, { timeout: 3000 }).then(
    () => check(true, "Copy button reads Copied"), () => check(false, "Copy button reads Copied"));
  await shot("7b-details");
  await page.click("#run-details summary");
  await page.selectOption("#subject", "naive_bot");
  for (let i = 0; i < 2; i++) {
    await page.click("#run");
    await page.waitForFunction(() => document.querySelector(".headline")?.innerText === "8 of 14 tests failed" && document.querySelector("#run-label").textContent === "Run test");
  }
  check((await page.locator("#strip").innerText()).includes("Same result as last run"), "rerun of the naive bot reads 'Same result as last run'");

  // The minimal scenario's conversation before a run.
  await page.goto(base + "?pack=minimal#timeline");
  await page.waitForSelector("#timeline .event");
  await page.click('#seg button[data-filter="all"]');
  const texts = await page.locator("#timeline .event p").allInnerTexts();
  check(texts.length > 0 && texts.every((t) => t.trim().length > 0), "every conversation row has text (away, back, reacted, deleted included)");
  check(texts.some((t) => t === "Reacted to Ana's message") && texts.some((t) => t === "Away"), "textless events read 'Reacted to Ana's message' and 'Away'");
  const tags = await page.locator("#timeline .tag").allInnerTexts();
  check(tags.some((t) => t.startsWith("Unverified claim: date = Monday 13 April")), "the unauthorised claim reads 'Unverified claim'");
  check(tags.some((t) => t === "Secret: access code"), "the secret is labelled 'Secret: access code'");
  check(tags.some((t) => t === "Fact: budget = 12 units · private to leads"), "a private fact names its audience");
  check(tags.some((t) => t === "Update: date → Thursday 16 April"), "a changed fact reads 'Update: date → …'");
  check(tags.includes("Edited"), "edits are tagged 'Edited'");
  const opts = await page.locator("#place option").allInnerTexts();
  check(opts.includes("All channels") && opts.includes("#leads · Ana, Di") && opts.includes("DM with Bo"), "channel select: " + opts.join(" / "));
  check(await page.locator("#timeline .event-meta strong", { hasText: "Ana" }).count() > 0, "authors are named 'Ana', not ids");
  await assertNoIds(page, "the minimal Conversation tab");
  await page.click("#tab-checks");
  await assertNoIds(page, "the minimal Results tab");
  await page.click("#run");
  await page.waitForFunction(() => document.querySelector(".headline")?.innerText.includes("tests failed"), null, { timeout: 8000 });
  await page.waitForTimeout(500);
  await assertNoIds(page, "the minimal Results tab after a run");
  await shot("8-minimal");

  check(problems.length === 0, "no console errors or failed requests" + (problems.length ? ": " + problems.join(" | ") : ""));
  await context.close();
}

async function runReduced(browser) {
  console.log("--- reduced motion 1440x900");
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "light", reducedMotion: "reduce" });
  const page = await context.newPage();
  await page.goto(base + "?pack=team-ten&subject=naive_bot#checks");
  await page.waitForSelector("#strip .steps");
  await page.click("#run");
  await page.waitForFunction(() => document.querySelector(".headline")?.innerText === "8 of 14 tests failed", null, { timeout: 5000 });
  check(true, "reduced motion: the headline shows the final number at once");
  const d = await page.evaluate(() => ({
    row: getComputedStyle(document.querySelector(".result-row")).transitionDuration,
    ind: getComputedStyle(document.querySelector("#tab-ind")).transitionDuration,
    seg: getComputedStyle(document.querySelector(".bar .seg")).animationName,
    spin: getComputedStyle(document.querySelector("#run .spin")).animationName,
  }));
  check(d.row === "0s", "reduced motion: .result-row transition-duration is 0s (" + d.row + ")");
  check(d.ind === "0s", "reduced motion: tab indicator transition-duration is 0s (" + d.ind + ")");
  check(d.seg === "none" && d.spin === "none", "reduced motion: no keyframe animation on the score bar or spinner");
  await page.click("#tab-users");
  const m = await indicatorMatches(page, "tab-users");
  check(m.dl <= 2, "reduced motion: indicator lands under the active tab at once");
  await context.close();
}

const browser = await chromium.launch({ channel: "msedge" });
for (const [name, width, height] of [["desktop", 1440, 900], ["phone", 390, 844]]) {
  for (const scheme of ["light", "dark"]) await runMode(browser, name, width, height, scheme);
}
await runReduced(browser);

// Motion check: the count-up starts at 0 and ends on the exact number; the tab indicator follows the tab.
{
  console.log("--- motion check");
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await page.goto(base + "?pack=team-ten&subject=naive_bot#checks");
  await page.waitForSelector("#strip .steps");
  const seen = [];
  await page.exposeFunction("sample", (v) => seen.push(v));
  await page.evaluate(() => {
    const node = document.querySelector("#strip");
    new MutationObserver(() => { const n = document.querySelector(".headline .fail, .headline .pass"); if (n) window.sample(n.textContent); }).observe(node, { subtree: true, childList: true, characterData: true });
  });
  await page.click("#run");
  await page.waitForFunction(() => document.querySelector(".headline")?.innerText === "8 of 14 tests failed");
  await page.waitForTimeout(500);
  const final = await page.locator(".headline .fail").innerText();
  check(final === "8" && seen.length > 1 && seen[0] === "0", "count-up starts at 0 and ends on exactly 8 (" + seen.join(",") + ")");
  await page.click("#tab-users");
  await page.waitForTimeout(60);
  const mid = await indicatorMatches(page, "tab-users");
  await page.waitForTimeout(400);
  const end = await indicatorMatches(page, "tab-users");
  check(end.dl <= 2 && end.dw <= 2, "tab indicator settles under People (mid-slide left offset " + mid.dl.toFixed(0) + "px, final " + end.dl.toFixed(1) + "px)");
  await context.close();
}
await browser.close();
console.log(failures ? failures + " assertion(s) failed" : "all assertions passed");
process.exit(failures ? 1 : 0);
