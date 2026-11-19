"use strict";
// All pack and bot text is untrusted: it only ever reaches the page through textContent.

const DAY = 86400000;
const SUBJECT_LABELS = {
  naive_bot: "naive_bot (remembers everything, answers by word overlap)",
  careful_bot: "careful_bot (tracks who saw what, who may say what, what replaced what)",
  null: "control: null (never acts)",
  oracle: "control: oracle (answers every question correctly)",
  "defect:stale": "defect:stale (answers with an earlier value)",
  "defect:gullible": "defect:gullible (believes a claim from someone without authority)",
  "defect:leaky": "defect:leaky (also says withheld facts where others can read)",
  "defect:echo": "defect:echo (repeats a secret where it saw it)",
  "defect:amnesiac": "defect:amnesiac (answers a catch-up question without the changes it missed)",
  "defect:deaf": "defect:deaf (ignores every place that is not a direct message)",
};
const CONTROL_ORDER = ["null", "oracle"];

const $ = (id) => document.getElementById(id);
const state = { packs: [], subjects: [], pack: null, run: null, hit: new Set(), digests: {}, busy: false };

function el(tag, props, ...kids) {
  const node = document.createElement(tag);
  if (props) for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v; else if (k === "text") node.textContent = v; else node.dataset[k] = v;
  }
  for (const kid of kids) if (kid != null) node.append(kid);
  return node;
}
const clear = (node) => node.replaceChildren();

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
  for (const id of ["run", "validate", "pack", "subject"]) $(id).disabled = busy;
}

const dayOf = (t) => Math.floor(t / DAY) + 1;
function when(t) {
  if (t == null) return "";
  const rest = t % DAY, h = Math.floor(rest / 3600000), m = Math.floor((rest % 3600000) / 60000);
  return "day " + dayOf(t) + " " + String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0");
}

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

function currentFact(pack, check) {
  if (check.fact) return pack.factById.get(check.fact) || null;
  const same = pack.facts.filter((f) => f.key === check.key && f.kind !== "claim");
  const replaced = new Set(same.map((f) => f.supersedes).filter(Boolean));
  return same.filter((f) => !replaced.has(f.id)).pop() || null;
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
      if (e) rows.push({ t: entry.t_ms, n: entry.n, event: e, surface: e.surface, who: e.actor, text: e.text, delivery: entry });
    } else if (entry.type === "observation" && entry.kind === "action" && entry.action) {
      rows.push({
        t: entry.t_ms, n: entry.n, bot: entry, surface: entry.action.surface, who: "bot",
        text: entry.action.text,
      });
    }
  }
  return rows;
}

function isKey(row) {
  if (row.bot) return true;
  const e = row.event;
  return !!(e.probe || (e.discloses && e.discloses.length) || e.kind === "away" || e.kind === "back");
}

function marks(pack, row) {
  const out = [];
  if (row.bot) {
    out.push("bot reply");
    const readers = row.bot.readers || [];
    out.push("readable by " + (readers.length <= 4 ? readers.join(", ") || "nobody" : readers.length + " users"));
    if (row.bot.action.reply_to) out.push("reply to " + row.bot.action.reply_to);
    return out;
  }
  const e = row.event;
  if (e.kind !== "post") out.push(e.kind);
  for (const id of e.discloses || []) {
    const f = pack.factById.get(id);
    if (f) out.push("fact planted: " + f.key + " = " + f.value);
  }
  if (e.probe) out.push("question to the bot");
  return out;
}

function renderTimeline() {
  const pack = state.pack, box = $("timeline");
  const all = $("filter").value === "all", place = $("place").value;
  const rows = state.rows.filter((r) => (!place || r.surface === place) && (all || isKey(r) || state.hit.has(r.n)));
  const frag = document.createDocumentFragment();
  for (const r of rows) {
    const cls = "row" + (r.bot ? " bot" : "") + (isRestricted(pack, r.surface) ? " restricted" : "")
      + (state.hit.has(r.n) ? " hit" : "");
    const text = el("div", { class: "text" });
    text.append(el("span", { text: r.text == null ? "" : r.text }));
    const m = marks(pack, r);
    if (m.length) text.append(el("div", { class: "marks" }, ...m.map((x) => el("span", { class: "mark", text: x }))));
    const node = el("div", { class: cls }, el("div", { class: "when", text: when(r.t) }),
      el("div", { class: "place", text: r.surface }), el("div", { class: "who", text: r.who }), text);
    if (r.n != null) node.dataset.n = r.n;
    frag.append(node);
  }
  box.replaceChildren(frag);
  $("count").textContent = rows.length + " of " + state.rows.length + " lines";
}

// --- sections ----------------------------------------------------------------

function renderUsers(pack) {
  const head = ["user", "role", "reply median", "active hours", "away days", "typo %", "split %", "wrong place %", "probe %"];
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
      num(t.typo_pct), num(t.split_pct), num(t.wrong_place_pct), num(t.probe_pct)];
    body.append(el("tr", null, ...cells.map((c) => el("td", { text: String(c) }))));
  }
  table.append(body);
  $("users-section").hidden = false;
}

