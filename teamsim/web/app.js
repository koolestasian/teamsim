"use strict";
// All pack and bot text is untrusted: it only ever reaches the page through textContent.

const DAY = 86400000;
const KEY_STORE = "teamsim.onlyKey";
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
  "lantern-shelf": ["Lantern Shelf",
    "Six people and a crash-report bot plan and ship an e-reader app over eight weeks, with decisions that change along the way.",
    "Six people build an e-reader app over eight weeks."],
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
  "lantern-shelf": [
    "Every channel is public, so tests about who may see what don't apply.",
    "The chat is a fixed transcript written by hand; it is the same in every run.",
  ],
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
  const actor = state.pack && state.pack.actorById && state.pack.actorById.get(id);
  if (actor && actor.display) return String(actor.display);
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
  busy: false, tab: "checks", selected: null, matrices: {}, matrixBusy: false,
  catchKeys: {}, ready: false, card: null,
  items: [], itemsFor: null, ws: { surface: "", keyOnly: false, person: null }, profile: null, sheet: null,
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
  pack.actorById = new Map(pack.actors.map((a) => [a.id, a]));
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

// --- conversation tab: chat workspace ---------------------------------------------------------------
// People and bots get generated portraits; every name and avatar opens a profile card.

const SVGNS = "http://www.w3.org/2000/svg";
function svgEl(tag, attrs, ...kids) {
  const node = document.createElementNS(SVGNS, tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  for (const kid of kids) if (kid) node.append(kid);
  return node;
}

function hashOf(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) { h ^= text.charCodeAt(i); h = Math.imul(h, 16777619); }
  h ^= h >>> 15; h = Math.imul(h, 2246822519); h ^= h >>> 13;
  return h >>> 0;
}
const pick = (id, salt, n) => hashOf(id + "|" + salt) % n;

const AV_BG = ["#B9A0FF", "#8ED0FF", "#FF9C8C", "#FFD173", "#7FE0B8", "#F4A6D7", "#9FB4C7", "#C9D987"];
const AV_SKIN = ["#F1C7A5", "#E0A97F", "#C68B63", "#8D5A3C", "#5C3A26"];
const AV_HAIR = ["#1A1210", "#4A2C1B", "#8A5A2B", "#C9A15A", "#B33A2E"];
const AV_TOP = ["#E8A93A", "#4B6BFB", "#D6455D", "#2F9E7A", "#7A4FD1", "#EF7D3B", "#3C4A62", "#C25E9E"];
const AV_BOT = ["#2F9E7A", "#EF7D3B", "#7A4FD1", "#3C4A62"];
const BOT_UNDER_TEST = "#5865F2";
const HAIR_FRONT_A = "M78 104 C80 66 104 54 128 54 C152 54 176 66 178 104 C164 86 150 80 128 80 C106 80 92 86 78 104 Z";
const HAIR_FRONT_B = "M76 110 C74 64 104 50 132 52 C160 54 182 72 178 108 C170 90 150 78 120 84 C98 90 84 98 76 110 Z";

const isBotId = (id) => id === "subject" || id === "bot";
const canon = (id) => (isBotId(id) ? "subject" : id);
function kindOf(id) {
  if (isBotId(id)) return "subject";
  const actor = state.pack && state.pack.actorById.get(id);
  return actor && actor.role === "bot" ? "bot" : "person";
}

