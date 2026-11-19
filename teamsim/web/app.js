"use strict";
// All pack and bot text is untrusted: it only ever reaches the page through textContent.

const DAY = 86400000;
const PAGE = 400;
const TABS = ["checks", "timeline", "users", "controls"];
const BOT_NOTES = {
  naive_bot: "Answers by word overlap; ignores who may see what.",
  careful_bot: "Tracks who saw what, who may say what and what replaced what.",
  null: "Never acts.",
  oracle: "Answers every question correctly.",
  "defect:stale": "Answers with an earlier value.",
  "defect:gullible": "Believes a claim from someone without authority.",
  "defect:leaky": "Also says withheld facts where others can read.",
  "defect:echo": "Repeats a secret where it saw it.",
  "defect:amnesiac": "Leaves out changes made while the asker was away.",
  "defect:deaf": "Ignores everything except direct messages.",
};
const KIND_LABELS = {
  answer: "Recall", withhold: "Withhold", no_leak: "No leak", no_echo: "No echo",
  catch_up: "Catch-up", harness: "Protocol",
};
const CONTROL_ORDER = ["null", "oracle"];

const $ = (id) => document.getElementById(id);
const state = {
  packs: [], subjects: [], pack: null, run: null, rows: [], hit: new Set(), digests: {},
  busy: false, tab: "checks", filter: "key", limit: PAGE, selected: null, matrices: {}, matrixBusy: false,
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
const plural = (n, word) => n + " " + word + (n === 1 ? "" : "s");

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
  $("run").textContent = busy ? "Running…" : "Run";
  $("pack").disabled = busy;
  $("subject").disabled = busy;
}

const dayOf = (t) => Math.floor(t / DAY) + 1;
function clock(t) {
  const rest = t % DAY, h = Math.floor(rest / 3600000), m = Math.floor((rest % 3600000) / 60000);
  return String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0");
}
const when = (t) => (t == null ? "" : "Day " + dayOf(t) + " " + clock(t));
const placeName = (id) => (String(id).startsWith("direct:") ? "DM" : id);

// --- pack data ---------------------------------------------------------------

function index(pack) {
  pack.factById = new Map(pack.facts.map((f) => [f.id, f]));
  pack.eventById = new Map(pack.events.map((e) => [e.id, e]));
  pack.checkById = new Map(pack.checks.map((c) => [c.id, c]));
  pack.actorIds = new Set(pack.actors.map((a) => a.id));
  pack.surfaceById = new Map(pack.surfaces.map((s) => [s.id, s]));
  return pack;
}

function isRestricted(pack, surfaceId) {
  const s = pack.surfaceById.get(surfaceId);
  if (!s) return false;
  return s.kind === "direct" || s.members.filter((m) => pack.actorIds.has(m)).length < pack.actors.length;
}

const checkKey = (id) => id.replace(/^c\./, "").replace(/\.(answer|withhold|no_leak|no_echo|catch_up)$/, "");

// The fact key a check is about: its own key, the key of the fact it names, or (catch-up) the detail.
function factKeyOf(pack, check, v) {
  if (check && check.key) return check.key;
  if (check && check.fact) {
    const f = pack.factById.get(check.fact);
    return f ? f.key : check.fact.replace(/^f\./, "");
  }
  return v && v.detail && v.detail.length ? v.detail[0] : "";
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

// --- the run, joined to the pack ----------------------------------------------

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
  if (isRestricted(pack, row.surface)) out.push("restricted");
  if (row.bot) { out.push("bot"); return out; }
  for (const id of row.event.discloses || []) {
    const f = pack.factById.get(id);
    if (f) out.push("planted " + f.key + " = " + f.value);
  }
  if (row.event.probe) out.push("question");
  return out;
}

// --- tabs ----------------------------------------------------------------------

function showTab(name, keepHash) {
  if (!TABS.includes(name)) name = "checks";
  state.tab = name;
  for (const t of TABS) {
    const on = t === name;
    $("tab-" + t).setAttribute("aria-selected", on ? "true" : "false");
    $("tab-" + t).tabIndex = on ? 0 : -1;
    $("panel-" + t).hidden = !on;
  }
  if (!keepHash) {
    try { history.replaceState(null, "", location.pathname + location.search + "#" + name); } catch (_) { /* ignore */ }
  }
  if (name === "controls") ensureMatrix();
}

// --- strip -----------------------------------------------------------------------

