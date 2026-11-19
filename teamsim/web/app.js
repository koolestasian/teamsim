"use strict";
// All pack and bot text is untrusted: it only ever reaches the page through textContent.

const DAY = 86400000;
const PAGE = 400;
const TABS = ["checks", "timeline", "users", "controls"];
const CONTROL_ORDER = ["null", "oracle"];

// --- names a person can read -------------------------------------------------------

const SCENARIOS = {
  minimal: ["Demo day planning",
    "Four people plan a demo day: a date change, a private budget, a secret and a false claim.",
    "Four people plan a demo day in one session."],
  "team-ten": ["Team workspace",
    "A 10-person team chat over three weeks: plans change, one channel is private, a secret is pasted, someone goes away.",
    "A 10-person team chats for three weeks."],
  "social-ten": ["Social feed",
    "Ten people on a social feed: a friends-only post, a block and a deleted post.",
    "Ten people share posts on a social feed."],
  solo: ["Personal assistant",
    "One person over three weeks: changes of mind, a pasted document with a hidden instruction, a week away.",
    "One person talks to an assistant for three weeks."],
};
// What a user should keep in mind when reading results. The scenario's own technical notes
// stay available under "Technical notes".
const COMMON_LIMITS = [
  "Messages come from templates, so they don't show how real people write.",
  "Answers are matched against a few known phrasings; a correct answer worded differently can fail.",
  "Only facts said in the conversation are scored. A question about anything else has no test.",
];
const SCENARIO_LIMITS = {
  "social-ten": [
    "Posting, following and blocking are generic actions; your product has to map them to its own.",
    "A post's audience is a list of people. A rule like everyone except one person can't be described.",
  ],
  solo: [
    "With one person, tests about who may see what don't apply.",
    "The pasted document is scored only on whether the bot repeats a harmless code it asks for.",
  ],
};

const BOTS = {
  naive_bot: ["Naive bot", "Remembers everything and answers by matching words."],
  careful_bot: ["Careful bot", "Tracks the latest answer and who may see it."],
  null: ["Silent", "Never replies."],
  oracle: ["Perfect", "Always right."],
  "defect:stale": ["Out of date", "Gives old answers."],
  "defect:gullible": ["Gullible", "Believes anyone."],
  "defect:leaky": ["Leaky", "Shares private info."],
  "defect:echo": ["Echo", "Repeats secrets."],
  "defect:amnesiac": ["Forgetful", "Skips what you missed."],
  "defect:deaf": ["DMs only", "Ignores channels."],
};
const TEST_TYPES = {
  answer: "latest answer", withhold: "kept from outsiders", no_leak: "stays private",
  no_echo: "no repeat", catch_up: "catch-up",
};
const CHIPS = {
  stale: "Old answer", leaked: "Leaked", missing: "Wrong answer", missed: "Missed updates",
  no_response: "No reply", unauthorised: "Believed a false claim", echoed: "Repeated secret",
};

const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
const humanize = (s) => String(s).replace(/[_-]+/g, " ").trim();
const plural = (n, word) => n + " " + word + (n === 1 ? "" : "s");
const people = (n) => (n === 1 ? "1 person" : n + " people");

function person(id) {
  if (id === "subject" || id === "bot") return "Bot";
  const m = /^(.*?)-(\d+)$/.exec(String(id));
  return m ? cap(humanize(m[1])) + " " + m[2] : cap(humanize(id));
}
function place(id) {
  id = String(id);
  return id.startsWith("direct:") ? "DM with " + person(id.slice(7)) : "#" + id;
}
const topic = (key) => humanize(String(key).replace(/^f\./, ""));
const list = (names) => new Intl.ListFormat("en", { type: "conjunction" }).format(names);
const dayOf = (t) => Math.floor(t / DAY) + 1;
function clock(t) {
  const rest = t % DAY, h = Math.floor(rest / 3600000), m = Math.floor((rest % 3600000) / 60000);
  return String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0");
}
const when = (t) => (t == null ? "" : "Day " + dayOf(t) + ", " + clock(t));
const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const scenarioName = (pack) => (SCENARIOS[pack.name] ? SCENARIOS[pack.name][0] : String(pack.title || pack.name).split(":")[0]);
const scenarioLine = (pack) => (SCENARIOS[pack.name] ? SCENARIOS[pack.name][2] : String(pack.title || "").split(":")[0]);
const scenarioAbout = (pack) => (SCENARIOS[pack.name] ? SCENARIOS[pack.name][1] : String(pack.title || ""));
const botName = (id) => (BOTS[id] ? BOTS[id][0] : cap(humanize(id)));
const botAbout = (id) => (BOTS[id] ? BOTS[id][1] : "");

// --- state and DOM helpers -------------------------------------------------------------

const $ = (id) => document.getElementById(id);
const state = {
  packs: [], subjects: [], pack: null, run: null, rows: [], hit: new Set(), digests: {},
  busy: false, tab: "checks", filter: "key", limit: PAGE, selected: null, matrices: {}, matrixBusy: false,
  catchKeys: {}, ready: false, card: null,
};

function el(tag, props, ...kids) {
  const node = document.createElement(tag);
  if (props) for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else node.setAttribute(k, v);
  }
  for (const kid of kids) if (kid != null) node.append(kid);
  return node;
}
const clear = (node) => node.replaceChildren();
function restart(node, cls) {
  node.classList.remove(cls);
  void node.offsetWidth;
  node.classList.add(cls);
}

async function api(path, body) {
  const options = body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  };
  const response = await fetch(path, options);
  let data = null;
  try { data = await response.json(); } catch (_) { /* fall through */ }
  if (!response.ok) throw new Error((data && data.error) || "request failed (" + response.status + ")");
  return data;
}

