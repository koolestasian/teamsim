// Browser check for the run page (Playwright, Edge). CI does not run this file.
//
//   1. Start the page:  python -m teamsim serve
//   2. PW_PATH=<path to the playwright package> node tests/browser/run_page.mjs <page url> <screenshot dir>
//
// PW_PATH points at an installed `playwright` module folder (it is not a repo dependency).
// Runs at 1440x900, 2560x1440 and 390x844, each in a light and a dark colour scheme, then the conversation
// workspace at 1440x900 and 390x844 for every scenario (the Lantern Shelf one only when packs/lantern-shelf
// exists), then once more with reduced motion. Exits 1 when any assertion fails. WS_ONLY=1 runs only the
// workspace checks.
import { createRequire } from "node:module";
import { mkdirSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const lanternPack = existsSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "packs", "lantern-shelf"));

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
  // "ana_k" is the display name the minimal scenario gives its first person.
  const text = (await bodyText(page)).replace(/\bana_k\b/g, "Ana");
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
  const shot = async (label) => { await page.evaluate(() => window.scrollTo(0, 0)); await page.waitForTimeout(120); await page.screenshot({ path: path.join(outDir, tag + "-" + label + ".png") }); };

  // Nothing is scored until a button is pressed, whatever the URL asks for.
  await page.goto(base + "?pack=team-ten&subject=naive_bot&run=1&validate=1#controls");
  await page.waitForSelector("#scenario-card .stat-num");
  await page.waitForTimeout(500);
  check(scored.length === 0, "no run or validation on load, even with run=1, validate=1 and #controls");
  check(await page.locator("#run-controls").isVisible(), "Verify tests tab offers a button instead of running");
  check(!(await bodyText(page)).includes("Every test catches its flaw and passes the Perfect bot"), "no verification result before the button is pressed");
  await shot("5a-verify-before");

  await page.goto(base + "?pack=team-ten&subject=naive_bot#checks");
  await page.waitForSelector("#scenario-card .stat-num");
  check((await page.locator("#strip").innerText()).trim() === "" && !(await page.locator("#strip").isVisible()), "no summary or placeholder before a run");
  const rootPx = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize));
  const bodyPx = await page.evaluate(() => parseFloat(getComputedStyle(document.body).fontSize));
  const wantRoot = width >= 2560 ? 20 : 16;
  check(Math.abs(rootPx - wantRoot) < 0.5 && Math.abs(bodyPx - wantRoot) < 0.5, "root and body font-size are " + wantRoot + "px (" + rootPx.toFixed(2) + ", " + bodyPx.toFixed(2) + ")");
  const minText = await page.evaluate((root) => {
    let least = 99;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const el = n.parentElement;
      if (!n.textContent.trim() || !el.getClientRects().length || getComputedStyle(el).visibility === "hidden") continue;
      least = Math.min(least, parseFloat(getComputedStyle(el).fontSize));
    }
    return least;
  });
  check(minText >= 13 - 0.01, "no visible text below 13px (smallest " + minText.toFixed(1) + "px)");
  const optTexts = await page.locator("#pack option").allInnerTexts();
  check(optTexts.length === (lanternPack ? 5 : 4) && ["Team workspace", "Demo day planning", "Social feed", "Personal assistant"].every((n) => optTexts.includes(n)) && (!lanternPack || optTexts.includes("Lantern Shelf")), "scenario options show only the name: " + optTexts.join("|"));
  const botTexts = await page.locator("#subject option").allInnerTexts();
  check(botTexts.slice(0, 2).join("|") === "Naive bot|Careful bot" && botTexts.every((t) => !/[·:(]/.test(t)), "bot options show only the name: " + botTexts.join("|"));
  const stats = await page.locator("#scenario-card .stat").evaluateAll((n) => n.map((x) => x.querySelector(".stat-num").textContent + " " + x.querySelector(".stat-label").textContent));
  check(stats.slice(0, 3).join("|") === "10 people|21 days|14 tests" && /^\d+ questions to the bot$/.test(stats[3]), "scenario card shows 10 people, 21 days, 14 tests: " + stats.join("|"));
  const chipTexts = await page.locator("#scenario-card .tagchip").allInnerTexts();
  check(["Changed plans", "Private info", "Secrets", "False claims", "Time away"].every((c) => chipTexts.includes(c)), "Team workspace chips: " + chipTexts.join(", "));
  check((await page.locator("#scenario-card .card-line").innerText()) === "A 10-person team chats for three weeks.", "scenario card has one short line");
  check((await page.locator("#bot-card").innerText()).includes("Remembers everything and answers by matching words.") && !(await page.locator("#bot-card .flaw").count()), "bot card names the Naive bot with its line and no flaw chip");
  const cardNum = await page.evaluate(() => parseFloat(getComputedStyle(document.querySelector(".stat-num")).fontSize) / parseFloat(getComputedStyle(document.documentElement).fontSize));
  check(Math.abs(cardNum - 1.75) < 0.01, "stat numbers are 1.75rem");
  const layout = await page.evaluate(() => {
    const a = document.querySelector(".setup").getBoundingClientRect(), b = document.querySelector("main").getBoundingClientRect();
    const run = document.querySelector("#run").getBoundingClientRect();
    return { sideBySide: b.left >= a.right - 1 && Math.abs(a.top - b.top) < 4, stacked: b.top >= a.bottom - 1, span: b.right - a.left, runW: run.width, setupW: a.width };
  });
  if (width >= 1100) check(layout.sideBySide, "setup panel and results sit side by side");
  else check(layout.stacked, "setup panel sits above the results");
  if (width >= 2560) check(layout.span > 1700, "page content is wider than 1700px (" + Math.round(layout.span) + ")");
  check(Math.abs(layout.runW - layout.setupW) < 2, "Run test fills the setup panel width");
  check(!(await bodyText(page)).includes("Results appear here after a run") && !/Choose a scenario|Choose a bot|questions to the bot ·/.test(await bodyText(page)), "removed commentary is gone");
  check((await page.locator("#tab-checks").getAttribute("aria-disabled")) === "true" && (await page.locator("#tab-timeline").getAttribute("aria-selected")) === "true", "Results tab is disabled and Conversation is open before a run");
  await page.click("#tab-checks", { force: true });
  check((await page.locator("#tab-timeline").getAttribute("aria-selected")) === "true", "clicking the disabled Results tab does nothing");
  await page.click(".about > summary");
  const about = await page.locator(".about").first().innerText();
  check(about.includes("Keep in mind") && !/reply_median_s|\bpack\b|surface/.test(about), "scenario limits are in plain language");
  await page.click(".about > summary");
  check((await page.locator("#tab-checks").innerText()) === "Results 14", "results tab shows the count");
  await assertNoIds(page, "the Conversation tab before a run");
  await shot("1-empty");

  // Switching scenario updates the card.
  await page.selectOption("#pack", "minimal");
  await page.waitForFunction(() => document.querySelector("#scenario-card .card-name")?.textContent === "Demo day planning");
  await page.waitForTimeout(500);
  const stats2 = await page.locator("#scenario-card .stat").evaluateAll((n) => n.map((x) => x.querySelector(".stat-num").textContent + " " + x.querySelector(".stat-label").textContent));
  check(stats2[0] === "4 people" && stats2[1] === "1 day", "scenario card updates to 4 people and 1 day: " + stats2.join("|"));
  await shot("1b-minimal-card");
  await page.selectOption("#subject", "defect:stale");
  check((await page.locator("#bot-card").innerText()).includes("Gives old answers.") && (await page.locator("#bot-card .flaw").innerText()) === "Known flaw", "reference bot card has the Known flaw chip and its line");
  await shot("1c-flaw-card");
  await page.selectOption("#subject", "naive_bot");
  await page.selectOption("#pack", "team-ten");
  await page.waitForFunction(() => document.querySelector("#scenario-card .card-name")?.textContent === "Team workspace");
  await page.waitForTimeout(500);

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
  check(!body.includes("..") && !/Results appear here|The same scenario and bot always|tests · \d+ questions/.test(body), "no '..' and none of the removed strings in body text");
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
  check(evidence.includes("Old answer") || width < 1280, "chip says 'Old answer'");
  const evidenceAfterRow = await page.evaluate(() => {
    const prev = document.querySelector("#evidence").previousElementSibling;
    return !!prev && prev.matches(".result-row[aria-pressed=true]");
  });
  check(evidenceAfterRow === (width < 1280), width < 1280 ? "detail opens under the tapped row" : "detail stays in the right column");
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
  await page.waitForSelector(".msg.hit");
  check((await page.locator(".msg.hit").count()) >= 2, ">= 2 highlighted conversation rows");
  check((await page.evaluate(() => location.hash)) === "#timeline", "conversation tab in the URL hash");
  await page.waitForFunction(() => {
    const r = document.querySelector(".msg.hit").getBoundingClientRect(), f = document.querySelector("#timeline").getBoundingClientRect();
    return r.top >= f.top - 1 && r.bottom <= f.bottom + 1 && r.top >= 0 && r.bottom <= window.innerHeight;
  }, null, { timeout: 4000 }).then(
    () => check(true, "first highlight scrolled into view"), () => check(false, "first highlight scrolled into view"));
  await page.waitForTimeout(350);
  const ind = await indicatorMatches(page, "tab-timeline");
  check(ind.dl <= 2 && ind.dw <= 2, "tab indicator sits under Conversation (left off by " + ind.dl.toFixed(1) + "px, width off by " + ind.dw.toFixed(1) + "px)");
  const ct = await page.locator("#count").innerText();
  check(/^\d+ messages$/.test(ct), "count reads '{n} messages' with every message shown: " + ct);
  check(await page.locator("#timeline .tag", { hasText: "Question for the bot" }).count() > 0, "question rows carry the 'Question for the bot' tag");
  check(await page.locator("#timeline .msg.bot").count() > 0 && (await page.locator("#timeline .msg.bot .name").first().textContent()) === "Naive bot" && (await page.locator("#timeline .msg.bot .bot-tag").first().textContent()) === "BOT", "bot rows name the bot and carry a BOT tag");
  // With "Only key messages" on, a highlighted message is still shown.
  await page.check("#key-only");
  await page.click("#tab-checks");
  await page.click('.result-row:has(.key:text-is("Venue room"))');
  await page.waitForTimeout(450);
  await page.click("text=Show in conversation");
  await page.waitForSelector(".msg.hit");
  check(/^\d+ of \d+ messages$/.test(await page.locator("#count").innerText()) && (await page.locator(".msg.hit").count()) >= 2, "Show in conversation works with Only key messages on");
  await page.uncheck("#key-only");
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
  await page.waitForFunction(() => document.body.innerText.includes("Every test catches its flaw and passes the Perfect bot."), null, { timeout: 60000 });
  check(true, "Verify tests tab shows 'Every test catches its flaw and passes the Perfect bot.'");
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
  await page.waitForSelector("#scenario-card .stat-num");
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
  check(details.includes("Run ID") && details.includes("Test id") && details.includes("Record entries") && details.includes("c.harness"), "Run details holds the ids");
  check((await page.locator("#run-details .mono").first().getAttribute("title")) === "The same scenario and bot always produce this ID." && !details.includes("always produce this ID"), "Run ID carries the explanation as a tooltip only");
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
  await page.waitForSelector("#timeline .msg");
  const texts = await page.locator("#timeline .mtext").allTextContents();
  check(texts.length > 0 && texts.every((t) => t.trim().length > 0), "every message row has text");
  check(await page.locator("#timeline .sys").filter({ hasText: "went away" }).count() === 1 && await page.locator("#timeline .reacts .react").count() === 1, "away shows as a system row and the reaction as a pill under its message");
  const tags = await page.locator("#timeline .tag").allTextContents();
  check(tags.some((t) => t.startsWith("Unverified claim: date = Monday 13 April")), "the unauthorised claim reads 'Unverified claim'");
  check(tags.some((t) => t === "Secret: access code"), "the secret is labelled 'Secret: access code'");
  check(tags.some((t) => t === "Fact: budget = 12 units · private to leads"), "a private fact names its audience");
  check(tags.some((t) => t === "Update: date → Thursday 16 April"), "a changed fact reads 'Update: date → …'");
  check(await page.locator("#timeline .msg.key.upd").count() > 0 && await page.locator("#timeline .msg.key.priv").count() > 0 && await page.locator("#timeline .msg.key.ask").count() > 0, "key messages carry update, private and question accents");
  const cueTime = await page.locator("#timeline .msg", { hasText: "Did I miss anything while I was away?" }).first().locator(".stamp").innerText();
  check(cueTime.trim() === "—", "an event timed by the run shows a dash before a run, not Day 1 00:00");
  check(await page.locator("#timeline .edited").count() === 1 && await page.locator("#timeline .gone-note").first().innerText() === "Deleted on Day 1", "an edited message shows (edited) and a deleted one says when");
  const chans = await page.locator("#ws-chlist .ch-name").allTextContents();
  check(chans.join("|") === "All channels|general|leads|Bo" || width < 760, "channel list: " + chans.join("|"));
  check(await page.locator("#timeline .name", { hasText: "ana_k" }).count() > 0, "authors use the display name 'ana_k'");
  await assertNoIds(page, "the minimal Conversation tab");
  check((await page.locator("#tab-checks").getAttribute("aria-disabled")) === "true", "minimal: Results tab is still disabled before a run");
  await page.click("#run");
  await page.waitForFunction(() => document.querySelector("#tab-checks").getAttribute("aria-selected") === "true", null, { timeout: 8000 });
  check(true, "the page switches to Results after the first run");
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
  await page.waitForSelector("#scenario-card .stat-num");
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

const NON_MESSAGE = new Set(["edit", "delete", "react"]);
async function packOf(page, name) {
  return page.evaluate(async (n) => (await fetch("/api/pack?name=" + n)).json(), name);
}
const expectedRows = (pack, surface) => pack.events.filter((e) => (!surface || e.surface === surface) && !NON_MESSAGE.has(e.kind)).length;
const rowCount = (page) => page.locator("#timeline .msg, #timeline .sys").count();
const counterWord = (pack) => (pack.events.some((e) => e.kind === "post") ? "messages" : "actions");

async function pickSurface(page, id, phone) {
  if (phone) {
    await page.click("#ws-chbtn");
    await page.waitForSelector("#ws-channels.open");
  }
  await page.click('#ws-chlist .ch[data-surface="' + id + '"]');
  await page.waitForTimeout(80);
}

// The conversation workspace for one scenario at one size.
async function runWorkspace(browser, name, width, height, scheme) {
  const phone = width < 760;
  const tag = "ws-" + name + "-" + width + "-" + scheme;
  console.log("--- workspace " + name + " " + width + "x" + height + " " + scheme);
  const context = await browser.newContext({ viewport: { width, height }, colorScheme: scheme });
  const page = await context.newPage();
  const problems = [];
  page.on("console", (m) => { if (m.type() === "error") problems.push("console: " + m.text()); });
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message));
  page.on("response", (r) => { if (r.status() >= 400) problems.push(r.status() + " " + r.url()); });
  const shot = async (label) => { await page.evaluate(() => document.querySelector("#ws").scrollIntoView({ block: "start" })); await page.waitForTimeout(150); await page.screenshot({ path: path.join(outDir, tag + "-" + label + ".png") }); };

  await page.goto(base + "?pack=" + name + "#timeline");
  await page.waitForSelector("#timeline .msg, #timeline .sys");
  const pack = await packOf(page, name);
  const word = counterWord(pack);
  const expected = expectedRows(pack, "");
  const rows = await rowCount(page);
  check(rows === expected, name + ": every event of All channels renders (" + rows + " of " + expected + ")");
  check((await page.locator("#count").innerText()) === expected + " " + word, name + ": counter reads '" + expected + " " + word + "': " + (await page.locator("#count").innerText()));
  check(!(await page.locator("#more").count()), name + ": no 'Show more' button");
  check(await page.evaluate(() => !document.querySelector(".grp") || getComputedStyle(document.querySelector(".grp")).contentVisibility === "auto"), name + ": message groups use content-visibility");
  await shot("1-all");

  // Only key messages.
  check(!(await page.locator("#key-only").isChecked()), name + ": Only key messages is off by default");
  await page.check("#key-only");
  const keyRows = await rowCount(page);
  const nonKey = await page.locator("#timeline .msg:not(.key):not(.hit), #timeline .sys").count();
  const keySys = await page.locator("#timeline .sys").count();
  check(keyRows <= expected && (keyRows < expected || pack.events.every((e) => e.probe || (e.discloses && e.discloses.length) || NON_MESSAGE.has(e.kind))), name + ": Only key messages shows fewer rows (" + keyRows + " of " + expected + ")");
  check(nonKey === keySys, name + ": with Only key messages every message is a key message");
  if (keyRows < expected) check(/^\d+ of \d+ /.test(await page.locator("#count").innerText()), name + ": counter reads '{shown} of {total}': " + (await page.locator("#count").innerText()));
  await page.reload();
  await page.waitForSelector("#timeline .msg, #timeline .sys");
  check(await page.locator("#key-only").isChecked() && (await rowCount(page)) === keyRows, name + ": the setting survives a reload");
  await shot("2-key");
  await page.uncheck("#key-only");
  check((await rowCount(page)) === expected, name + ": unchecking restores every row");

  // Channel and direct-message filters.
  const channel = pack.surfaces.find((s) => s.kind !== "direct" && expectedRows(pack, s.id) > 0);
  if (channel) {
    await pickSurface(page, channel.id, phone);
    check((await rowCount(page)) === expectedRows(pack, channel.id), name + ": # " + channel.id + " shows only its own rows (" + (await rowCount(page)) + ")");
    check((await page.locator("#ws-title").textContent()) === "#" + channel.id, name + ": header names the channel");
    check((await page.locator("#timeline .chan").count()) === 0, name + ": no channel chips inside a single channel");
  }
  const direct = pack.surfaces.find((s) => s.kind === "direct" && expectedRows(pack, s.id) > 1);
  if (direct) {
    await pickSurface(page, direct.id, phone);
    check((await rowCount(page)) === expectedRows(pack, direct.id), name + ": a direct message shows only its own rows (" + (await rowCount(page)) + ")");
  }
  const members = await (async () => {
    if (phone) { await page.click("#ws-membtn"); await page.waitForSelector("#ws-members.open"); }
    const n = await page.locator("#ws-memlist .mem").count();
    if (phone) { await page.keyboard.press("Escape"); await page.waitForSelector("#ws-members.open", { state: "detached", timeout: 1000 }).catch(() => {}); }
    return n;
  })();
  check(members >= 2, name + ": member list shows people and the bot (" + members + ")");
  check(phone || (await page.locator("#ws-members").isVisible()), name + ": member list is a column on wide screens");
  await pickSurface(page, "", phone);

  // Profile card.
  const opener = (await page.locator("#timeline .av-btn").count()) ? page.locator("#timeline .av-btn").first() : page.locator("#timeline .sys .name").first();
  const authorName = await page.locator("#timeline .name").first().innerText();
  const authorId = await page.locator("#timeline .name").first().getAttribute("data-actor");
  await opener.click();
  await page.waitForSelector("#profile:not([hidden])");
  check((await page.locator("#pc-title").innerText()) === authorName, name + ": the avatar opens the profile of " + authorName);
  if (name === "minimal") check(authorName === "ana_k" && (await page.locator("#profile").innerText()).includes("@ana"), "minimal: the profile shows the display name 'ana_k' and @ana");
  const card = await page.locator("#profile").innerText();
  check(/(Messages sent|Product actions)\s*\d+/.test(card) && card.includes("Synthetic user") && card.includes("Show only their messages"), name + ": the card shows activity and the filter button");
  const box = await page.locator("#profile").boundingBox();
  check(box.x >= -0.5 && box.y >= -0.5 && box.x + box.width <= width + 0.5 && box.y + box.height <= height + 0.5, name + ": the card stays inside the viewport");
  check(await page.evaluate(() => document.querySelector("#profile").contains(document.activeElement) || document.activeElement === document.querySelector("#profile")), name + ": focus moves into the card");
  check(!(await page.evaluate(() => /\b(undefined|NaN)\b|\bnull\b/.test(document.querySelector("#profile").textContent))), name + ": the card has no undefined, null or NaN");
  await shot("3-card");
  await page.keyboard.press("Escape");
  check(await page.locator("#profile").isHidden(), name + ": Esc closes the card");
  check(await page.evaluate(() => document.activeElement && document.activeElement.matches(".av-btn, .name")), name + ": focus returns to the avatar");
  await opener.click();
  await page.waitForSelector("#profile:not([hidden])");
  await page.mouse.click(4, 4);
  check(await page.locator("#profile").isHidden(), name + ": an outside click closes the card");
  // Names open the same card.
  await page.locator("#timeline .name").first().click();
  check((await page.locator("#profile:not([hidden]) #pc-title").innerText()) === authorName, name + ": a name opens the same card");
  await page.locator("#profile .pc-only").click();
  check(await page.locator("#profile").isHidden() && (await page.locator(".chip-person").innerText()).startsWith("From " + authorName), name + ": Show only their messages closes the card and adds a 'From " + authorName + "' chip");
  const owners = await page.locator("#timeline .msg, #timeline .sys").evaluateAll((n) => [...new Set(n.map((x) => x.dataset.who))]);
  check(owners.length === 1 && owners[0] === authorId, name + ": only " + authorId + " messages remain (" + owners.join(",") + ")");
  await shot("4-person");
  await page.locator(".chip-person").click();
  check((await rowCount(page)) === expected && (await page.locator(".chip-person").count()) === 0, name + ": removing the chip restores every row");

  // The People tab opens the same card.
  await page.click("#tab-users");
  await page.locator("#users .link-name").first().click();
  check((await page.locator("#profile:not([hidden]) #pc-title").count()) === 1, name + ": a name in the People tab opens the profile card");
  await page.keyboard.press("Escape");
  await page.click("#tab-timeline");

  // Layout.
  check((await scrollWidth(page)) <= width, name + ": no horizontal scroll (" + (await scrollWidth(page)) + " <= " + width + ")");
  check(!(await page.evaluate(() => {
    const bad = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const p = n.parentElement;
      if (p.closest(".mtext, .orig, script")) continue;
      if (/\b(undefined|NaN)\b|\bnull\b/.test(n.textContent)) bad.push(n.textContent.slice(0, 40));
    }
    return bad.length;
  })), name + ": no text node says undefined, null or NaN");
  if (phone) {
    await page.click("#ws-chbtn");
    await page.click('#ws-chlist .ch[data-surface=""]');
    const small = await page.evaluate(() => {
      const bad = [];
      for (const n of document.querySelectorAll(".ws-head button, .ws-head label, .ws-head input, #ws-chlist .ch, .av-btn")) {
        const r = n.getBoundingClientRect(), s = getComputedStyle(n);
        if (s.display === "none" || r.width === 0) continue;
        if (n.tagName === "INPUT") continue;
        if (r.height < 39.5 || r.width < 39.5) bad.push((n.className || n.tagName) + "=" + Math.round(r.width) + "x" + Math.round(r.height));
      }
      return bad;
    });
    check(small.length === 0, name + ": touch targets are at least 40px" + (small.length ? " (" + small.join(", ") + ")" : ""));
    await page.click("#ws-membtn");
    await page.waitForSelector("#ws-members.open");
    check(await page.evaluate(() => [...document.querySelectorAll("#ws-members .mem")].every((n) => n.getBoundingClientRect().height >= 39.5)), name + ": member rows are at least 40px");
    await shot("5-members");
    await page.mouse.click(10, 10);
    check(await page.locator("#ws-members.open").count() === 0, name + ": an outside tap closes the member sheet");
  }
  check(problems.length === 0, name + ": no console errors or failed requests" + (problems.length ? ": " + problems.join(" | ") : ""));
  await context.close();
}