// Each portrait is built once as a <symbol>; avatars reference it.
function symbolFor(id, kind) {
  const key = "av-" + kind + "-" + hashOf(id).toString(36);
  let sprite = $("sprite");
  if (!sprite) {
    sprite = svgEl("svg", { id: "sprite", width: 0, height: 0, "aria-hidden": "true", focusable: "false" });
    sprite.classList.add("sprite");
    document.body.append(sprite);
  }
  if (sprite.querySelector("#" + key)) return key;
  const sym = svgEl("symbol", { id: key, viewBox: "0 0 256 256" });
  if (kind === "person") {
    const bg = AV_BG[pick(id, "bg", 8)], skin = AV_SKIN[pick(id, "skin", 5)], hair = AV_HAIR[pick(id, "hair", 5)];
    const top = AV_TOP[pick(id, "top", 8)], style = pick(id, "style", 4);
    sym.append(svgEl("rect", { width: 256, height: 256, fill: bg }));
    if (style === 1) sym.append(svgEl("path", { d: "M70 100 C66 170 62 200 76 232 L180 232 C194 200 190 170 186 100 Z", fill: hair }));
    if (style === 2) sym.append(svgEl("circle", { cx: 128, cy: 44, r: 42, fill: hair }));
    if (style === 3) sym.append(svgEl("circle", { cx: 128, cy: 36, r: 24, fill: hair }));
    sym.append(
      svgEl("path", { d: "M28 256 C30 206 70 184 128 184 C186 184 226 206 228 256 Z", fill: top }),
      svgEl("rect", { x: 112, y: 150, width: 32, height: 40, rx: 12, fill: skin }),
      svgEl("rect", { x: 112, y: 150, width: 32, height: 40, rx: 12, fill: "#000", "fill-opacity": ".12" }),
      svgEl("ellipse", { cx: 128, cy: 116, rx: 50, ry: 58, fill: skin }),
      svgEl("path", { d: style % 2 ? HAIR_FRONT_B : HAIR_FRONT_A, fill: hair }),
      svgEl("ellipse", { cx: 108, cy: 124, rx: 5.5, ry: 6.5, fill: "#160F0C" }),
      svgEl("ellipse", { cx: 148, cy: 124, rx: 5.5, ry: 6.5, fill: "#160F0C" }),
      svgEl("path", { d: "M114 148 Q128 158 142 148", fill: "none", stroke: "#2C140C", "stroke-width": 5, "stroke-linecap": "round" }));
  } else {
    const bg = kind === "subject" ? BOT_UNDER_TEST : AV_BOT[pick(id, "bg", 4)];
    sym.append(
      svgEl("rect", { width: 256, height: 256, fill: bg }),
      svgEl("rect", { x: 127, y: 46, width: 2, height: 36, fill: "#F2F3F5" }),
      svgEl("circle", { cx: 128, cy: 44, r: 11, fill: "#F2F3F5" }),
      svgEl("rect", { x: 36, y: 122, width: 20, height: 44, rx: 8, fill: "#F2F3F5", "fill-opacity": ".75" }),
      svgEl("rect", { x: 200, y: 122, width: 20, height: 44, rx: 8, fill: "#F2F3F5", "fill-opacity": ".75" }),
      svgEl("rect", { x: 56, y: 80, width: 144, height: 126, rx: 36, fill: "#F2F3F5" }),
      svgEl("rect", { x: 86, y: 120, width: 24, height: 30, rx: 9, fill: "#23262E" }),
      svgEl("rect", { x: 146, y: 120, width: 24, height: 30, rx: 9, fill: "#23262E" }),
      svgEl("rect", { x: 102, y: 170, width: 52, height: 9, rx: 4.5, fill: "#23262E" }));
  }
  sprite.append(sym);
  return key;
}

function avatar(id, size) {
  const kind = kindOf(id);
  const svg = svgEl("svg", { class: "av " + kind, width: size, height: size, viewBox: "0 0 256 256", "aria-hidden": "true", focusable: "false" },
    svgEl("use", { href: "#" + symbolFor(canon(id), kind) }));
  return svg;
}

const nameClass = (id) => (isBotId(id) ? "nc-bot" : "nc" + pick(id, "nc", 8));
function botLabel() { return botName(state.runSubject || $("subject").value); }
function who(id) { return isBotId(id) ? botLabel() : person(id); }
const hasBotTag = (id) => kindOf(id) !== "person";

// --- items: the run's rows folded into what a chat shows -----------------------------------------------

const FOLDED = new Set(["edit", "delete", "react"]);