function setStatus(text, isError) {
  const node = $("status");
  node.textContent = text || "";
  node.className = isError ? "error" : "";
}
function setBusy(busy) {
  state.busy = busy;
  $("run").disabled = busy;
  $("run").classList.toggle("running", busy);
  $("run-label").textContent = busy ? "Running…" : "Run test";
  $("pack").disabled = busy;
  $("subject").disabled = busy;
}

// --- pack data ---------------------------------------------------------------------------

function index(pack) {
  pack.factById = new Map(pack.facts.map((f) => [f.id, f]));
  pack.eventById = new Map(pack.events.map((e) => [e.id, e]));
  pack.checkById = new Map(pack.checks.map((c) => [c.id, c]));
  pack.actorIds = new Set(pack.actors.map((a) => a.id));
  pack.surfaceById = new Map(pack.surfaces.map((s) => [s.id, s]));
  return pack;
}

// The fact key a check is about: its own key, the key of the fact it names, or (catch-up) the detail.
function factKeyOf(pack, check, v) {
  if (check && check.key) return check.key;
  if (check && check.fact) {
    const f = pack.factById.get(check.fact);
    return f ? f.key : check.fact.replace(/^f\./, "");
  }
  if (v && v.detail && v.detail.length) return v.detail[0].replace(/^f\./, "");
  return state.catchKeys[check ? check.id : ""] || "";
}

// Every value a key has held, oldest to newest, following supersedes links.
function chainOf(pack, key) {
  const same = pack.facts.filter((f) => f.key === key && f.kind !== "claim");
  if (!same.length) return [];
  const replaced = new Set(same.map((f) => f.supersedes).filter(Boolean));
  const heads = same.filter((f) => !replaced.has(f.id));
  let cur = heads.length ? heads[heads.length - 1] : same[same.length - 1];
  const out = [];
  const seen = new Set();
  while (cur && !seen.has(cur.id)) {
    seen.add(cur.id);
    out.unshift(cur);
    cur = cur.supersedes ? pack.factById.get(cur.supersedes) : null;
  }
  return out;
}

// Who may know a fact, in words; empty when everyone may.
function audienceOf(fact) {
  const a = (fact && fact.audience) || [];
  if (!a.length || a.includes("*")) return "";
  const groups = a.filter((x) => x.startsWith("group:")).map((x) => x.slice(6));
  const names = a.filter((x) => !x.startsWith("group:")).map(person);
  return groups.length ? list(groups) : list(names);
}

// --- the run, joined to the pack ---------------------------------------------------------------

function buildRows(pack, run) {
  const rows = [];
  if (!run) {
    for (const e of pack.events) rows.push({ t: e.at, n: null, event: e, surface: e.surface, who: e.actor, text: e.text });
    return rows;
  }
  for (const entry of run.entries) {
    if (entry.type === "delivery" && entry.event) {
      const e = pack.eventById.get(entry.event);
      if (e) rows.push({ t: entry.t_ms, n: entry.n, event: e, surface: e.surface, who: e.actor, text: e.text });
    } else if (entry.type === "observation" && entry.kind === "action" && entry.action) {
      rows.push({ t: entry.t_ms, n: entry.n, bot: entry, surface: entry.action.surface, who: "bot", text: entry.action.text });
    }
  }
  return rows;
}

function isKey(row) {
  if (row.bot) return true;
  const e = row.event;
  return !!(e.probe || (e.discloses && e.discloses.length) || e.kind === "away" || e.kind === "back");
}

function tagsFor(pack, row) {
  const out = [];
  if (row.bot) return out;
  const e = row.event;
  for (const id of e.discloses || []) {
    const f = pack.factById.get(id);
    if (!f) continue;
    const name = topic(f.key);
    if (f.kind === "claim") out.push("Unverified claim: " + name + " = " + f.value);
    else if (f.kind === "secret") out.push("Secret: " + name);
    else {
      const who = audienceOf(f);
      const head = f.supersedes ? "Update: " + name + " → " + f.value : "Fact: " + name + " = " + f.value;
      out.push(head + (who ? " · private to " + who : ""));
    }
  }
  if (e.probe) out.push("Question for the bot");
  if (e.kind === "edit") out.push("Edited");
  return out;
}

// Events without text still say what happened.
function actionText(pack, row) {
  const e = row.event;
  if (!e || row.text != null) return null;
  const target = e.target && pack.eventById.get(e.target);
  switch (e.kind) {
    case "away": return "Away";
    case "back": return "Back";
    case "react": return target ? "Reacted to " + person(target.actor) + "'s message" : "Reacted to a message";
    case "delete": return target ? "Deleted " + (target.actor === e.actor ? "their" : person(target.actor) + "'s") + " message" : "Deleted a message";
    case "subject_join": return "Bot joined " + place(e.surface);
    case "op": return "Used the product";
    default: return cap(humanize(e.kind));
  }
}

// --- tests: title, test line, verdict, reason ----------------------------------------------------

function replyFor(run, v) {
  const entry = v.entries.map((n) => run.entries[n - 1]).find((x) => x && x.type === "observation" && x.action);
  return entry ? entry.action.text : null;
}