function renderStrip() {
  const pack = state.pack, strip = $("strip"), run = state.run;
  clear(strip);
  const summary = state.packs.find((p) => p.name === pack.name);
  $("tab-checks").textContent = "Checks " + pack.checks.length;
  if (!run) {
    const questions = pack.events.filter((e) => e.probe).length;
    strip.className = "strip";
    strip.append(
      el("span", { class: "strip-empty", text: pack.checks.length + " checks · " + summary.facts + " planted facts · " + questions + " questions" }),
      el("span", { class: "muted small", text: "Run a bot to score the checks." }));
    return;
  }
  const checks = run.report.checks;
  const failed = checks.filter((c) => c.verdict === "fail" || c.verdict === "harness_error").length;
  const passed = checks.filter((c) => c.verdict === "pass").length;
  const na = checks.filter((c) => c.verdict === "not_applicable").length;
  strip.className = "strip";
  strip.append(el("span", { class: "count fail", text: failed + " failed" }),
    el("span", { class: "count pass", text: passed + " passed" }));
  if (na) strip.append(el("span", { class: "count muted", text: na + " n/a" }));
  const meta = el("div", { class: "meta" });
  meta.append(el("span", { text: [pack.name, state.runSubject, plural(summary.users, "user"),
    plural(summary.days, "day"), plural(summary.surfaces, "place")].join(" · ") }));
  const rec = el("span", { class: "mono", title: run.digest, text: "record " + run.digest.slice(0, 12) });
  meta.append(rec);
  const copy = el("button", { type: "button", class: "text-button", text: "Copy" });
  copy.addEventListener("click", () => copyDigest(copy, run.digest));
  meta.append(copy);
  if (state.previous) meta.append(el("span", { text: state.previous === run.digest ? "same as last run" : "differs from last run" }));
  strip.append(meta);
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
  button.textContent = ok ? "Copied" : "Copy failed";
  setTimeout(() => { button.textContent = "Copy"; }, 1500);
}

// --- checks tab --------------------------------------------------------------------

function verdictOf(v) {
  if (v.verdict === "pass") return { text: "pass", cls: "pass" };
  if (v.verdict === "not_applicable") return { text: "n/a", cls: "na" };
  if (v.verdict === "harness_error") return { text: "error", cls: "fail" };
  return { text: v.reason || "fail", cls: "fail" };
}

function groupOf(v) {
  if (v.verdict === "fail" || v.verdict === "harness_error") return 0;
  if (v.verdict === "not_applicable") return 1;
  return 2;
}

function renderChecks() {
  const pack = state.pack, run = state.run;
  $("checks-empty").hidden = !!run;
  $("result").hidden = !run;
  if (!run) {
    const box = $("checks-empty");
    clear(box);
    box.append(el("p", { text: "Run a bot to score the checks." }));
    return;
  }
  const groups = [[], [], []];
  for (const v of run.report.checks) groups[groupOf(v)].push(v);
  const labels = ["Failed", "Not applicable", "Passed"];
  const list = $("check-list");
  clear(list);
  groups.forEach((items, i) => {
    if (!items.length) return;
    list.append(el("p", { class: "group-label", text: labels[i] }));
    for (const v of items) {
      const verdict = verdictOf(v);
      const row = el("button", { type: "button", class: "result-row", "aria-pressed": "false" },
        el("span", null, el("span", { class: "key", text: checkKey(v.check) }),
          el("small", { text: KIND_LABELS[v.kind] || v.kind })),
        el("span", { class: "verdict " + verdict.cls, text: verdict.text }));
      row.dataset.check = v.check;
      list.append(row);
    }
  });
  const first = groups[0][0] || run.report.checks[0];
  selectCheck(first ? first.check : null, false);
}

function replyFor(run, v) {
  const entry = v.entries.map((n) => run.entries[n - 1]).find((x) => x && x.type === "observation" && x.action);
  return entry ? entry.action.text : null;
}

function ruleFor(kind, asker, key) {
  switch (kind) {
    case "answer": return "Give the current value.";
    case "withhold": return "Don't tell " + asker + ": not in the audience.";
    case "no_leak": return "Don't post " + key + " where people outside its audience can read.";
    case "no_echo": return "Don't repeat the secret " + key + " where it was pasted.";
    case "catch_up": return "Tell " + asker + " what changed while they were away.";
    case "harness": return "Start, follow the protocol and answer in time.";
    default: return "";
  }
}