function renderPlaces(pack) {
  const select = $("place");
  select.replaceChildren(el("option", { text: "all places" }));
  select.firstChild.value = "";
  for (const s of pack.surfaces) {
    const o = el("option", { text: s.id });
    o.value = s.id;
    select.append(o);
  }
}

function packStats(pack) {
  const changed = pack.facts.filter((f) => f.supersedes).length;
  const secret = pack.facts.filter((f) => f.kind === "secret").length;
  const priv = pack.facts.filter((f) => f.kind !== "secret" && !(f.audience.length === 1 && f.audience[0] === "*")).length;
  const questions = pack.events.filter((e) => e.probe).length;
  return { changed, secret, priv, questions };
}

function renderSummary(pack, summary, run) {
  const st = packStats(pack);
  const line = $("facts-line");
  clear(line);
  const item = (n, label) => line.append(el("li", null, el("b", { text: String(n) }), " " + label));
  item(summary.users, "users");
  item(summary.days, "virtual days");
  item(summary.surfaces, "places");
  item(pack.facts.length, "facts planted (" + st.changed + " later changed, " + st.priv + " private to a group, " + st.secret + " secret)");
  item(st.questions, "questions asked of the bot");
  if (run) {
    const checks = run.report.checks;
    const passed = checks.filter((c) => c.verdict === "pass").length;
    const failed = checks.filter((c) => c.verdict === "fail" || c.verdict === "harness_error").length;
    item(passed, "checks passed");
    item(failed, "checks failed");
  } else {
    item(summary.checks, "checks (run a bot to score them)");
  }
  $("purpose").textContent = summary.title + ". " + summary.purpose;
  const limits = $("limits");
  clear(limits);
  for (const text of summary.limits) limits.append(el("li", { text }));
  $("summary").hidden = false;
}

function renderDigest(run, previous) {
  const node = $("digest");
  if (!run) { node.textContent = ""; return; }
  let text = "Record digest " + run.digest + ".";
  if (previous) text += previous === run.digest
    ? " Same as the previous run of this pack and bot."
    : " Different from the previous run of this pack and bot.";
  node.textContent = text;
}

// One plain sentence per check, built from pack data and what the bot said.
function sentence(pack, run, v) {
  const check = pack.checkById.get(v.check);
  const probe = v.events.length ? pack.eventById.get(v.events[0]) : null;
  const delivery = probe && run.entries.find((x) => x.type === "delivery" && x.event === probe.id);
  const reply = v.entries.map((n) => run.entries[n - 1]).find((x) => x && x.type === "observation" && x.action);
  const said = reply ? "Bot replied “" + reply.action.text + "”" : "Bot did not reply";
  const asked = probe
    ? probe.actor + " asked “" + probe.text + "” in " + probe.surface + " on " + when(delivery ? delivery.t_ms : probe.at) + ". "
    : "";
  const result = ". Result: " + (v.verdict === "fail" ? v.reason : v.verdict.replace("_", " ")) + ".";
  const fact = check ? currentFact(pack, check) : null;
  switch (v.kind) {
    case "answer": {
      let value = "";
      if (fact) {
        const prev = fact.supersedes ? pack.factById.get(fact.supersedes) : null;
        value = "Current value: " + fact.value + (prev ? " (changed from " + prev.value + ")" : "") + ". ";
      }
      return asked + value + said + result;
    }
    case "withhold": {
      const who = probe ? probe.actor : "the asker";
      return asked + "The " + (fact ? fact.key : "fact") + " is not for " + who + ". " + said + result;
    }
    case "no_leak":
      return "No bot message readable by someone outside the audience of " + (fact ? fact.key : "the fact")
        + " may contain it. " + (reply ? said : "") + result;
    case "no_echo":
      return "The bot must not repeat the secret " + (fact ? fact.key : "") + " in a place where it was shared." + result;
    case "catch_up":
      return asked + "The bot must report what changed while " + (probe ? probe.actor : "the asker") + " was away. " + said + result;
    case "harness":
      return "The bot started, kept to the protocol and answered in time." + result;
    default:
      return v.kind + " check " + v.check + (v.detail.length ? " on " + v.detail.join(", ") : "") + "." + result;
  }
}

function renderChecks(pack, run) {
  const list = $("checks");
  clear(list);
  for (const v of run.report.checks) {
    const cls = v.verdict === "pass" ? "pass" : v.verdict === "not_applicable" ? "na" : "fail";
    const head = el("div", { class: "head" },
      el("span", { class: cls, text: v.verdict === "fail" ? "fail: " + v.reason : v.verdict.replace("_", " ") }),
      el("span", { class: "id", text: v.check }), el("span", { class: "kind", text: v.kind }),
      v.policy ? el("span", { class: "policy", text: "policy" }) : null);
    const li = el("li", { check: v.check }, head, el("p", { text: sentence(pack, run, v) }));
    list.append(li);
  }
  $("checks-section").hidden = false;
}