// Everything the list row and the detail panel say about one test.
function describeTest(v) {
  const pack = state.pack, run = state.run;
  const check = pack.checkById.get(v.check);
  const key = factKeyOf(pack, check, v);
  if (v.kind === "catch_up" && v.detail && v.detail.length) state.catchKeys[v.check] = v.detail[0].replace(/^f\./, "");
  const probe = v.events.length ? pack.eventById.get(v.events[0]) : null;
  const delivery = probe && run.entries.find((x) => x.type === "delivery" && x.event === probe.id);
  const asker = probe ? person(probe.actor) : "the asker";
  const fact = check && check.fact ? pack.factById.get(check.fact) : null;
  const audience = fact ? audienceOf(fact) : "";
  const chain = key ? chainOf(pack, key) : [];
  const current = chain.length ? chain[chain.length - 1].value : "";
  const reply = replyFor(run, v);
  const name = key ? cap(topic(key)) : "Test";
  const title = v.kind === "harness" ? "Bot connection" : name;
  let line = "";
  switch (v.kind) {
    case "answer": line = "Gives " + asker + " the latest answer"; break;
    case "withhold": line = "Doesn't tell " + asker + ", who isn't allowed to know"; break;
    case "no_leak": line = audience ? "Keeps it where only " + audience + " can read" : "Keeps it private"; break;
    case "no_echo": line = "Doesn't repeat the secret"; break;
    case "catch_up": line = "Tells " + asker + " what changed while they were away"; break;
    case "harness": line = "Starts, follows the rules and replies in time"; break;
    default: line = "";
  }
  return { v, check, key, probe, delivery, asker, audience, chain, current, reply, title, line, verdict: verdictOf(v, { asker, audience, chain, current, reply, key }) };
}

function verdictOf(v, ctx) {
  if (v.verdict === "pass") return { chip: "Passed", cls: "pass", why: "The bot got this right." };
  if (v.verdict === "not_applicable") return { chip: "Not scored", cls: "na", why: "This test didn't apply to this run." };
  if (v.verdict === "harness_error") return { chip: "Didn't run", cls: "fail", why: "The bot crashed, broke the rules or timed out." };
  const reason = v.reason || "fail";
  const chip = CHIPS[reason] || cap(humanize(reason));
  let why = chip + ".";
  const current = ctx.current || "the current value";
  if (reason === "stale") {
    let old = ctx.chain.length ? ctx.chain[0].value : "";
    const said = (ctx.reply || "").toLowerCase();
    for (const f of ctx.chain.slice(0, -1)) {
      if ((f.forms || [f.value]).some((form) => said.includes(String(form).toLowerCase()))) { old = f.value; break; }
    }
    why = "It gave " + old + ", which was later changed to " + current + ".";
  } else if (reason === "leaked") {
    why = v.kind === "no_leak"
      ? "The bot posted it where people outside " + (ctx.audience || "the audience") + " can read."
      : ctx.asker + " isn't allowed to know this, and the bot told them.";
  } else if (reason === "missing") why = "The reply doesn't contain " + current + ".";
  else if (reason === "missed") why = "The reply leaves out what changed while " + ctx.asker + " was away.";
  else if (reason === "no_response") why = "The bot didn't answer.";
  else if (reason === "unauthorised") why = "It repeated a claim from someone who can't make that call.";
  else if (reason === "echoed") why = "It repeated the secret in the channel where it was pasted.";
  return { chip, cls: "fail", why };
}

function groupOf(v) {
  if (v.verdict === "fail" || v.verdict === "harness_error") return 0;
  if (v.verdict === "not_applicable") return 2;
  return 1;
}

// --- tabs ----------------------------------------------------------------------------------------

function placeIndicator(animate) {
  const ind = $("tab-ind"), tab = $("tab-" + state.tab);
  if (!tab || !tab.offsetWidth) return;
  const target = "translateX(" + tab.offsetLeft + "px) scaleX(" + tab.offsetWidth + ")";
  if (animate && state.ready) {
    ind.classList.remove("still");
    ind.style.transform = target;
    return;
  }
  ind.classList.add("still");
  ind.style.transform = target;
  void ind.offsetWidth;
  ind.classList.remove("still");
}

function showTab(name, keepHash) {
  if (!TABS.includes(name)) name = "checks";
  if (name === "checks" && !state.run) name = "timeline";
  const changed = name !== state.tab;
  state.tab = name;
  $("tab-checks").setAttribute("aria-disabled", state.run ? "false" : "true");
  for (const t of TABS) {
    const on = t === name;
    $("tab-" + t).setAttribute("aria-selected", on ? "true" : "false");
    $("tab-" + t).tabIndex = on ? 0 : -1;
    $("panel-" + t).hidden = !on;
  }
  if (changed && state.ready) restart($("panel-" + name), "enter");
  placeIndicator(changed);
  if (!keepHash) {
    try { history.replaceState(null, "", location.pathname + location.search + "#" + name); } catch (_) { /* ignore */ }
  }
  if (name === "controls") showControls();
}

// --- summary ------------------------------------------------------------------------------------

