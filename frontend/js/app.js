/* SmartDesk AI - vanilla JS single-page UI. All data comes from the FastAPI backend via fetch(). */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const view = $("#view");

/* ---------- helpers ---------- */
function esc(v) {  // escape everything that comes from the API before putting it in HTML
  return String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
async function api(path, opts = {}) {
  let res;
  try {
    res = await fetch(path, {
      headers: opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {},
      ...opts,
      body: opts.body && !(opts.body instanceof FormData) ? JSON.stringify(opts.body) : opts.body,
    });
  } catch (e) {
    throw new Error("Cannot reach the SmartDesk server. Is it running?");
  }
  let data = null;
  try { data = await res.json(); } catch (e) { /* non-JSON body */ }
  if (!res.ok) {
    let msg = data && data.detail;
    if (Array.isArray(msg)) msg = msg.map(d => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
    throw new Error(msg || `Request failed (${res.status})`);
  }
  return data;
}
function toast(msg, kind = "") {
  const t = document.createElement("div");
  t.className = `toast ${kind}`; t.textContent = msg;
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), 4500);
}
const loading = () => (view.innerHTML = '<div class="spinner" role="status" aria-label="Loading"></div>');
const showError = (e) => (view.innerHTML = `<div class="error-box">${esc(e.message)}</div>`);
const fmtDate = (s) => (s ? s.replace("T", " ").slice(0, 16) : "");
const PRIORITY_CLASS = { Critical: "b-critical", High: "b-high", Moderate: "b-moderate", Low: "b-low" };
const prioBadge = (label) => `<span class="badge ${PRIORITY_CLASS[label] || ""}">${esc(label)}</span>`;
const STATUS_CLASS = { New: "b-info", "In Progress": "b-warn", Resolved: "b-ok", Closed: "", Submitted: "b-info", Approved: "b-moderate", Fulfilled: "b-ok", Rejected: "b-bad" };
const statusBadge = (s) => `<span class="badge ${STATUS_CLASS[s] || ""}">${esc(s)}</span>`;
const IMPACT = { 1: "High", 2: "Medium", 3: "Low" };
const COLORS = ["#2563eb", "#0ea5e9", "#14b8a6", "#f59e0b", "#ef4444", "#8b5cf6"];
const PRIO_COLORS = { Critical: "#ef4444", High: "#f59e0b", Moderate: "#2563eb", Low: "#94a3b8" };

function bars(obj, colorFn) {
  const entries = Object.entries(obj), max = Math.max(1, ...entries.map(([, v]) => v));
  if (!entries.length) return '<div class="empty">No data yet</div>';
  return `<div class="bars">${entries.map(([k, v], i) =>
    `<div class="row"><span>${esc(k)}</span><div class="bar"><span style="width:${(v / max) * 100}%;background:${colorFn(k, i)}"></span></div><b>${v}</b></div>`).join("")}</div>`;
}
function donut(obj) {
  const entries = Object.entries(obj), total = entries.reduce((a, [, v]) => a + v, 0);
  if (!total) return '<div class="empty">No data yet</div>';
  const r = 42, c = 2 * Math.PI * r; let offset = 0;
  const arcs = entries.map(([, v], i) => {
    const len = (v / total) * c;
    const s = `<circle cx="60" cy="60" r="${r}" fill="none" stroke="${COLORS[i % COLORS.length]}" stroke-width="18" stroke-dasharray="${len} ${c - len}" stroke-dashoffset="${-offset}" transform="rotate(-90 60 60)"/>`;
    offset += len; return s;
  }).join("");
  return `<div class="donut-wrap"><svg width="120" height="120" viewBox="0 0 120 120" role="img" aria-label="Chart">${arcs}<text x="60" y="65" text-anchor="middle" font-size="20" font-weight="700" fill="#1b2437">${total}</text></svg>
    <div class="legend">${entries.map(([k, v], i) => `<div><span class="dot" style="background:${COLORS[i % COLORS.length]}"></span>${esc(k)} <b>${v}</b></div>`).join("")}</div></div>`;
}
function modal(html) {
  const root = $("#modalRoot");
  root.innerHTML = `<div class="modal-bg"><div class="modal">${html}</div></div>`;
  root.querySelector(".modal-bg").addEventListener("mousedown", (e) => { if (e.target.classList.contains("modal-bg")) closeModal(); });
  const x = root.querySelector(".x"); if (x) x.addEventListener("click", closeModal);
  return root.querySelector(".modal");
}
function closeModal() { $("#modalRoot").innerHTML = ""; }
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