function renderMatrix(pack, data) {
  const table = $("matrix");
  clear(table);
  const controls = Object.keys(data.matrix).sort((a, b) => {
    const ia = CONTROL_ORDER.indexOf(a), ib = CONTROL_ORDER.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
  });
  table.append(el("thead", null, el("tr", null, el("th", { text: "check" }), ...controls.map((c) => el("th", { text: c })))));
  const body = el("tbody");
  for (const check of pack.checks) {
    const cells = controls.map((c) => {
      const cell = data.matrix[c][check.id];
      if (!cell) return el("td");
      if (cell.verdict === "pass") return el("td", { class: "pass", text: "pass" });
      if (cell.verdict === "fail") return el("td", { class: "fail", text: "fail: " + cell.reason });
      return el("td", { class: "na", text: cell.verdict.replace("_", " ") });
    });
    body.append(el("tr", null, el("th", { text: check.id }), ...cells));
  }
  table.append(body);
  $("matrix-note").textContent = "Each defect control is the oracle with one known defect. A cell shows whether that check catches it (fail) or not (pass).";
  const mism = $("mismatches");
  clear(mism);
  for (const line of data.problems) mism.append(el("li", { class: "fail", text: line }));
  if (!data.problems.length) mism.append(el("li", { class: "pass", text: "Every control got the verdict the ledger predicts." }));
  const info = data.lines.filter((x) => !data.problems.includes(x));
  for (const line of info) mism.append(el("li", { class: "na", text: line }));
  $("matrix-section").hidden = false;
}

// --- actions -----------------------------------------------------------------

async function loadPack(name) {
  setStatus("Loading " + name + "…");
  state.pack = index(await api("/api/pack?name=" + encodeURIComponent(name)));
  state.run = null;
  state.hit = new Set();
  state.rows = buildRows(state.pack, null);
  $("checks-section").hidden = true;
  $("matrix-section").hidden = true;
  const summary = state.packs.find((p) => p.name === name);
  renderSummary(state.pack, summary, null);
  renderDigest(null);
  renderPlaces(state.pack);
  renderUsers(state.pack);
  renderTimeline();
  $("timeline-section").hidden = false;
  setStatus("");
}

async function doRun() {
  const name = $("pack").value, subject = $("subject").value;
  setBusy(true);
  setStatus("Running " + subject + " on " + name + "…");
  try {
    if (!state.pack || state.pack.name !== name) await loadPack(name);
    const run = await api("/api/run", { pack: name, subject });
    const key = name + "|" + subject, previous = state.digests[key];
    state.digests[key] = run.digest;
    state.run = run;
    state.hit = new Set();
    state.rows = buildRows(state.pack, run);
    renderSummary(state.pack, state.packs.find((p) => p.name === name), run);
    renderDigest(run, previous);
    renderChecks(state.pack, run);
    renderTimeline();
    setStatus("");
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setBusy(false);
  }
}

async function doValidate() {
  const name = $("pack").value;
  setBusy(true);
  setStatus("Running every control bot on " + name + "…");
  try {
    if (!state.pack || state.pack.name !== name) await loadPack(name);
    renderMatrix(state.pack, await api("/api/validate", { pack: name }));
    setStatus("");
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setBusy(false);
  }
}

function pickCheck(id) {
  const v = state.run && state.run.report.checks.find((c) => c.check === id);
  if (!v) return;
  state.hit = new Set(v.entries);
  renderTimeline();
  const first = $("timeline").querySelector(".row.hit");
  if (first) first.scrollIntoView({ block: "center" });
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
  for (const p of state.packs) { const o = el("option", { text: p.name + " (" + p.users + " users, " + p.days + " days)" }); o.value = p.name; $("pack").append(o); }
  const bots = state.subjects.filter((s) => s === "naive_bot" || s === "careful_bot");
  const controls = state.subjects.filter((s) => !bots.includes(s));
  for (const s of bots.concat(controls)) { const o = el("option", { text: SUBJECT_LABELS[s] || s }); o.value = s; $("subject").append(o); }
  if (state.packs.some((p) => p.name === params.get("pack"))) $("pack").value = params.get("pack");
  if (state.subjects.includes(params.get("subject"))) $("subject").value = params.get("subject");

  $("controls").addEventListener("submit", (ev) => { ev.preventDefault(); if (!state.busy) doRun(); });
  $("validate").addEventListener("click", () => { if (!state.busy) doValidate(); });
  $("pack").addEventListener("change", () => loadPack($("pack").value).catch((e) => setStatus(e.message, true)));
  $("filter").addEventListener("change", renderTimeline);
  $("place").addEventListener("change", renderTimeline);
  $("checks").addEventListener("click", (ev) => {
    const li = ev.target.closest("li");
    if (li) pickCheck(li.dataset.check);
  });

  if (params.get("run") === "1") await doRun();
  else await loadPack($("pack").value).catch((e) => setStatus(e.message, true));
  if (params.get("validate") === "1") await doValidate();
}

start();