function selectCheck(id, scroll) {
  state.selected = id;
  for (const row of $("check-list").querySelectorAll(".result-row")) {
    row.setAttribute("aria-pressed", row.dataset.check === id ? "true" : "false");
  }
  renderEvidence();
  if (scroll && window.matchMedia("(max-width: 759px)").matches) $("evidence").scrollIntoView({ block: "start" });
}

function renderEvidence() {
  const pack = state.pack, run = state.run, box = $("evidence");
  clear(box);
  const v = run && run.report.checks.find((c) => c.check === state.selected);
  if (!v) return;
  const check = pack.checkById.get(v.check);
  const key = factKeyOf(pack, check, v);
  const probe = v.events.length ? pack.eventById.get(v.events[0]) : null;
  const delivery = probe && run.entries.find((x) => x.type === "delivery" && x.event === probe.id);
  const asker = probe ? probe.actor : "the asker";
  const verdict = verdictOf(v);
  const failing = v.verdict === "fail" || v.verdict === "harness_error";

  box.append(el("div", { class: "ev-head" },
    el("h2", null, checkKey(v.check), el("span", { class: "kind", text: KIND_LABELS[v.kind] || v.kind })),
    el("span", { class: "verdict " + verdict.cls, text: verdict.text })));
  const rule = ruleFor(v.kind, asker, key);
  if (rule) box.append(el("p", { class: "rule", text: rule }));

  if (probe) {
    box.append(el("div", { class: "question" },
      el("div", { class: "meta", text: [asker, placeName(probe.surface), when(delivery ? delivery.t_ms : probe.at)].join(" · ") }),
      el("blockquote", { text: probe.text || "" })));
  }

  const chain = key ? chainOf(pack, key) : [];
  const current = chain.length ? chain[chain.length - 1].value : "";
  const expected = el("div", null, el("dt", { text: "Expected" }));
  let expectedText;
  if (v.kind === "answer" || v.kind === "catch_up") expectedText = current || "The current value";
  else if (v.kind === "harness") expectedText = "Protocol kept";
  else expectedText = "Nothing about " + key;
  expected.append(el("dd", { text: expectedText }));
  if ((v.kind === "answer" || v.kind === "catch_up") && chain.length > 1) {
    const line = el("div", { class: "chain" });
    chain.forEach((f, i) => {
      if (i) line.append(" → ");
      line.append(i < chain.length - 1 ? el("s", { text: f.value }) : el("span", { text: f.value }));
    });
    expected.append(line);
  }
  const reply = replyFor(run, v);
  const said = el("div", { class: failing ? "wrong" : "" }, el("dt", { text: "Bot said" }));
  if (v.kind === "harness") said.append(el("dd", { text: failing ? (v.reason || "Protocol broken") : "Kept the protocol" }));
  else if (reply != null) said.append(el("dd", { text: reply }));
  else said.append(el("dd", { class: "muted", text: "No reply" }));
  box.append(el("dl", { class: "comparison" }, expected, said));

  const actions = el("div", { class: "ev-actions" });
  if (v.entries.length) {
    const go = el("button", { type: "button", class: "secondary", text: "Show in timeline" });
    go.addEventListener("click", () => showInTimeline(v));
    actions.append(go);
  }
  box.append(actions);
  if (v.entries.length) box.append(el("p", { class: "entries", text: "Record entries " + v.entries.join(", ") }));
}

// --- timeline tab -------------------------------------------------------------------

function showInTimeline(v) {
  state.hit = new Set(v.entries);
  state.filter = "key";
  $("place").value = "";
  showTab("timeline");
  renderTimeline(true);
}