/* ---------- router ---------- */
const PAGES = { dashboard: renderDashboard, incidents: renderIncidents, assistant: renderAssistant, requests: renderRequests, knowledge: renderKnowledge, settings: renderSettings };
const TITLES = { dashboard: "Dashboard", incidents: "Incident Management", assistant: "AI Knowledge Assistant", requests: "Service Requests", knowledge: "Knowledge Base", settings: "Settings & Integrations" };
async function route() {
  const page = (location.hash.replace("#/", "") || "dashboard").split("?")[0];
  const name = PAGES[page] ? page : "dashboard";
  document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("active", a.dataset.page === name));
  $("#pageTitle").textContent = TITLES[name];
  $("#sidebar").classList.remove("open");
  loading();
  try { await PAGES[name](); } catch (e) { showError(e); }
}
window.addEventListener("hashchange", route);
$("#menuBtn").addEventListener("click", () => $("#sidebar").classList.toggle("open"));

/* ---------- Dashboard ---------- */
async function renderDashboard() {
  const d = await api("/api/dashboard"), t = d.totals;
  const stat = (label, v) => `<div class="card stat"><div class="label">${label}</div><div class="value">${v}</div></div>`;
  view.innerHTML = `
    <div class="grid stats">
      ${stat("Total incidents", t.incidents)}${stat("Open incidents", t.open_incidents)}
      ${stat("Resolved incidents", t.resolved_incidents)}${stat("Pending requests", t.pending_requests)}
    </div>
    <div class="grid two" style="margin-top:16px">
      <div class="card"><h2>Incidents by priority</h2>${bars(d.priority_breakdown, (k) => PRIO_COLORS[k])}</div>
      <div class="card"><h2>Incidents by category</h2>${donut(d.category_breakdown)}</div>
      <div class="card"><h2>Incidents by status</h2>${bars(d.status_breakdown, (k, i) => COLORS[i % COLORS.length])}</div>
      <div class="card"><h2>Service requests by department</h2>${bars(d.requests_by_department, (k, i) => COLORS[i % COLORS.length])}</div>
    </div>
    <div class="card" style="margin-top:16px">
      <div class="card-head"><h2>Recent incidents</h2><a href="#/incidents">View all</a></div>
      ${incidentTable(d.recent_incidents)}
    </div>`;
  bindIncidentRows();
}