async function runWorkspaceRun(browser, width, height) {
  console.log("--- workspace after a run " + width + "x" + height);
  const context = await browser.newContext({ viewport: { width, height }, colorScheme: "dark" });
  const page = await context.newPage();
  const problems = [];
  page.on("console", (m) => { if (m.type() === "error") problems.push("console: " + m.text()); });
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message));
  await page.goto(base + "?pack=minimal&subject=naive_bot#timeline");
  await page.waitForSelector("#timeline .msg");
  const before = await rowCount(page);
  await page.click("#run");
  await page.waitForSelector(".headline");
  await page.click("#tab-timeline");
  await page.waitForSelector("#timeline .msg.bot");
  const botRows = await page.locator("#timeline .msg.bot").count();
  const expectedAfter = await page.evaluate(async () => {
    const pack = await (await fetch("/api/pack?name=minimal")).json();
    const run = await (await fetch("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pack: "minimal", subject: "naive_bot" }) })).json();
    const byId = new Map(pack.events.map((e) => [e.id, e]));
    let n = 0;
    for (const x of run.entries) {
      if (x.type === "delivery" && x.event && byId.has(x.event) && !["edit", "delete", "react"].includes(byId.get(x.event).kind)) n += 1;
      else if (x.type === "observation" && x.kind === "action" && x.action) n += 1;
    }
    return n;
  });
  check(botRows > 0 && (await rowCount(page)) === expectedAfter && (await rowCount(page)) !== before, "minimal after a run: the feed shows what the run delivered plus the bot's replies (" + (await rowCount(page)) + " rows, " + botRows + " from the bot)");
  check(await page.locator("#timeline .msg.bot .bot-tag").count() === botRows, "minimal after a run: every bot reply carries a BOT tag");
  check(await page.locator("#ws-memlist .mem .bot-tag").count() >= 1, "minimal after a run: the bot is listed under Bot");
  await page.locator("#timeline .msg.bot .av-btn").first().click();
  check((await page.locator("#pc-title").innerText()) === "Naive bot" && (await page.locator("#profile").innerText()).includes("Bot"), "the bot's avatar opens a Bot profile");
  await page.keyboard.press("Escape");
  check(problems.length === 0, "workspace after a run: no console errors" + (problems.length ? ": " + problems.join(" | ") : ""));
  await context.close();
}

const browser = await chromium.launch({ channel: "msedge" });
// WS_ONLY=1 runs only the conversation workspace checks.
if (!process.env.WS_ONLY) {
  for (const [name, width, height] of [["desktop", 1440, 900], ["wide", 2560, 1440], ["phone", 390, 844]]) {
    for (const scheme of ["light", "dark"]) await runMode(browser, name, width, height, scheme);
  }
}
for (const [width, height] of [[1440, 900], [390, 844]]) {
  const names = ["minimal", "team-ten", "solo", "social-ten"].concat(lanternPack ? ["lantern-shelf"] : []);
  for (const name of names) await runWorkspace(browser, name, width, height, width > 760 ? "dark" : "light");
  await runWorkspace(browser, "minimal", width, height, width > 760 ? "light" : "dark");
  await runWorkspaceRun(browser, width, height);
}
await runReduced(browser);

// Motion check: the count-up starts at 0 and ends on the exact number; the tab indicator follows the tab.
{
  console.log("--- motion check");
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await page.goto(base + "?pack=team-ten&subject=naive_bot#checks");
  await page.waitForSelector("#scenario-card .stat-num");
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