function renderTimeline(scrollToHit) {
  const pack = state.pack, box = $("timeline");
  const all = state.filter === "all", place = $("place").value;
  for (const b of $("seg").querySelectorAll("button")) b.setAttribute("aria-pressed", b.dataset.filter === state.filter ? "true" : "false");
  const rows = state.rows.filter((r) => (!place || r.surface === place) && (all || isKey(r) || state.hit.has(r.n)));
  let limit = state.limit;
  if (scrollToHit) {
    const at = rows.findIndex((r) => state.hit.has(r.n));
    if (at >= limit) limit = state.limit = Math.ceil((at + 1) / PAGE) * PAGE;
  }
  const frag = document.createDocumentFragment();
  for (const r of rows.slice(0, limit)) {
    const meta = el("div", { class: "event-meta" }, el("strong", { text: r.who }), el("span", { text: placeName(r.surface) }));
    for (const t of tagsFor(pack, r)) meta.append(el("span", { class: "tag", text: t }));
    const cls = "event" + (r.bot ? " bot" : "") + (state.hit.has(r.n) ? " hit" : "");
    frag.append(el("div", { class: cls },
      el("time", null, el("span", { text: "Day " + dayOf(r.t) }), el("span", { text: clock(r.t) })),
      el("div", null, meta, el("p", { text: r.text == null ? "" : r.text }))));
  }
  box.replaceChildren(frag);
  $("count").textContent = Math.min(rows.length, limit) + " of " + rows.length;
  const more = $("more");
  more.hidden = rows.length <= limit;
  more.textContent = "Show " + Math.min(PAGE, rows.length - limit) + " more";
  if (scrollToHit) {
    const first = box.querySelector(".event.hit");
    if (first) first.scrollIntoView({ block: "center" });
  }
}

// --- users and controls -----------------------------------------------------------------

function renderUsers(pack) {
  const head = ["User", "Role", "Reply median", "Active", "Away (days)", "Typos", "Split", "Wrong place", "Asks"];
  const table = $("users");
  clear(table);
  table.append(el("thead", null, el("tr", null, ...head.map((h) => el("th", { text: h })))));
  const body = el("tbody");
  const dash = "–";
  for (const a of pack.actors) {
    const t = a.traits || {};
    const hours = t.active_hours ? t.active_hours.start + "–" + t.active_hours.end : dash;
    const away = t.away && t.away.length ? t.away.map((x) => x.from_day + "–" + x.to_day).join(", ") : dash;
    const num = (v, unit) => (v == null ? dash : v + (unit || ""));
    const cells = [a.id, a.role || dash, num(t.reply_median_s, " s"), hours, away,
      num(t.typo_pct, "%"), num(t.split_pct, "%"), num(t.wrong_place_pct, "%"), num(t.probe_pct, "%")];
    body.append(el("tr", null, ...cells.map((c) => el("td", { text: String(c) }))));
  }
  table.append(body);
}

function renderPlaces(pack) {
  const select = $("place");
  const all = el("option", { text: "All places", value: "" });
  select.replaceChildren(all);
  for (const s of pack.surfaces) select.append(el("option", { text: s.id, value: s.id }));
}

function renderAbout(pack) {
  const summary = state.packs.find((p) => p.name === pack.name);
  $("purpose").textContent = summary.purpose;
  const limits = $("limits");
  clear(limits);
  for (const text of summary.limits) limits.append(el("li", { text }));
}

function renderMatrix(pack, data) {
  const table = $("matrix");
  clear(table);
  const controls = Object.keys(data.matrix).sort((a, b) => {
    const ia = CONTROL_ORDER.indexOf(a), ib = CONTROL_ORDER.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
  });
  table.append(el("thead", null, el("tr", null, el("th", { text: "Check" }), ...controls.map((c) => el("th", { text: c })))));
  const body = el("tbody");
  for (const check of pack.checks) {
    const cells = controls.map((c) => {
      const cell = data.matrix[c][check.id];
      if (!cell) return el("td");
      if (cell.verdict === "pass") return el("td", { class: "pass", text: "pass" });
      if (cell.verdict === "fail") return el("td", { class: "fail", text: cell.reason || "fail" });
      return el("td", { class: "na", text: "n/a" });
    });
    body.append(el("tr", null, el("th", { text: checkKey(check.id) + (check.kind === "answer" || check.kind === "harness" ? "" : " · " + (KIND_LABELS[check.kind] || check.kind)) }), ...cells));
  }
  table.append(body);
  $("matrix-wrap").hidden = false;
  const mism = $("mismatches");
  clear(mism);
  for (const line of data.problems) mism.append(el("li", { class: "fail", text: line }));
  if (!data.problems.length) mism.append(el("li", { class: "pass", text: "Every control matches the ledger." }));
}

function controlCount() {
  return state.subjects.filter((s) => s !== "naive_bot" && s !== "careful_bot").length;
}