/* ---------- Incidents ---------- */
function incidentTable(list) {
  if (!list.length) return '<div class="empty">No incidents match. Create one with &ldquo;New incident&rdquo;.</div>';
  return `<div class="table-wrap"><table><thead><tr><th>Number</th><th>Description</th><th>Category</th><th>Priority</th><th>Status</th><th>Assigned to</th><th>Created</th></tr></thead><tbody>
    ${list.map(i => `<tr class="click" data-id="${i.id}"><td><b>${esc(i.number)}</b>${i.sn_number ? `<div class="small muted">SN: ${esc(i.sn_number)}</div>` : ""}</td>
      <td>${esc(i.short_description)}</td><td>${esc(i.category)}</td><td>${prioBadge(i.priority_label)}</td><td>${statusBadge(i.status)}</td>
      <td>${esc(i.assigned_to || "Unassigned")}</td><td class="muted">${fmtDate(i.created_at)}</td></tr>`).join("")}
    </tbody></table></div>`;
}
function bindIncidentRows() {
  view.querySelectorAll("tr.click").forEach(tr => tr.addEventListener("click", () => openIncident(tr.dataset.id)));
}
async function renderIncidents() {
  view.innerHTML = `
    <div class="card">
      <div class="toolbar">
        <input id="fq" type="search" placeholder="Search number or text&hellip;">
        <select id="fs"><option value="">All statuses</option><option>New</option><option>In Progress</option><option>Resolved</option><option>Closed</option></select>
        <select id="fc"><option value="">All categories</option><option>Network</option><option>Hardware</option><option>Software</option><option>Access</option><option>Other</option></select>
        <select id="fp"><option value="">All priorities</option><option value="1">Critical</option><option value="2">High</option><option value="3">Moderate</option><option value="4">Low</option></select>
        <button class="btn" id="newInc" style="margin-left:auto">+ New incident</button>
      </div>
      <div id="incList"><div class="spinner"></div></div>
    </div>`;
  const load = async () => {
    const p = new URLSearchParams();
    [["q", "#fq"], ["status", "#fs"], ["category", "#fc"], ["priority", "#fp"]].forEach(([k, s]) => { const v = $(s).value.trim(); if (v) p.set(k, v); });
    try { $("#incList").innerHTML = incidentTable(await api(`/api/incidents?${p}`)); bindIncidentRows(); }
    catch (e) { $("#incList").innerHTML = `<div class="error-box">${esc(e.message)}</div>`; }
  };
  let timer; $("#fq").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(load, 250); });
  ["#fs", "#fc", "#fp"].forEach(s => $(s).addEventListener("change", load));
  $("#newInc").addEventListener("click", () => newIncidentModal());
  await load();
}
function newIncidentModal(prefill = {}) {
  const m = modal(`
    <div class="modal-head"><h2>New incident</h2><button class="x" aria-label="Close">&times;</button></div>
    <p class="muted small">The AI summarises, categorises and suggests impact/urgency. Priority is then calculated by a fixed impact &times; urgency matrix.</p>
    <form id="incForm">
      <label>Short description</label><input name="short_description" required minlength="5" maxlength="200" value="${esc(prefill.short || "")}" placeholder="e.g. Cannot connect to VPN">
      <label>Detailed description</label><textarea name="description" required minlength="10" maxlength="5000" placeholder="What happened, since when, who is affected, error messages&hellip;">${esc(prefill.desc || "")}</textarea>
      <div class="form-row">
        <div><label>Impact</label><select name="impact"><option value="">Let AI suggest</option><option value="1">1 - High (many users)</option><option value="2">2 - Medium</option><option value="3">3 - Low (one user)</option></select></div>
        <div><label>Urgency</label><select name="urgency"><option value="">Let AI suggest</option><option value="1">1 - High (cannot work)</option><option value="2">2 - Medium</option><option value="3">3 - Low</option></select></div>
      </div>
      <div style="margin-top:16px;display:flex;gap:10px;justify-content:flex-end"><button type="button" class="btn secondary" id="cancel">Cancel</button><button class="btn" id="submitInc">Create &amp; analyse</button></div>
    </form>`);
  $("#cancel", m).addEventListener("click", closeModal);
  $("#incForm", m).addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target), body = { short_description: f.get("short_description"), description: f.get("description") };
    if (f.get("impact")) body.impact = +f.get("impact"); if (f.get("urgency")) body.urgency = +f.get("urgency");
    const btn = $("#submitInc", m); btn.disabled = true; btn.textContent = "Analysing…";
    try {
      const inc = await api("/api/incidents", { method: "POST", body });
      toast(`${inc.number} created`, "good"); closeModal(); await openIncident(inc.id);
      if (location.hash === "#/incidents" || location.hash === "#/dashboard" || !location.hash) route();
    } catch (err) { toast(err.message, "err"); btn.disabled = false; btn.textContent = "Create & analyse"; }
  });
}
async function openIncident(id) {
  let i; try { i = await api(`/api/incidents/${id}`); } catch (e) { return toast(e.message, "err"); }
  const live = i.ai_source && i.ai_source.startsWith("LLM");
  const sn = i.sn_sys_id ? `<span class="badge b-ok">Created in ServiceNow: ${esc(i.sn_number)}</span>`
    : i.sn_status === "Failed" ? `<span class="badge b-failed">Failed</span>` : `<span class="badge">Not sent</span>`;
  const m = modal(`
    <div class="modal-head"><div><h2>${esc(i.number)} &middot; ${esc(i.short_description)}</h2><div style="margin-top:6px">${prioBadge(i.priority_label)} ${statusBadge(i.status)} <span class="badge">${esc(i.category)}</span></div></div><button class="x" aria-label="Close">&times;</button></div>
    <dl class="kv">
      <dt>Description</dt><dd>${esc(i.description)}</dd>
      <dt>Impact / Urgency</dt><dd>${IMPACT[i.impact]} / ${IMPACT[i.urgency]} &rarr; priority ${esc(i.priority_label)}</dd>
      <dt>Assignment group</dt><dd>${esc(i.assignment_group)}</dd>
      <dt>Reporter</dt><dd>${esc(i.reporter)}</dd>
      <dt>Created / Updated</dt><dd>${fmtDate(i.created_at)} / ${fmtDate(i.updated_at)} (UTC)</dd>
    </dl>
    <div class="section"><h3>AI analysis <span class="badge ${live ? "b-ok" : "b-warn"}">${esc(i.ai_source || "n/a")}</span></h3>
      <div class="muted small">${esc(i.ai_note || "")}</div>
      <p><b>Summary:</b> ${esc(i.ai_summary)}</p>
      <b>Troubleshooting steps</b><ol class="steps">${i.ai_steps.map(s => `<li>${esc(s)}</li>`).join("")}</ol>
      <p><b>Recommended resolution:</b> ${esc(i.ai_resolution)}</p></div>
    <div class="section"><h3>Update ticket</h3>
      <div class="form-row"><div><label>Status</label><select id="stSel">${["New", "In Progress", "Resolved", "Closed"].map(s => `<option ${s === i.status ? "selected" : ""}>${s}</option>`).join("")}</select></div>
      <div><label>Assigned technician</label><input id="techInp" maxlength="80" value="${esc(i.assigned_to || "")}"></div></div>
      <div style="margin-top:12px"><button class="btn" id="saveInc">Save changes</button></div></div>
    <div class="section"><h3>ServiceNow ${sn}</h3>
      <div class="muted small" id="snMsg">${esc(i.sn_message || "Optional: push this incident into a real ServiceNow instance (needs SERVICENOW_* settings).")}</div>
      <div style="margin-top:10px"><button class="btn secondary" id="snBtn" ${i.sn_sys_id ? "disabled" : ""}>Create in ServiceNow</button></div></div>`);
  $("#saveInc", m).addEventListener("click", async () => {
    try {
      await api(`/api/incidents/${id}`, { method: "PATCH", body: { status: $("#stSel", m).value, assigned_to: $("#techInp", m).value } });
      toast("Incident updated", "good"); closeModal(); route();
    } catch (e) { toast(e.message, "err"); }
  });
  $("#snBtn", m).addEventListener("click", async (ev) => {
    ev.target.disabled = true; ev.target.textContent = "Contacting ServiceNow…";
    try {
      const r = await api("/api/servicenow/incidents", { method: "POST", body: { incident_id: +id } });
      toast(r.message, r.ok ? "good" : "err"); closeModal(); if (r.ok) openIncident(id); else openIncident(id);
    } catch (e) { toast(e.message, "err"); ev.target.disabled = false; ev.target.textContent = "Create in ServiceNow"; }
  });
}