function buildItems(pack, rows) {
  const items = [], byEvent = new Map();
  for (const r of rows) {
    const e = r.event;
    if (e && FOLDED.has(e.kind)) {
      const target = byEvent.get(e.target);
      if (target) {
        if (r.n != null) target.ns.add(r.n);
        if (e.kind === "edit") {
          if (target.orig == null) target.orig = target.text;
          target.text = r.text == null ? "" : r.text;
          target.edited = true;
          for (const tag of tagsFor(pack, r)) if (tag !== "Edited" && !target.tags.includes(tag)) target.tags.push(tag);
          if (isKey(r)) target.key = true;
        } else if (e.kind === "delete") target.deleted = r.t;
        else target.reacts.set(e.emoji || "", (target.reacts.get(e.emoji || "") || 0) + 1);
        continue;
      }
      items.push({ kind: "sys", ev: e.kind, who: r.who, surface: r.surface, t: r.t, key: isKey(r), ns: new Set(r.n != null ? [r.n] : []), loose: true });
      continue;
    }
    const ns = new Set(r.n != null ? [r.n] : []);
    if (r.bot || (e && e.kind === "post")) {
      const it = { kind: "msg", who: r.who, surface: r.surface, t: r.t, text: r.text == null ? "" : r.text, bot: !!r.bot, tags: tagsFor(pack, r),
        key: isKey(r), ns, reacts: new Map(), edited: false, orig: null, deleted: null };
      items.push(it);
      if (e) byEvent.set(e.id, it);
    } else {
      items.push({ kind: "sys", ev: e ? e.kind : "event", op: e && e.op, who: r.who, surface: r.surface, t: r.t, key: isKey(r), ns });
    }
  }
  return items;
}

function itemsNow() {
  if (state.itemsFor !== state.rows) { state.items = buildItems(state.pack, state.rows); state.itemsFor = state.rows; }
  return state.items;
}

const REACTION = { "+1": "👍", "-1": "👎" };
const SYS_ICON = { away: "◐", back: "●", join: "→", leave: "←", subject_join: "→", subject_leave: "←", subject_down: "○", subject_up: "●", op: "▸", edit: "✎", delete: "✕", react: "☺" };

function sysText(it) {
  const k = it.ev;
  switch (k) {
    case "away": return "went away";
    case "back": return "is back";
    case "join": case "subject_join": return "joined " + place(it.surface);
    case "leave": case "subject_leave": return "left " + place(it.surface);
    case "subject_down": return "went offline";
    case "subject_up": return "is back online";
    case "op": return "Used the product" + (it.op ? ": " + it.op : "");
    case "edit": return "edited a message";
    case "delete": return "deleted a message";
    case "react": return "reacted to a message";
    default: return humanize(k);
  }
}

// --- text with mention and channel pills -------------------------------------------------------------------