function countUp(node, to) {
  node.textContent = String(to);
  if (reduced() || to === 0) return;
  const start = performance.now(), dur = 320;
  node.textContent = "0";
  const tick = (now) => {
    const p = Math.min(1, (now - start) / dur);
    node.textContent = String(p < 1 ? Math.round(to * (1 - Math.pow(1 - p, 3))) : to);
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  setTimeout(() => { node.textContent = String(to); }, dur + 120);
}

function renderStrip() {
  const pack = state.pack, strip = $("strip"), run = state.run;
  clear(strip);
  const summary = state.packs.find((p) => p.name === pack.name);
  $("tab-checks").textContent = "Results " + pack.checks.length;
  placeIndicator(false);
  if (!run) {
    $("live").textContent = "";
    return;
  }
  const checks = run.report.checks;
  const failed = checks.filter((c) => c.verdict === "fail" || c.verdict === "harness_error").length;
  const passed = checks.filter((c) => c.verdict === "pass").length;
  const na = checks.filter((c) => c.verdict === "not_applicable").length;
  const total = failed + passed;
  const head = el("h1", { class: "headline", "aria-hidden": "true" });
  let finalText, num;
  if (failed === 0) {
    num = el("span", { class: "pass", text: String(total) });
    head.append("All ", num, " " + (total === 1 ? "test" : "tests") + " passed");
    finalText = "All " + total + " " + (total === 1 ? "test" : "tests") + " passed";
  } else {
    num = el("span", { class: "fail", text: String(failed) });
    head.append(num, " of " + total + " " + (total === 1 ? "test" : "tests") + " failed");
    finalText = failed + " of " + total + " " + (total === 1 ? "test" : "tests") + " failed";
  }
  const bar = el("div", { class: "bar", role: "group", "aria-label": passed + " passed, " + failed + " failed" });
  const segment = (cls, n, label) => {
    const s = el("span", { class: "seg " + cls, title: n + " " + label, tabindex: "0" });
    s.style.flexGrow = String(n);
    return s;
  };
  if (passed) bar.append(segment("pass", passed, "passed"));
  if (failed) bar.append(segment("fail", failed, "failed"));
  const sub = [botName(state.runSubject), scenarioName(pack), people(summary.users), plural(summary.days, "day")];
  if (na) sub.push(na + " not scored");
  strip.append(head, bar, el("p", { class: "muted small sub", text: sub.join(" · ") }));
  if (state.previous) {
    strip.append(el("p", { class: "muted small sub", text: state.previous === run.digest ? "Same result as last run" : "Different result from last run" }));
  }
  $("live").textContent = finalText;
  countUp(num, failed === 0 ? total : failed);
}

async function copyDigest(button, text) {
  let ok = false;
  try { await navigator.clipboard.writeText(text); ok = true; } catch (_) { /* fall back */ }
  if (!ok) {
    const box = el("textarea");
    box.value = text;
    document.body.append(box);
    box.select();
    try { ok = document.execCommand("copy"); } catch (_) { ok = false; }
    box.remove();
  }
  clear(button);
  if (ok) button.append(el("span", { class: "tick", "aria-hidden": "true", text: "✓" }), "Copied");
  else button.append("Copy failed");
  restart(button, "pop");
  setTimeout(() => { button.classList.remove("pop"); button.textContent = "Copy"; }, 1500);
}

// --- results tab ----------------------------------------------------------------------------------

const NARROW = window.matchMedia("(max-width: 1279px)");
const STACKED = window.matchMedia("(max-width: 1099px)");
const rowFor = (id) => [...$("check-list").querySelectorAll(".result-row")].find((r) => r.dataset.check === id);

// On a phone the detail opens directly under the selected row; on wider screens it sits in the
// right-hand column.
function placeEvidence(animate) {
  const box = $("evidence"), listEl = $("check-list");
  const row = state.selected && rowFor(state.selected);
  if (NARROW.matches && row) {
    if (animate && !reduced()) {
      box.classList.add("closed");
      row.after(box);
      void box.offsetWidth;
      box.classList.remove("closed");
    } else {
      box.classList.remove("closed");
      row.after(box);
    }
  } else if (box.parentElement !== $("result")) {
    box.classList.remove("closed");
    listEl.after(box);
  }
}

function renderChecks() {
  const run = state.run;
  $("result").hidden = !run;
  if (!run) return;
  const groups = [[], [], []];
  for (const v of run.report.checks) groups[groupOf(v)].push(describeTest(v));
  const labels = ["Failed", "Passed", "Not scored"];
  const listEl = $("check-list");
  if ($("evidence").parentElement === listEl) listEl.after($("evidence"));
  clear(listEl);
  let i = 0;
  groups.forEach((items, g) => {
    if (!items.length) return;
    listEl.append(el("p", { class: "group-label", text: labels[g] + " " + items.length }));
    for (const d of items) {
      const row = el("button", { type: "button", class: "result-row", "aria-pressed": "false" },
        el("span", { class: "dot " + d.verdict.cls, "aria-hidden": "true" }),
        el("span", { class: "rtext" }, el("span", { class: "key", text: d.title }), el("small", { text: d.line })),
        el("span", { class: "chip " + d.verdict.cls, text: d.verdict.chip }));
      row.dataset.check = d.v.check;
      row.style.setProperty("--i", String(Math.min(i, 12)));
      i += 1;
      listEl.append(row);
    }
  });
  if (!reduced()) {
    listEl.classList.add("stagger");
    clearTimeout(state.staggerTimer);
    state.staggerTimer = setTimeout(() => listEl.classList.remove("stagger"), 12 * 18 + 320);
  }
  const first = groups[0][0] || groups[1][0] || groups[2][0];
  state.selected = null;
  selectCheck(first ? first.v.check : null, false);
}

function selectCheck(id, user) {
  if (user && id === state.selected && $("evidence").childElementCount) return;
  const box = $("evidence");
  const listEl = $("check-list");
  // Phone: the section that was open collapses while the new one opens.
  if (user && NARROW.matches && box.parentElement === listEl && !reduced()) {
    const ghost = box.cloneNode(true);
    ghost.removeAttribute("id");
    ghost.setAttribute("aria-hidden", "true");
    ghost.setAttribute("inert", "");
    box.before(ghost);
    requestAnimationFrame(() => requestAnimationFrame(() => ghost.classList.add("closed")));
    setTimeout(() => ghost.remove(), 260);
  }
  state.selected = id;
  for (const row of listEl.querySelectorAll(".result-row")) {
    row.setAttribute("aria-pressed", row.dataset.check === id ? "true" : "false");
  }
  renderEvidence(user);
  placeEvidence(user);
  if (user && NARROW.matches) {
    const row = rowFor(id);
    setTimeout(() => { if (row && state.selected === id) row.scrollIntoView({ block: "start", behavior: reduced() ? "auto" : "smooth" }); }, reduced() ? 0 : 240);
  }
}
NARROW.addEventListener("change", () => placeEvidence(false));

function renderEvidence(animate) {
  const pack = state.pack, run = state.run, box = $("evidence");
  clear(box);
  const v = run && run.report.checks.find((c) => c.check === state.selected);
  if (!v) return;
  const d = describeTest(v);
  const failing = v.verdict === "fail" || v.verdict === "harness_error";
  const body = el("div", { class: "ev-body" });
  box.append(el("div", { class: "ev-clip" }, body));

  body.append(el("div", { class: "ev-head" },
    el("h2", { text: d.title }),
    el("span", { class: "chip " + d.verdict.cls, text: d.verdict.chip })));
  if (d.line) body.append(el("p", { class: "rule", text: d.line }));
  if (failing) {
    body.append(el("div", { class: "why" },
      el("span", { class: "why-label", text: "Why it failed" }),
      el("p", { text: d.verdict.why })));
  }
  if (d.probe) {
    body.append(el("div", { class: "question" },
      el("div", { class: "meta", text: d.asker + " in " + place(d.probe.surface) + " · " + when(d.delivery ? d.delivery.t_ms : d.probe.at) }),
      el("blockquote", { text: d.probe.text || "" })));
  }

  const expected = el("div", null, el("dt", { text: "Expected" }));
  let expectedText;
  if (v.kind === "answer" || v.kind === "catch_up") expectedText = d.current || "The current value";
  else if (v.kind === "harness") expectedText = "A bot that connects, follows the rules and replies in time";
  else expectedText = "Nothing about the " + topic(d.key || "fact");
  expected.append(el("dd", { text: expectedText }));
  if ((v.kind === "answer" || v.kind === "catch_up") && d.chain.length > 1) {
    const line = el("div", { class: "chain" });
    d.chain.forEach((f, i) => {
      if (i) line.append(" → ");
      line.append(i < d.chain.length - 1 ? el("s", { text: f.value }) : el("strong", { text: f.value }));
    });
    expected.append(line);
  }
  const said = el("div", { class: failing ? "wrong" : "" }, el("dt", { text: "Bot said" }));
  if (v.kind === "harness") said.append(el("dd", { text: failing ? d.verdict.chip : "Connected and replied in time" }));
  else if (d.reply != null) said.append(el("dd", { text: d.reply }));
  else said.append(el("dd", { class: "muted", text: "No reply" }));
  body.append(el("dl", { class: "comparison" }, expected, said));

  if (v.entries.length) {
    const go = el("button", { type: "button", class: "secondary", text: "Show in conversation" });
    go.addEventListener("click", () => showInTimeline(v));
    body.append(el("div", { class: "ev-actions" }, go));
  }
  if (animate) restart(body, "enter");
}

// --- conversation tab ---------------------------------------------------------------------------------

function showInTimeline(v) {
  state.hit = new Set(v.entries);
  state.filter = "key";
  $("place").value = "";
  showTab("timeline");
  renderTimeline(true, 0);
}

function renderTimeline(scrollToHit, fromIndex) {
  const pack = state.pack, box = $("timeline");
  const all = state.filter === "all", where = $("place").value;
  for (const b of $("seg").querySelectorAll("button")) b.setAttribute("aria-pressed", b.dataset.filter === state.filter ? "true" : "false");
  const rows = state.rows.filter((r) => (!where || r.surface === where) && (all || isKey(r) || state.hit.has(r.n)));
  let limit = state.limit;
  if (scrollToHit) {
    const at = rows.findIndex((r) => state.hit.has(r.n));
    if (at >= limit) limit = state.limit = Math.ceil((at + 1) / PAGE) * PAGE;
  }
  const frag = document.createDocumentFragment();
  rows.slice(0, limit).forEach((r, i) => {
    const meta = el("div", { class: "event-meta" }, el("strong", { text: person(r.who) }), el("span", { text: place(r.surface) }));
    for (const t of tagsFor(pack, r)) meta.append(el("span", { class: "tag" + (t === "Question for the bot" ? " ask" : ""), text: t }));
    const cls = "event" + (r.bot ? " bot" : "") + (state.hit.has(r.n) ? " hit" : "") + (fromIndex != null && i >= fromIndex ? " fresh" : "");
    const action = actionText(pack, r);
    frag.append(el("div", { class: cls },
      r.t == null
        ? el("time", { title: "Sent in response to an earlier message; the time is set when the test runs." }, el("span", { text: "—" }))
        : el("time", null, el("span", { text: "Day " + dayOf(r.t) }), el("span", { text: clock(r.t) })),
      el("div", null, meta, action != null
        ? el("p", { class: "action", text: action })
        : el("p", { text: r.text == null ? "" : r.text }))));
  });
  box.replaceChildren(frag);
  $("count").textContent = rows.length + " of " + state.rows.length + " messages";
  const more = $("more");
  more.hidden = rows.length <= limit;
  more.textContent = "Show " + Math.min(PAGE, rows.length - limit) + " more";
  if (scrollToHit) {
    box.classList.add("pulse");
    clearTimeout(state.pulseTimer);
    state.pulseTimer = setTimeout(() => box.classList.remove("pulse"), 1000);
    const first = box.querySelector(".event.hit");
    if (first) first.scrollIntoView({ block: "center", behavior: reduced() ? "auto" : "smooth" });
  }
}

// --- people and verification ----------------------------------------------------------------------------

function renderUsers(pack) {
  const head = ["Person", "Role", "Typical reply", "Online", "Away", "Typos", "Splits messages", "Wrong channel", "Asks the bot"];
  const table = $("users");
  clear(table);
  table.append(el("thead", null, el("tr", null, ...head.map((h) => el("th", { text: h })))));
  const body = el("tbody");
  const dash = "–";
  const pct = (v) => (v == null ? dash : v + "%");
  const hour = (h) => (Number.isInteger(h) ? h + ":00" : String(h));
  for (const a of pack.actors) {
    const t = a.traits || {};
    const reply = t.reply_median_s == null ? dash : t.reply_median_s >= 90 ? Math.round(t.reply_median_s / 60) + " min" : t.reply_median_s + " s";
    const hours = t.active_hours ? hour(t.active_hours.start) + "–" + hour(t.active_hours.end) : dash;
    const away = t.away && t.away.length ? "Days " + t.away.map((x) => x.from_day + "–" + x.to_day).join(", ") : dash;
    const cells = [person(a.id), a.role ? cap(a.role) : dash, reply, hours, away,
      pct(t.typo_pct), pct(t.split_pct), pct(t.wrong_place_pct), pct(t.probe_pct)];
    body.append(el("tr", null, ...cells.map((c, i) => el(i === 0 ? "th" : "td", { text: String(c) }))));
  }
  table.append(body);
}

function renderPlaces(pack) {
  const select = $("place");
  select.replaceChildren(el("option", { text: "All channels", value: "" }));
  for (const s of pack.surfaces) {
    const readers = s.members.filter((m) => pack.actorIds.has(m));
    const label = s.kind === "direct" || readers.length === pack.actors.length ? place(s.id) : place(s.id) + " · " + readers.map(person).join(", ");
    select.append(el("option", { text: label, value: s.id }));
  }
}

function renderAbout(pack) {
  const summary = state.packs.find((p) => p.name === pack.name);
  $("purpose").textContent = scenarioAbout(summary);
  const limits = $("limits");
  clear(limits);
  for (const text of COMMON_LIMITS.concat(SCENARIO_LIMITS[pack.name] || [])) limits.append(el("li", { text }));
  $("tech-purpose").textContent = summary.purpose;
  const tech = $("tech-limits");
  clear(tech);
  for (const text of summary.limits) tech.append(el("li", { text }));
}

function testRowTitle(pack, check) {
  if (check.kind === "harness") return "Bot connection";
  const key = factKeyOf(pack, check, null);
  if (!key) return "Catch-up after being away";
  return cap(topic(key)) + " · " + (TEST_TYPES[check.kind] || humanize(check.kind));
}

// "pass" / "fail (stale)" as the server writes it, in plain words.
function verdictWords(text) {
  const m = /^(\w+)(?: \((\w+)\))?$/.exec(String(text).trim());
  if (!m) return String(text);
  if (m[1] === "pass") return "pass";
  if (m[1] === "fail") return m[2] ? (CHIPS[m[2]] || cap(humanize(m[2]))).toLowerCase() : "fail";
  if (m[1] === "harness_error") return "didn't run";
  return humanize(m[1]);
}

function problemText(pack, line) {
  const m = /^(\S+): check (\S+): expected (.+), observed (.+)$/.exec(line);
  if (!m) return "A reference bot does not behave as expected.";
  const check = pack.checkById.get(m[2]);
  const name = check ? testRowTitle(pack, check) : "a test";
  return botName(m[1]) + " on " + name + ": expected " + verdictWords(m[3]) + ", got " + verdictWords(m[4]) + ".";
}

function renderMatrix(pack, data, reveal) {
  const table = $("matrix");
  clear(table);
  const bots = Object.keys(data.matrix).sort((a, b) => {
    const ia = CONTROL_ORDER.indexOf(a), ib = CONTROL_ORDER.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });
  const col = (node, i) => { node.style.setProperty("--c", String(i)); return node; };
  table.className = reveal ? "reveal" : "";
  table.append(el("thead", null, el("tr", null, el("th", { text: "Test" }),
    ...bots.map((c, i) => col(el("th", { text: botName(c) }), i)))));
  const body = el("tbody");
  for (const check of pack.checks) {
    const cells = bots.map((c, i) => {
      const cell = data.matrix[c][check.id];
      if (!cell) return col(el("td"), i);
      if (cell.verdict === "pass") return col(el("td", { class: "pass", text: "✓" }), i);
      if (cell.verdict === "fail") return col(el("td", { class: "caught", title: CHIPS[cell.reason] || cap(humanize(cell.reason || "fail")), text: "Caught" }), i);
      return col(el("td", { class: "na", text: "–" }), i);
    });
    body.append(el("tr", null, el("th", { text: testRowTitle(pack, check) }), ...cells));
  }
  table.append(body);
  $("matrix-wrap").hidden = false;
  const mism = $("mismatches");
  clear(mism);
  for (const line of data.problems) mism.append(el("li", { class: "fail", text: problemText(pack, line) }));
  if (!data.problems.length) mism.append(el("li", { class: "pass", text: "Every test catches its flaw and passes the Perfect bot." }));
}

function setVerifyButton(busy) {
  const b = $("run-controls");
  b.classList.toggle("running", busy);
  b.disabled = busy;
  $("run-controls-label").textContent = busy ? "Verifying…" : "Verify tests";
  $("progress").classList.toggle("on", busy);
}

// Opening the tab only shows what has already run; verification runs on the button alone.
function showControls() {
  const pack = state.pack;
  if (!pack || state.matrixBusy) return;
  const cached = state.matrices[pack.name];
  $("matrix-note").textContent = "Runs 8 reference bots with known flaws.";
  $("run-controls").hidden = !!cached;
  if (cached) { renderMatrix(pack, cached, false); return; }
  $("matrix-wrap").hidden = true;
  clear($("mismatches"));
}

async function runControls() {
  const pack = state.pack;
  if (!pack || state.matrixBusy || state.busy) return;
  state.matrixBusy = true;
  setVerifyButton(true);
  $("matrix-wrap").hidden = true;
  clear($("mismatches"));
  try {
    const data = await api("/api/validate", { pack: pack.name });
    state.matrices[pack.name] = data;
    if (state.pack === pack) {
      renderMatrix(pack, data, !reduced());
      $("run-controls").hidden = true;
    }
  } catch (error) {
    clear($("mismatches"));
    $("mismatches").append(el("li", { class: "fail", text: error.message }));
  } finally {
    state.matrixBusy = false;
    setVerifyButton(false);
  }
}

// --- footer: run details -------------------------------------------------------------------------------------

function renderDetails() {
  const box = $("details-body"), root = $("run-details"), run = state.run;
  clear(box);
  root.hidden = !run;
  if (!run) return;
  const copy = el("button", { type: "button", class: "text-button", text: "Copy" });
  copy.addEventListener("click", () => copyDigest(copy, run.digest));
  box.append(
    el("p", { class: "id-line" }, el("span", { class: "k", text: "Run ID" }), el("span", { class: "mono", title: "The same scenario and bot always produce this ID.", text: run.digest }), copy),
    el("p", { class: "id-line" }, el("span", { class: "k", text: "Scenario" }), el("span", { class: "mono", text: state.pack.name })),
    el("p", { class: "id-line" }, el("span", { class: "k", text: "Bot" }), el("span", { class: "mono", text: state.runSubject })));
  const table = el("table", { class: "ids" });
  table.append(el("thead", null, el("tr", null, el("th", { text: "Test id" }), el("th", { text: "Record entries" }))));
  const body = el("tbody");
  for (const v of run.report.checks) {
    body.append(el("tr", null, el("td", { class: "mono", text: v.check }), el("td", { class: "mono", text: v.entries.length ? v.entries.join(", ") : "–" })));
  }
  table.append(body);
  box.append(el("div", { class: "table-scroll" }, table));
}

// --- actions ---------------------------------------------------------------------------------------------------

function packChips(pack) {
  const kinds = new Set(pack.checks.map((c) => c.kind));
  const out = [];
  if (pack.facts.some((f) => f.supersedes)) out.push("Changed plans");
  if (kinds.has("withhold") || kinds.has("no_leak")) out.push("Private info");
  if (kinds.has("no_echo")) out.push("Secrets");
  if (pack.facts.some((f) => f.kind === "claim")) out.push("False claims");
  if (kinds.has("catch_up") || pack.events.some((e) => e.kind === "away")) out.push("Time away");
  return out;
}

function tween(node, from, to, animate) {
  if (!animate || reduced() || from === to) { node.textContent = String(to); return; }
  const start = performance.now(), dur = 320;
  node.textContent = String(from);
  const tick = (now) => {
    const p = Math.min(1, (now - start) / dur);
    node.textContent = String(Math.round(from + (to - from) * (1 - Math.pow(1 - p, 3))));
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  setTimeout(() => { node.textContent = String(to); }, dur + 120);
}

// The scenario card needs the loaded scenario, so it is drawn when loadPack finishes.
function renderScenarioCard(animate) {
  const pack = state.pack, summary = state.packs.find((p) => p.name === pack.name), box = $("scenario-card");
  const questions = pack.events.filter((e) => e.probe).length;
  const nums = [summary.users, summary.days, pack.checks.length, questions];
  const labels = [["person", "people"], ["day", "days"], ["test", "tests"], ["question to the bot", "questions to the bot"]];
  const prev = (state.card && state.card.nums) || [0, 0, 0, 0];
  const body = el("div", { class: "card-body" }, el("h2", { class: "card-name", text: scenarioName(summary) }),
    el("p", { class: "card-line", text: scenarioLine(summary) }));
  const grid = el("div", { class: "stats" });
  nums.forEach((n, i) => {
    const num = el("span", { class: "stat-num", text: String(n) });
    tween(num, prev[i], n, animate);
    grid.append(el("div", { class: "stat" }, num, el("span", { class: "stat-label", text: labels[i][n === 1 ? 0 : 1] })));
  });
  body.append(grid);
  const chips = packChips(pack);
  if (chips.length) {
    const row = el("div", { class: "chips" });
    chips.forEach((c, i) => { const chip = el("span", { class: "tagchip", text: c }); chip.style.setProperty("--i", String(i)); row.append(chip); });
    body.append(el("div", { class: "tests-for" }, el("span", { text: "Tests for" }), row));
  }
  box.replaceChildren(body);
  if (animate && !reduced()) restart(body, "fade");
  state.card = { nums };
}

function renderBotCard(animate) {
  const bot = $("subject").value;
  const head = el("div", { class: "bot-head" }, el("h2", { class: "card-name", text: botName(bot) }));
  if (bot !== "naive_bot" && bot !== "careful_bot" && bot !== "oracle") head.append(el("span", { class: "flaw", text: "Known flaw" }));
  const body = el("div", { class: "card-body" }, head, el("p", { class: "card-line", text: botAbout(bot) }));
  $("bot-card").replaceChildren(body);
  if (animate && !reduced()) restart(body, "fade");
}

async function loadPack(name) {
  setStatus("Loading scenario…");
  state.pack = index(await api("/api/pack?name=" + encodeURIComponent(name)));
  const animateCard = state.ready;
  state.run = null;
  state.hit = new Set();
  state.limit = PAGE;
  state.rows = buildRows(state.pack, null);
  renderStrip();
  renderChecks();
  renderScenarioCard(animateCard);
  if (state.tab === "checks") showTab("timeline");
  else $("tab-checks").setAttribute("aria-disabled", "true");
  renderPlaces(state.pack);
  renderUsers(state.pack);
  renderTimeline(false, null);
  renderAbout(state.pack);
  renderDetails();
  setStatus("");
  if (state.tab === "controls") showControls();
}

async function doRun() {
  const name = $("pack").value, subject = $("subject").value;
  setBusy(true);
  setStatus("");
  try {
    if (!state.pack || state.pack.name !== name) await loadPack(name);
    const run = await api("/api/run", { pack: name, subject });
    const firstRun = !state.run;
    const key = name + "|" + subject;
    state.previous = state.digests[key] || null;
    state.digests[key] = run.digest;
    state.run = run;
    state.runSubject = subject;
    state.hit = new Set();
    state.limit = PAGE;
    state.rows = buildRows(state.pack, run);
    renderStrip();
    renderChecks();
    renderTimeline(false, null);
    renderDetails();
    if (firstRun) showTab("checks");
    else $("tab-checks").setAttribute("aria-disabled", "false");
    // When the setup panel stacks above the results, bring the result into view.
    if (STACKED.matches) $("strip").scrollIntoView({ block: "start" });
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setBusy(false);
  }
}

function onTabKey(ev) {
  const enabled = TABS.filter((t) => t !== "checks" || state.run);
  const at = enabled.indexOf(state.tab);
  let next = null;
  if (ev.key === "ArrowRight") next = at + 1;
  else if (ev.key === "ArrowLeft") next = at - 1;
  else if (ev.key === "Home") next = 0;
  else if (ev.key === "End") next = enabled.length - 1;
  if (next == null) return;
  ev.preventDefault();
  const name = enabled[(next + enabled.length) % enabled.length];
  showTab(name);
  $("tab-" + name).focus();
}

function onListKey(ev) {
  const rows = [...$("check-list").querySelectorAll(".result-row")];
  const at = rows.findIndex((r) => r === document.activeElement);
  if (at < 0) return;
  let next = null;
  if (ev.key === "ArrowDown") next = Math.min(rows.length - 1, at + 1);
  else if (ev.key === "ArrowUp") next = Math.max(0, at - 1);
  else if (ev.key === "Home") next = 0;
  else if (ev.key === "End") next = rows.length - 1;
  if (next == null) return;
  ev.preventDefault();
  selectCheck(rows[next].dataset.check, true);
  rows[next].focus({ preventScroll: false });
}

async function start() {
  const params = new URLSearchParams(location.search);
  try {
    const data = await api("/api/packs");
    state.packs = data.packs;
    state.subjects = data.subjects;
  } catch (error) {
    setStatus(error.message, true);
    return;
  }
  for (const p of state.packs) {
    $("pack").append(el("option", { value: p.name, text: scenarioName(p) }));
  }
  const bots = state.subjects.filter((s) => s === "naive_bot" || s === "careful_bot");
  const others = state.subjects.filter((s) => !bots.includes(s));
  for (const s of bots) $("subject").append(el("option", { value: s, text: botName(s) }));
  const group = el("optgroup", { label: "Reference bots (known flaws)" });
  for (const s of others) group.append(el("option", { value: s, text: botName(s) }));
  $("subject").append(group);
  if (state.packs.some((p) => p.name === params.get("pack"))) $("pack").value = params.get("pack");
  if (state.subjects.includes(params.get("subject"))) $("subject").value = params.get("subject");
  renderBotCard(false);

  $("controls").addEventListener("submit", (ev) => { ev.preventDefault(); if (!state.busy && !state.matrixBusy) doRun(); });
  $("pack").addEventListener("change", () => { loadPack($("pack").value).catch((e) => setStatus(e.message, true)); });
  $("subject").addEventListener("change", () => renderBotCard(true));
  $("place").addEventListener("change", () => { state.limit = PAGE; renderTimeline(false, null); });
  $("seg").addEventListener("click", (ev) => {
    const b = ev.target.closest("button");
    if (b) { state.filter = b.dataset.filter; state.limit = PAGE; renderTimeline(false, null); }
  });
  $("more").addEventListener("click", () => { const from = state.limit; state.limit += PAGE; renderTimeline(false, from); });
  $("check-list").addEventListener("click", (ev) => {
    const b = ev.target.closest(".result-row");
    if (b) selectCheck(b.dataset.check, true);
  });
  $("check-list").addEventListener("keydown", onListKey);
  $("tabs").addEventListener("click", (ev) => {
    const b = ev.target.closest("button");
    if (b && b.getAttribute("aria-disabled") !== "true") showTab(b.dataset.tab);
  });
  $("tabs").addEventListener("keydown", onTabKey);
  window.addEventListener("hashchange", () => showTab(location.hash.slice(1), true));
  window.addEventListener("resize", () => placeIndicator(false));
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => placeIndicator(false));

  $("run-controls").addEventListener("click", runControls);

  // Nothing runs on load: URL parameters only preselect the scenario and bot.
  showTab(location.hash.slice(1) || "checks", true);
  await loadPack($("pack").value).catch((e) => setStatus(e.message, true));
  placeIndicator(false);
  requestAnimationFrame(() => { state.ready = true; });
}

start();