/* ---------- AI Assistant ---------- */
const MODE_LABEL = {
  "rag-llm": ["RAG + LLM answer", "b-ok"],
  "extractive-fallback": ["Fallback: retrieved passage, no LLM", "b-warn"],
  "no-knowledge": ["No matching knowledge", "b-bad"],
};
async function renderAssistant() {
  view.innerHTML = `
    <div class="card chat">
      <div class="notice small" style="margin-bottom:10px"><b>RAG vs a plain chatbot:</b> a plain LLM answers from memory and may invent company details. This assistant first <i>retrieves</i> your company's knowledge-base articles, then answers only from them and shows the sources.</div>
      <div class="chips" id="chips"></div>
      <div class="chat-log" id="log"></div>
      <form class="chat-form" id="chatForm"><input id="chatInp" maxlength="1000" placeholder="Ask an IT question, e.g. My VPN is not connecting" autocomplete="off" required><button class="btn" id="chatBtn">Ask</button></form>
    </div>`;
  const log = $("#log");
  ["My VPN is not connecting.", "How do I reset my password?", "My laptop is running slowly.", "I cannot access the company portal.", "Outlook keeps crashing"].forEach(q => {
    const b = document.createElement("button"); b.className = "chip"; b.type = "button"; b.textContent = q;
    b.addEventListener("click", () => { $("#chatInp").value = q; $("#chatForm").requestSubmit(); }); $("#chips").appendChild(b);
  });
  const add = (cls, html) => { const d = document.createElement("div"); d.className = `msg ${cls}`; d.innerHTML = html; log.appendChild(d); log.scrollTop = log.scrollHeight; return d; };
  try {  // restore history
    (await api("/api/assistant/history")).forEach(h => h.role === "user" ? add("user", esc(h.content)) : add("bot", botHtml({ answer: h.content, answer_mode: h.mode, sources: [], notes: [], retrieval_mode: null }, true)));
  } catch (e) { /* history is optional */ }
  if (!log.children.length) add("bot", "Hi! I answer IT questions using the company knowledge base. Try one of the examples above.");
  $("#chatForm").addEventListener("submit", async (e) => {
    e.preventDefault(); const q = $("#chatInp").value.trim(); if (!q) return;
    $("#chatInp").value = ""; add("user", esc(q)); $("#chatBtn").disabled = true;
    const wait = add("bot", '<span class="muted">Searching knowledge base…</span>');
    try {
      const r = await api("/api/assistant/chat", { method: "POST", body: { message: q } });
      wait.innerHTML = botHtml(r);
      const b = wait.querySelector(".raise"); if (b) b.addEventListener("click", () => newIncidentModal({ short: q.slice(0, 120), desc: q }));
    } catch (err) { wait.innerHTML = `<span style="color:var(--bad)">${esc(err.message)}</span>`; }
    $("#chatBtn").disabled = false; log.scrollTop = log.scrollHeight;
  });
}
function botHtml(r, fromHistory) {
  const [label, cls] = MODE_LABEL[r.answer_mode] || ["", ""];
  const retr = r.retrieval_mode ? `<span class="badge ${r.retrieval_mode === "semantic" ? "b-ok" : "b-warn"}">Retrieval: ${r.retrieval_mode === "semantic" ? "semantic (embeddings)" : "keyword fallback (not semantic)"}</span>` : "";
  const src = (r.sources || []).map(s => `<details><summary>${esc(s.title)} &middot; ${esc(s.document)} &middot; score ${s.score}</summary><pre>${esc(s.excerpt)}</pre></details>`).join("");
  const notes = (r.notes || []).map(n => `<div class="small muted" style="margin-top:6px">&#9432; ${esc(n)}</div>`).join("");
  const raise = r.answer_mode === "no-knowledge" && !fromHistory ? '<div style="margin-top:8px"><button class="btn secondary raise" type="button">Raise an incident instead</button></div>' : "";
  return `<div class="meta">${label ? `<span class="badge ${cls}">${label}</span>` : ""}${retr}</div>${esc(r.answer)}${src ? `<div class="sources"><b class="small">Sources</b>${src}</div>` : ""}${notes}${raise}`;
}