function actorForMention(token) {
  const pack = state.pack, low = token.toLowerCase();
  for (const a of pack.actors) if (a.id.toLowerCase() === low || (a.display && String(a.display).toLowerCase() === low)) return a.id;
  return null;
}
function richText(text) {
  const frag = document.createDocumentFragment();
  for (const part of String(text).split(/(@[\w.]+|#[a-z][\w-]*)/g)) {
    if (/^@[\w.]+$/.test(part)) {
      const id = actorForMention(part.slice(1));
      if (id) { const b = el("button", { type: "button", class: "pill", "data-actor": id, text: part }); frag.append(b); }
      else frag.append(el("span", { class: "pill", text: part }));
    } else if (/^#[a-z][\w-]*$/.test(part)) {
      if (state.pack.surfaceById.has(part.slice(1))) frag.append(el("button", { type: "button", class: "pill", "data-surface": part.slice(1), text: part }));
      else frag.append(el("span", { class: "pill", text: part }));
    } else if (part) frag.append(document.createTextNode(part));
  }
  return frag;
}

// --- the three columns -------------------------------------------------------------------------------------------

function surfaceLabel(id) { return id ? place(id) : "All channels"; }

function renderChannels() {
  const pack = state.pack, items = itemsNow();
  const summary = state.packs.find((p) => p.name === pack.name);
  $("ws-scn").textContent = summary ? scenarioName(summary) : pack.name;
  const counts = new Map();
  for (const it of items) counts.set(it.surface, (counts.get(it.surface) || 0) + 1);
  const nav = $("ws-chlist");
  clear(nav);
  const row = (id, label, count, extra) => {
    const b = el("button", { type: "button", class: "ch", "aria-pressed": state.ws.surface === id ? "true" : "false" });
    b.dataset.surface = id;
    if (extra) b.append(extra);
    b.append(el("span", { class: "ch-name", text: label }), el("span", { class: "ch-count", text: String(count) }));
    return b;
  };
  nav.append(row("", "All channels", items.length, el("span", { class: "ch-hash", "aria-hidden": "true", text: "◎" })));
  const channels = pack.surfaces.filter((s) => s.kind !== "direct"), directs = pack.surfaces.filter((s) => s.kind === "direct");
  for (const s of channels) nav.append(row(s.id, s.id, counts.get(s.id) || 0, el("span", { class: "ch-hash", "aria-hidden": "true", text: "#" })));
  if (directs.length) {
    nav.append(el("p", { class: "ws-group", text: "Direct messages" }));
    for (const s of directs) {
      const other = s.members.find((m) => !isBotId(m)) || s.id.slice(7);
      const b = row(s.id, person(other), counts.get(s.id) || 0, avatar(other, 24));
      nav.append(b);
    }
  }
}

function membersOf(surfaceId) {
  const pack = state.pack;
  if (!surfaceId) return pack.actors.map((a) => a.id).concat(["subject"]);
  const s = pack.surfaceById.get(surfaceId);
  const ids = s.members.map(canon);
  return [...new Set(ids)].filter((id) => id === "subject" || pack.actorIds.has(id));
}

function renderMembers() {
  const pack = state.pack, box = $("ws-memlist");
  clear(box);
  const ids = membersOf(state.ws.surface);
  const groups = new Map();
  for (const id of ids) {
    const actor = pack.actorById.get(id);
    let g;
    if (id === "subject" || (actor && actor.role === "bot")) g = "Bot";
    else if (actor && actor.role) g = cap(actor.role);
    else g = "Members";
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(id);
  }
  const hasRoles = pack.actors.some((a) => a.role && a.role !== "bot");
  const rank = (g) => (g === "Lead" ? 0 : g === "Member" ? 1 : g === "Bot" ? 99 : 2);
  for (const g of [...groups.keys()].sort((a, b) => rank(a) - rank(b))) {
    const list = groups.get(g);
    box.append(el("p", { class: "ws-group", text: (hasRoles || g === "Bot" ? g : "Members") + " — " + list.length }));
    for (const id of list) {
      const b = el("button", { type: "button", class: "mem", "data-actor": id }, avatar(id, 32),
        el("span", { class: "mem-name " + nameClass(id), text: who(id) }));
      if (hasBotTag(id)) b.append(el("span", { class: "bot-tag", text: "BOT" }));
      box.append(b);
    }
  }
}

function visibleItems() {
  const w = state.ws;
  const scoped = itemsNow().filter((it) => (!w.surface || it.surface === w.surface) && (!w.person || canon(it.who) === w.person));
  const shown = w.keyOnly ? scoped.filter((it) => it.key || [...it.ns].some((n) => state.hit.has(n))) : scoped;
  return { shown, total: itemsNow().filter((it) => !w.surface || it.surface === w.surface).length };
}

const GROUP_GAP = 7 * 60000;

function renderFeed(scrollToHit) {
  const pack = state.pack, feed = $("timeline"), w = state.ws;
  const { shown, total } = visibleItems();
  const all = !w.surface;
  const frag = document.createDocumentFragment();
  let prev = null, grp = null, day = null;
  const isHit = (it) => [...it.ns].some((n) => state.hit.has(n));
  for (const it of shown) {
    const d = it.t == null ? day : dayOf(it.t);
    if (it.t != null && d !== day) {
      day = d;
      frag.append(el("div", { class: "day", role: "separator" }, el("span", { text: "Day " + d })));
      prev = null; grp = null;
    }
    if (it.kind === "sys") {
      const row = el("div", { class: "sys" + (isHit(it) ? " hit" : "") }, el("span", { class: "sys-icon", "aria-hidden": "true", text: SYS_ICON[it.ev] || "•" }));
      const text = sysText(it);
      row.append(el("button", { type: "button", class: "name " + nameClass(it.who), "data-actor": canon(it.who), text: who(it.who) }),
        el("span", { text: " " + (it.ev === "op" ? text.charAt(0).toLowerCase() + text.slice(1) : text) }));
      if (all && pack.surfaceById.has(it.surface) && !["away", "back", "join", "leave", "subject_join", "subject_leave", "subject_down", "subject_up"].includes(it.ev)) row.append(el("span", { class: "chan", text: place(it.surface) }));
      if (it.t != null) row.append(el("time", { text: "Day " + dayOf(it.t) + " · " + clock(it.t) }));
      row.dataset.who = canon(it.who);
      frag.append(row);
      prev = null; grp = null;
      continue;
    }
    const cont = prev && prev.kind === "msg" && canon(prev.who) === canon(it.who) && prev.surface === it.surface && it.t != null && prev.t != null && it.t - prev.t <= GROUP_GAP && it.t >= prev.t;
    const accent = it.tags.includes("Question for the bot") ? " ask" : it.tags.some((t) => t.startsWith("Secret") || t.includes("private to")) ? " priv" : it.tags.some((t) => t.startsWith("Update")) ? " upd" : "";
    const cls = "msg" + (it.bot ? " bot" : "") + (it.key ? " key" + accent : "") + (isHit(it) ? " hit" : "") + (it.deleted != null ? " gone" : "") + (cont ? " cont" : "");
    const body = el("div", { class: "mbody" });
    const when = it.t == null ? null : "Day " + dayOf(it.t) + " · " + clock(it.t);
    if (!cont) {
      const meta = el("div", { class: "meta" }, el("button", { type: "button", class: "name " + nameClass(it.who), "data-actor": canon(it.who), text: who(it.who) }));
      if (hasBotTag(it.who)) meta.append(el("span", { class: "bot-tag", text: "BOT" }));
      meta.append(el("time", { class: "stamp", text: when == null ? "—" : when, title: when == null ? "Sent in response to an earlier message; the time is set when the test runs." : "" }));
      if (all) meta.append(el("span", { class: "chan", text: place(it.surface) }));
      body.append(meta);
    }
    const text = el("div", { class: "mtext" }, richText(it.text));
    if (it.edited) {
      const toggle = el("button", { type: "button", class: "edited", "aria-expanded": "false", text: "(edited)" });
      text.append(" ", toggle);
    }
    body.append(text);
    if (it.edited) {
      const orig = el("div", { class: "orig", hidden: "" }, el("span", { text: "Original: " }), document.createTextNode(it.orig == null ? "" : it.orig));
      body.append(orig);
    }
    if (it.deleted != null) body.append(el("div", { class: "gone-note", text: "Deleted on Day " + dayOf(it.deleted) }));
    if (it.reacts.size) {
      const rs = el("div", { class: "reacts" });
      for (const [emoji, n] of it.reacts) {
        const label = emoji ? (REACTION[emoji] || emoji) : "";
        const pill = el("span", { class: "react", title: emoji ? "" : "Reaction" });
        if (label) pill.append(el("span", { text: label })); else pill.append(el("span", { class: "react-icon", "aria-hidden": "true", text: "☺" }));
        pill.append(el("span", { class: "react-n", text: String(n) }));
        rs.append(pill);
      }
      body.append(rs);
    }
    if (it.key && it.tags.length) {
      const tags = el("div", { class: "tags" });
      for (const t of it.tags) tags.append(el("span", { class: "tag" + (t === "Question for the bot" ? " ask" : ""), text: t }));
      body.append(tags);
    }
    const msg = el("div", { class: cls });
    msg.dataset.who = canon(it.who);
    if (cont) msg.append(el("time", { class: "hover-time", text: it.t == null ? "" : clock(it.t) }));
    else msg.append(el("button", { type: "button", class: "av-btn", "data-actor": canon(it.who), "aria-label": "Profile of " + who(it.who) }, avatar(it.who, 40)));
    msg.append(body);
    if (!cont) { grp = el("div", { class: "grp" }, msg); frag.append(grp); } else grp.append(msg);
    prev = it;
  }
  feed.replaceChildren(frag);
  if (!shown.length) feed.append(el("p", { class: "empty", text: w.keyOnly ? "No key messages here." : "No messages here." }));

  const unit = itemsNow().some((it) => it.kind === "msg") ? "messages" : "actions";
  $("count").textContent = (shown.length === total ? String(total) : shown.length + " of " + total) + " " + unit;
  renderHead();
  if (scrollToHit) {
    const first = feed.querySelector(".hit");
    if (first) {
      const top = first.getBoundingClientRect().top - feed.getBoundingClientRect().top + feed.scrollTop;
      feed.scrollTop = Math.max(0, top - feed.clientHeight / 3);
      first.classList.add("pulse");
      setTimeout(() => first.classList.remove("pulse"), 1100);
      $("ws").scrollIntoView({ block: "start", behavior: reduced() ? "auto" : "smooth" });
    }
  } else feed.scrollTop = 0;
}

function renderHead() {
  const w = state.ws, label = surfaceLabel(w.surface);
  $("ws-title").textContent = label;
  $("ws-chbtn").textContent = label + " ▾";
  $("key-only").checked = w.keyOnly;
  const chips = $("ws-chips");
  clear(chips);
  if (w.person) {
    const b = el("button", { type: "button", class: "chip-person", "aria-label": "Remove filter: from " + who(w.person) }, el("span", { text: "From " + who(w.person) }), el("span", { class: "x", "aria-hidden": "true", text: "×" }));
    b.addEventListener("click", () => { w.person = null; renderFeed(false); $("key-only").focus(); });
    chips.append(b);
  }
}

function renderWorkspace(scrollToHit) {
  renderChannels();
  renderMembers();
  renderFeed(scrollToHit);
}

function selectSurface(id) {
  state.ws.surface = id;
  renderChannels();
  renderMembers();
  renderFeed(false);
  closeSheets(true);
}

function showInTimeline(v) {
  state.hit = new Set(v.entries);
  state.ws.surface = "";
  state.ws.person = null;
  closeCard(false);
  showTab("timeline");
  renderWorkspace(true);
}

// --- sheets: channel list and member list on narrow screens ---------------------------------------------------------

function openSheet(name, opener) {
  closeCard(false);
  closeSheets(false);
  const box = $(name === "channels" ? "ws-channels" : "ws-members");
  box.classList.add("open");
  $("scrim").hidden = false;
  state.sheet = { name, opener };
  const first = box.querySelector("button");
  if (first) first.focus();
}
function closeSheets(restore) {
  const s = state.sheet;
  $("ws-channels").classList.remove("open");
  $("ws-members").classList.remove("open");
  if (!state.profile) $("scrim").hidden = true;
  state.sheet = null;
  if (s && restore && s.opener && s.opener.isConnected) s.opener.focus();
}

// --- profile card ---------------------------------------------------------------------------------------------------------

const PHONE = window.matchMedia("(max-width: 759px)");

// Habits and traits in words, the same wording for the People tab and the card.
function traitFacts(a) {
  const t = a.traits || {};
  const out = [];
  const hour = (h) => (Number.isInteger(h) ? h + ":00" : String(h));
  if (t.reply_median_s != null) out.push(["Typical reply", t.reply_median_s >= 90 ? Math.round(t.reply_median_s / 60) + " min" : t.reply_median_s + " s"]);
  if (t.active_hours) out.push(["Online", hour(t.active_hours.start) + "–" + hour(t.active_hours.end)]);
  if (t.away && t.away.length) out.push(["Away", "Days " + t.away.map((x) => x.from_day + "–" + x.to_day).join(", ")]);
  if (t.typo_pct != null) out.push(["Typos", t.typo_pct + "%"]);
  if (t.split_pct != null) out.push(["Splits messages", t.split_pct + "%"]);
  if (t.wrong_place_pct != null) out.push(["Wrong channel", t.wrong_place_pct + "%"]);
  if (t.probe_pct != null) out.push(["Asks the bot", t.probe_pct + "%"]);
  return out;
}

function activityOf(id) {
  const pack = state.pack, items = itemsNow().filter((it) => canon(it.who) === id);
  const msgs = items.filter((it) => it.kind === "msg");
  const places = [...new Set(items.filter((it) => it.kind === "msg" || it.ev === "op").map((it) => it.surface))];
  const times = items.map((it) => it.t).filter((t) => t != null);
  const facts = new Set();
  for (const r of state.rows) {
    if (canon(r.who) === id && r.event && r.event.discloses) for (const f of r.event.discloses) { const fact = pack.factById.get(f); if (fact) facts.add(topic(fact.key)); }
  }
  return { sent: msgs.length, ops: items.filter((it) => it.ev === "op").length, places, first: times.length ? dayOf(Math.min(...times)) : null, last: times.length ? dayOf(Math.max(...times)) : null, facts: [...facts] };
}

function buildCard(id) {
  const pack = state.pack, card = $("profile");
  const actor = pack.actorById.get(id), kind = kindOf(id);
  clear(card);
  const head = el("div", { class: "pc-head" }, avatar(id, 64));
  const names = el("div", { class: "pc-names" }, el("h2", { class: "pc-name " + nameClass(id), id: "pc-title", text: who(id) }));
  if (kind !== "subject") names.append(el("p", { class: "pc-id", text: "@" + id }));
  const tagsRow = el("div", { class: "pc-tags" });
  if (actor && actor.role && actor.role !== "bot") tagsRow.append(el("span", { class: "pc-tag", text: cap(actor.role) }));
  tagsRow.append(el("span", { class: "pc-tag", text: kind === "person" ? "Synthetic user" : "Bot" }));
  names.append(tagsRow);
  const close = el("button", { type: "button", class: "pc-close", "aria-label": "Close profile", text: "×" });
  close.addEventListener("click", () => closeCard(true));
  card.append(el("div", { class: "pc-top" }, head, names, close));
  const habits = actor ? traitFacts(actor) : [];
  if (habits.length) {
    const dl = el("dl", { class: "pc-list" });
    for (const [k, v] of habits) dl.append(el("div", null, el("dt", { text: k }), el("dd", { text: v })));
    card.append(el("h3", { class: "pc-sub", text: "Habits" }), dl);
  }
  const act = activityOf(id);
  const dl = el("dl", { class: "pc-list" });
  if (act.sent || !act.ops) dl.append(el("div", null, el("dt", { text: "Messages sent" }), el("dd", { text: String(act.sent) })));
  if (act.ops) dl.append(el("div", null, el("dt", { text: "Product actions" }), el("dd", { text: String(act.ops) })));
  if (act.places.length) dl.append(el("div", null, el("dt", { text: "Places" }), el("dd", { text: act.places.map(place).join(", ") })));
  if (act.first != null) dl.append(el("div", null, el("dt", { text: "Active" }), el("dd", { text: act.first === act.last ? "Day " + act.first : "Day " + act.first + " to Day " + act.last })));
  if (act.facts.length) dl.append(el("div", null, el("dt", { text: "Facts disclosed" }), el("dd", { text: act.facts.length + ": " + act.facts.join(", ") })));
  card.append(el("h3", { class: "pc-sub", text: "Activity" }), dl);
  const only = el("button", { type: "button", class: "secondary pc-only", text: "Show only their messages" });
  only.addEventListener("click", () => {
    state.ws.person = id;
    closeCard(false);
    showTab("timeline");
    renderFeed(false);
    $("ws-chips").querySelector("button")?.focus();
  });
  card.append(only);
  card.setAttribute("aria-labelledby", "pc-title");
}

function placeCard(opener) {
  const card = $("profile");
  if (PHONE.matches) { card.style.left = ""; card.style.top = ""; return; }
  const r = opener.getBoundingClientRect(), w = card.offsetWidth, h = card.offsetHeight;
  const left = Math.min(Math.max(8, r.left), window.innerWidth - w - 8);
  let top = r.bottom + 6;
  if (top + h > window.innerHeight - 8) top = Math.max(8, r.top - h - 6);
  card.style.left = left + "px";
  card.style.top = top + "px";
}

function openCard(id, opener) {
  if (!state.pack || (!isBotId(id) && !state.pack.actorIds.has(id))) return;
  const sheet = state.sheet;
  closeSheets(false);
  buildCard(id);
  const card = $("profile");
  card.hidden = false;
  if (PHONE.matches) $("scrim").hidden = false;
  placeCard(opener);
  state.profile = { id, opener, sheet };
  card.focus();
}

function closeCard(restore) {
  const p = state.profile;
  if (!p) return;
  $("profile").hidden = true;
  state.profile = null;
  if (!state.sheet) $("scrim").hidden = true;
  if (restore) {
    const o = p.opener;
    if (o && o.isConnected && o.getClientRects().length) o.focus();
    else if (p.sheet) $("ws-membtn").focus();
    else $("timeline").focus();
  }
}

// One click handler for every name, avatar and pill.
function onActorClick(ev) {
  const channel = ev.target.closest("[data-surface]");
  if (channel && channel.classList.contains("pill")) { selectSurface(channel.dataset.surface); return; }
  const b = ev.target.closest("[data-actor]");
  if (b && b.tagName === "BUTTON") { ev.preventDefault(); openCard(b.dataset.actor, b); }
}

// --- people and verification ----------------------------------------------------------------------------

function renderUsers(pack) {
  const head = ["Person", "Role", "Typical reply", "Online", "Away", "Typos", "Splits messages", "Wrong channel", "Asks the bot"];
  const table = $("users");
  clear(table);
  table.append(el("thead", null, el("tr", null, ...head.map((h) => el("th", { text: h })))));
  const body = el("tbody");
  const dash = "–";
  for (const a of pack.actors) {
    const facts = new Map(traitFacts(a));
    const cells = [a.role ? cap(a.role) : dash, ...["Typical reply", "Online", "Away", "Typos", "Splits messages", "Wrong channel", "Asks the bot"].map((k) => facts.get(k) || dash)];
    const name = el("button", { type: "button", class: "link-name", "data-actor": a.id }, avatar(a.id, 24), el("span", { text: person(a.id) }));
    body.append(el("tr", null, el("th", null, name), ...cells.map((c) => el("td", { text: String(c) }))));
  }
  table.append(body);
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
  state.ws.surface = "";
  state.ws.person = null;
  closeCard(false);
  closeSheets(false);
  state.rows = buildRows(state.pack, null);
  renderStrip();
  renderChecks();
  renderScenarioCard(animateCard);
  if (state.tab === "checks") showTab("timeline");
  else $("tab-checks").setAttribute("aria-disabled", "true");
  renderUsers(state.pack);
  renderWorkspace(false);
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
    state.rows = buildRows(state.pack, run);
    renderStrip();
    renderChecks();
    renderWorkspace(false);
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
  $("subject").addEventListener("change", () => { renderBotCard(true); if (state.pack) renderMembers(); });
  try { state.ws.keyOnly = localStorage.getItem(KEY_STORE) === "1"; } catch (_) { /* works without storage */ }
  $("key-only").checked = state.ws.keyOnly;
  $("key-only").addEventListener("change", () => {
    state.ws.keyOnly = $("key-only").checked;
    try { localStorage.setItem(KEY_STORE, state.ws.keyOnly ? "1" : "0"); } catch (_) { /* ignore */ }
    renderFeed(false);
  });
  $("ws-chlist").addEventListener("click", (ev) => {
    const b = ev.target.closest("button.ch");
    if (b) selectSurface(b.dataset.surface);
  });
  $("ws-chbtn").addEventListener("click", () => openSheet("channels", $("ws-chbtn")));
  $("ws-membtn").addEventListener("click", () => openSheet("members", $("ws-membtn")));
  $("scrim").addEventListener("pointerdown", () => { closeCard(true); closeSheets(true); });
  $("timeline").addEventListener("click", (ev) => {
    const b = ev.target.closest(".edited");
    if (!b) return;
    const orig = b.closest(".mbody").querySelector(".orig");
    orig.hidden = !orig.hidden;
    b.setAttribute("aria-expanded", orig.hidden ? "false" : "true");
  });
  $("timeline").addEventListener("scroll", () => closeCard(false), { passive: true });
  document.addEventListener("click", onActorClick);
  document.addEventListener("pointerdown", (ev) => {
    const p = state.profile;
    if (!p || $("profile").contains(ev.target) || (ev.target.closest && ev.target.closest("[data-actor]"))) return;
    closeCard(false);
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key !== "Escape") return;
    if (state.profile) { ev.preventDefault(); closeCard(true); }
    else if (state.sheet) { ev.preventDefault(); closeSheets(true); }
  });
  window.addEventListener("resize", () => { closeCard(false); });
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