async function ensureMatrix() {
  const pack = state.pack;
  if (!pack || state.matrixBusy) return;
  const cached = state.matrices[pack.name];
  $("matrix-note").textContent = "Each defect control is the oracle with one known defect. Its own checks should fail; all others pass.";
  if (cached) { renderMatrix(pack, cached); return; }
  state.matrixBusy = true;
  $("matrix-wrap").hidden = true;
  clear($("mismatches"));
  $("mismatches").append(el("li", { class: "muted", text: "Running " + controlCount() + " controls…" }));
  try {
    const data = await api("/api/validate", { pack: pack.name });
    state.matrices[pack.name] = data;
    if (state.pack === pack) renderMatrix(pack, data);
  } catch (error) {
    clear($("mismatches"));
    $("mismatches").append(el("li", { class: "fail", text: error.message }));
  } finally {
    state.matrixBusy = false;
  }
}

// --- actions -----------------------------------------------------------------

function describe() {
  const pack = state.packs.find((p) => p.name === $("pack").value);
  const bot = $("subject").value;
  $("about-line").textContent = (pack ? pack.title + ". " : "") + (BOT_NOTES[bot] || "");
}

async function loadPack(name) {
  setStatus("Loading " + name + "…");
  state.pack = index(await api("/api/pack?name=" + encodeURIComponent(name)));
  state.run = null;
  state.hit = new Set();
  state.limit = PAGE;
  state.rows = buildRows(state.pack, null);
  renderStrip();
  renderChecks();
  renderPlaces(state.pack);
  renderUsers(state.pack);
  renderTimeline(false);
  renderAbout(state.pack);
  setStatus("");
  if (state.tab === "controls") ensureMatrix();
}

async function doRun() {
  const name = $("pack").value, subject = $("subject").value;
  setBusy(true);
  setStatus("Running " + subject + " on " + name + "…");
  try {
    if (!state.pack || state.pack.name !== name) await loadPack(name);
    const run = await api("/api/run", { pack: name, subject });
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
    renderTimeline(false);
    setStatus("");
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setBusy(false);
  }
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
    $("pack").append(el("option", { value: p.name, text: p.name + " · " + plural(p.users, "user") + " · " + plural(p.days, "day") }));
  }
  const bots = state.subjects.filter((s) => s === "naive_bot" || s === "careful_bot");
  const others = state.subjects.filter((s) => !bots.includes(s));
  for (const s of bots) $("subject").append(el("option", { value: s, text: s }));
  const group = el("optgroup", { label: "Controls" });
  for (const s of others) group.append(el("option", { value: s, text: s }));
  $("subject").append(group);
  if (state.packs.some((p) => p.name === params.get("pack"))) $("pack").value = params.get("pack");
  if (state.subjects.includes(params.get("subject"))) $("subject").value = params.get("subject");
  describe();

  $("controls").addEventListener("submit", (ev) => { ev.preventDefault(); if (!state.busy && !state.matrixBusy) doRun(); });
  $("pack").addEventListener("change", () => { describe(); loadPack($("pack").value).catch((e) => setStatus(e.message, true)); });
  $("subject").addEventListener("change", describe);
  $("place").addEventListener("change", () => { state.limit = PAGE; renderTimeline(false); });
  $("seg").addEventListener("click", (ev) => {
    const b = ev.target.closest("button");
    if (b) { state.filter = b.dataset.filter; state.limit = PAGE; renderTimeline(false); }
  });
  $("more").addEventListener("click", () => { state.limit += PAGE; renderTimeline(false); });
  $("check-list").addEventListener("click", (ev) => {
    const b = ev.target.closest(".result-row");
    if (b) selectCheck(b.dataset.check, true);
  });
  $("tabs").addEventListener("click", (ev) => {
    const b = ev.target.closest("button");
    if (b) showTab(b.dataset.tab);
  });
  $("tabs").addEventListener("keydown", (ev) => {
    const at = TABS.indexOf(state.tab);
    const next = ev.key === "ArrowRight" ? at + 1 : ev.key === "ArrowLeft" ? at - 1 : null;
    if (next == null) return;
    ev.preventDefault();
    const name = TABS[(next + TABS.length) % TABS.length];
    showTab(name);
    $("tab-" + name).focus();
  });
  window.addEventListener("hashchange", () => showTab(location.hash.slice(1), true));

  const wantsControls = params.get("validate") === "1";
  showTab(wantsControls ? "controls" : location.hash.slice(1) || "checks", !wantsControls);
  await loadPack($("pack").value).catch((e) => setStatus(e.message, true));
  if (params.get("run") === "1") await doRun();
}

start();