/* ---------- Service Requests (USM) ---------- */
async function renderRequests() {
  const cat = await api("/api/requests/catalog");
  view.innerHTML = `
    <div class="notice" style="margin-bottom:16px"><b>Universal service management (USM) idea:</b> every department &mdash; IT, HR, Finance, Facilities &mdash; reuses the <i>same</i> workflow: Submit &rarr; Approve &rarr; In progress &rarr; Fulfilled, routed to that department's fulfilment group. This prototype demonstrates the principle; it is not an official ServiceNow USM product.</div>
    <div class="grid two">
      <div class="card"><h2>New service request</h2>
        <form id="reqForm">
          <div class="form-row"><div><label>Department</label><select name="department" id="dept">${cat.departments.map(d => `<option>${d}</option>`).join("")}</select></div>
          <div><label>Request type</label><select name="request_type" id="rtype"></select></div></div>
          <label>Title</label><input name="title" required minlength="5" maxlength="200" placeholder="Short title">
          <label>Details</label><textarea name="description" required minlength="10" maxlength="3000" placeholder="What do you need and why?"></textarea>
          <label>Priority</label><select name="priority"><option>Low</option><option selected>Medium</option><option>High</option></select>
          <div id="routeNote" class="muted small" style="margin-top:8px"></div>
          <div style="margin-top:14px"><button class="btn" id="reqBtn">Submit request</button></div>
        </form></div>
      <div class="card"><div class="card-head"><h2>Requests</h2><select id="rd" style="max-width:150px"><option value="">All departments</option>${cat.departments.map(d => `<option>${d}</option>`).join("")}</select></div><div id="reqList"></div></div>
    </div>`;
  const fillTypes = () => {
    $("#rtype").innerHTML = cat.catalog[$("#dept").value].map(t => `<option>${esc(t)}</option>`).join("");
    $("#routeNote").textContent = `Will be routed to: ${cat.groups[$("#dept").value]}`;
  };
  $("#dept").addEventListener("change", fillTypes); fillTypes();
  const load = async () => {
    const dep = $("#rd").value;
    try {
      const list = await api(`/api/requests${dep ? `?department=${encodeURIComponent(dep)}` : ""}`);
      $("#reqList").innerHTML = list.length ? `<div class="table-wrap"><table><thead><tr><th>Number</th><th>Request</th><th>Dept</th><th>Priority</th><th>Status</th></tr></thead><tbody>${list.map(r => `
        <tr><td><b>${esc(r.number)}</b><div class="small muted">${fmtDate(r.created_at)}</div></td><td>${esc(r.title)}<div class="small muted">${esc(r.request_type)} &middot; ${esc(r.assignment_group)}</div><div class="small muted">${esc(r.description)}</div></td>
        <td>${esc(r.department)}</td><td>${prioBadge(r.priority === "Medium" ? "Moderate" : r.priority)}</td>
        <td><select data-rid="${r.id}" aria-label="Status">${cat.statuses.map(s => `<option ${s === r.status ? "selected" : ""}>${s}</option>`).join("")}</select></td></tr>`).join("")}</tbody></table></div>` : '<div class="empty">No requests yet.</div>';
      $("#reqList").querySelectorAll("select[data-rid]").forEach(s => s.addEventListener("change", async () => {
        try { await api(`/api/requests/${s.dataset.rid}`, { method: "PATCH", body: { status: s.value } }); toast("Status updated", "good"); }
        catch (e) { toast(e.message, "err"); }
      }));
    } catch (e) { $("#reqList").innerHTML = `<div class="error-box">${esc(e.message)}</div>`; }
  };
  $("#rd").addEventListener("change", load);
  $("#reqForm").addEventListener("submit", async (e) => {
    e.preventDefault(); const f = new FormData(e.target), btn = $("#reqBtn"); btn.disabled = true;
    try {
      const r = await api("/api/requests", { method: "POST", body: Object.fromEntries(f.entries()) });
      toast(`${r.number} submitted to ${r.department}`, "good"); e.target.reset(); fillTypes(); await load();
    } catch (err) { toast(err.message, "err"); }
    btn.disabled = false;
  });
  await load();
}

/* ---------- Knowledge base ---------- */
async function renderKnowledge() {
  view.innerHTML = `
    <div class="grid two">
      <div class="card"><div class="card-head"><h2>Documents</h2><button class="btn secondary" id="reindex">Re-index embeddings</button></div><div id="docs"><div class="spinner"></div></div></div>
      <div class="stack">
        <div class="card"><h2>Upload a document</h2><p class="muted small">TXT, Markdown or PDF, up to 2 MB. It is chunked and embedded (if an embedding key is configured) and becomes searchable immediately.</p>
          <form id="upForm"><input type="file" id="file" accept=".txt,.md,.pdf" required><div style="margin-top:12px"><button class="btn" id="upBtn">Upload &amp; index</button></div></form></div>
        <div class="card"><h2>Test retrieval</h2><p class="muted small">Shows what the retriever finds &mdash; no LLM involved. Scores are cosine similarity (semantic) or TF-IDF (keyword fallback).</p>
          <form id="srForm" class="chat-form"><input id="srQ" placeholder="e.g. vpn disconnects" required><button class="btn">Search</button></form><div id="srOut" style="margin-top:12px"></div></div>
      </div>
    </div>`;
  const load = async () => {
    try {
      const docs = await api("/api/knowledge");
      $("#docs").innerHTML = docs.length ? docs.map(d => `<div style="padding:10px 0;border-bottom:1px solid var(--line)"><b>${esc(d.title)}</b> <span class="badge">${esc(d.source)}</span> <span class="badge ${d.embedded ? "b-ok" : "b-warn"}">${d.embedded ? "embedded" : "keyword only"}</span>
        <div class="small muted">${esc(d.filename)} &middot; ${d.chunk_count} chunks</div></div>`).join("") : '<div class="empty">No documents.</div>';
    } catch (e) { $("#docs").innerHTML = `<div class="error-box">${esc(e.message)}</div>`; }
  };
  $("#upForm").addEventListener("submit", async (e) => {
    e.preventDefault(); const fd = new FormData(); fd.append("file", $("#file").files[0]); $("#upBtn").disabled = true;
    try { const r = await api("/api/knowledge/upload", { method: "POST", body: fd }); toast(`Indexed ${r.filename}: ${r.chunks} chunks. ${r.note}`, "good"); e.target.reset(); await load(); }
    catch (err) { toast(err.message, "err"); }
    $("#upBtn").disabled = false;
  });
  $("#reindex").addEventListener("click", async (ev) => {
    ev.target.disabled = true;
    try { const r = await api("/api/knowledge/reindex", { method: "POST" }); toast(`Re-indexed ${r.documents} documents (${r.embedded} embedded)`, "good"); await load(); }
    catch (err) { toast(err.message, "err"); }
    ev.target.disabled = false;
  });
  $("#srForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const r = await api(`/api/knowledge/search?q=${encodeURIComponent($("#srQ").value)}`);
      $("#srOut").innerHTML = `<div class="small">Mode: <span class="badge ${r.mode === "semantic" ? "b-ok" : "b-warn"}">${r.mode === "semantic" ? "semantic" : "keyword fallback"}</span> ${esc(r.note)}</div>` +
        (r.hits.length ? r.hits.map(h => `<div class="sources"><details open><summary>${esc(h.title)} &middot; score ${h.score}</summary><pre>${esc(h.excerpt)}</pre></details></div>`).join("") : '<div class="empty">No relevant chunks found &mdash; the assistant would say the knowledge base lacks this information.</div>');
    } catch (err) { $("#srOut").innerHTML = `<div class="error-box">${esc(err.message)}</div>`; }
  });
  await load();
}

/* ---------- Settings ---------- */
async function renderSettings() {
  const [s, sn] = await Promise.all([api("/api/settings"), api("/api/servicenow/status")]);
  const row = (name, on, detail) => `<tr><td><b>${name}</b></td><td><span class="pill ${on ? "on" : "off"}">${on ? "Configured" : "Not configured"}</span></td><td class="muted">${detail}</td></tr>`;
  view.innerHTML = `
    <div class="card"><h2>Integration status</h2><div class="table-wrap"><table><tbody>
      ${row("LLM (chat completions)", s.llm.configured, s.llm.configured ? `Model ${esc(s.llm.model)} @ ${esc(s.llm.provider_host)}` : "Rule-based fallback is used for incidents; assistant returns retrieved passages only.")}
      ${row("Embeddings (semantic search)", s.embeddings.configured, s.embeddings.configured ? `Model ${esc(s.embeddings.model)}` : "Keyword (TF-IDF) fallback retrieval is used - labelled in the UI.")}
      ${row("ServiceNow Table API", sn.configured, sn.configured ? `Instance ${esc(sn.instance_host)}` : "Optional. The app works fully without it.")}
    </tbody></table></div>
    <p class="muted small">Retrieval mode right now: <b>${esc(s.retrieval_mode)}</b>. Secrets live in the <code>.env</code> file and are never shown here.</p></div>
    <div class="card" style="margin-top:16px"><div class="card-head"><h2>ServiceNow connection test</h2><button class="btn" id="snTest">Test connection</button></div>
      <p class="muted small">Makes one real read-only call to <code>/api/now/table/incident</code>. It reports success only if ServiceNow actually answers.</p><div id="snResult"></div></div>
    <div class="card" style="margin-top:16px"><h2>Security note</h2><p class="muted">${esc(s.demo_auth)} Requests are rate limited and size limited; inputs are validated by Pydantic.</p></div>`;
  $("#snTest").addEventListener("click", async (ev) => {
    ev.target.disabled = true; $("#snResult").innerHTML = '<div class="spinner"></div>';
    try { const r = await api("/api/servicenow/test", { method: "POST" }); $("#snResult").innerHTML = `<div class="${r.ok ? "notice" : "notice warn"}">${r.ok ? "&#10003; " : "&#10007; "}${esc(r.message)}</div>`; }
    catch (e) { $("#snResult").innerHTML = `<div class="error-box">${esc(e.message)}</div>`; }
    ev.target.disabled = false;
  });
}

/* ---------- boot ---------- */
(async function boot() {
  try {
    const s = await api("/api/settings"); const p = $("#llmPill");
    p.textContent = s.llm.configured ? `AI: LLM (${s.llm.model})` : "AI: fallback mode (no LLM key)";
    p.classList.add(s.llm.configured ? "on" : "off");
  } catch (e) { $("#llmPill").textContent = "Server offline"; }
  route();
})();
