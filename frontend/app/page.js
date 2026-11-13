"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

const card = { background: "#fff", borderRadius: 10, padding: 16, boxShadow: "0 1px 3px #0001", marginBottom: 12 };
const btn = { padding: "6px 12px", borderRadius: 6, border: "1px solid #0b6bcb", background: "#0b6bcb", color: "#fff", cursor: "pointer", marginRight: 8 };

async function api(path, opts) {
  const r = await fetch(`/api${path}`, { headers: { "Content-Type": "application/json" }, ...opts });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || r.statusText);
  return data;
}

export default function Home() {
  const [tickets, setTickets] = useState([]);
  const [total, setTotal] = useState(0);
  const [problems, setProblems] = useState([]);
  const [notice, setNotice] = useState("");
  const [health, setHealth] = useState(null);
  const [form, setForm] = useState({ short_description: "", description: "" });
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const t = await api("/tickets?limit=20");
      setTickets(t.tickets); setTotal(t.total);
      setProblems(await api("/problems"));
    } catch (e) { setError(e.message); }
  }, []);

  useEffect(() => {
    load();
    api("/health").then(setHealth).catch(() => setHealth(null));
  }, [load]);

  async function run(key, fn) {
    setBusy(key); setError("");
    try { await fn(); await load(); } catch (e) { setError(e.message); }
    setBusy(null);
  }

  const dot = (ok) => <span style={{ color: ok ? "#1a9d4b" : "#d33" }}>●</span>;

  return (
    <main style={{ maxWidth: 860, margin: "0 auto", padding: 24 }}>
      <h1 style={{ marginBottom: 4 }}>ProblemLens</h1>
      <p style={{ marginTop: 0, color: "#556" }}>AI-assisted IT service desk. The AI only suggests; a human reviews.</p>

      <div style={card}>
        {health ? (
          <>
            {dot(health.api)} API &nbsp; {dot(health.ollama?.up && health.ollama?.model_ready)} Ollama
            {health.ollama?.up && !health.ollama?.model_ready && " (model not pulled)"} &nbsp;
            {dot(health.servicenow?.ok)} ServiceNow {health.servicenow?.error && <small>({health.servicenow.error})</small>}
          </>
        ) : "Checking services…"}
      </div>

      <form style={card} onSubmit={(e) => { e.preventDefault(); run("create", async () => { await api("/tickets", { method: "POST", body: JSON.stringify(form) }); setForm({ short_description: "", description: "" }); }); }}>
        <h3 style={{ marginTop: 0 }}>Report an issue</h3>
        <input required placeholder="Short description" value={form.short_description} onChange={(e) => setForm({ ...form, short_description: e.target.value })} style={{ width: "100%", padding: 8, marginBottom: 8, boxSizing: "border-box" }} />
        <textarea required placeholder="Describe the problem" rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} style={{ width: "100%", padding: 8, marginBottom: 8, boxSizing: "border-box" }} />
        <button style={btn} disabled={busy === "create"}>Submit ticket</button>
      </form>

      <div style={card}>
        <h3 style={{ marginTop: 0 }}>Problem detection</h3>
        <p style={{ marginTop: 0, color: "#556" }}>{total} tickets in the system. Detection groups similar recent tickets with embeddings and drafts a Problem for each spike.</p>
        <button style={btn} disabled={busy === "seed"} onClick={() => run("seed", async () => { const r = await api("/demo/seed", { method: "POST" }); setNotice(`Loaded ${r.tickets} synthetic tickets (with hidden incident spikes).`); })}>
          {busy === "seed" ? "Loading…" : "Load demo data"}
        </button>
        <button style={btn} disabled={busy === "detect"} onClick={() => run("detect", async () => { const r = await api("/problems/detect", { method: "POST" }); setNotice(`Embedded ${r.embedded} tickets, checked ${r.tickets_considered} recent ones, found ${r.clusters_found} spike(s).`); })}>
          {busy === "detect" ? "Detecting… (can take a minute)" : "Detect problems"}
        </button>
        {notice && <div style={{ marginTop: 8, color: "#1a6" }}>{notice}</div>}
      </div>

      <div style={{ marginBottom: 12 }}>
        <Link href="/evaluation" style={{ fontSize: 13, padding: "4px 10px", border: "1px solid #0b6bcb", borderRadius: 6, color: "#0b6bcb", textDecoration: "none", background: "#fff" }}>
          View AI evaluation →
        </Link>
        <Link href="/knowledge" style={{ fontSize: 13, padding: "4px 10px", border: "1px solid #0b6bcb", borderRadius: 6, color: "#0b6bcb", textDecoration: "none", background: "#fff", marginLeft: 8 }}>
          Knowledge base →
        </Link>
      </div>

      {problems.map((p) => (
        <div key={p.id} style={{ ...card, borderLeft: "4px solid #d9822b" }}>
          <strong>{p.number} · {p.title}</strong>
          <span style={{ marginLeft: 8, color: "#a60" }}>{p.status} (AI draft, needs review)</span>
          <div style={{ margin: "6px 0" }}>{p.ticket_count} related tickets · {p.first_seen} → {p.last_seen} UTC</div>
          <div><b>Suspected cause:</b> {p.root_cause}</div>
          <ol style={{ margin: "6px 0 0 18px", padding: 0 }}>{p.actions.map((a, i) => <li key={i}>{a}</li>)}</ol>
        </div>
      ))}

      {error && <div style={{ ...card, background: "#fdecec", color: "#a11" }}>{error}</div>}

      <h3>Latest tickets (showing {tickets.length} of {total})</h3>
      {tickets.map((t) => (
        <div key={t.id} style={card}>
          <strong>#{t.id} {t.short_description}</strong>
          {t.sn_number && <span style={{ marginLeft: 8, color: "#1a9d4b" }}>Incident {t.sn_number}</span>}
          <p style={{ margin: "6px 0" }}>{t.description}</p>
          {t.ai && (
            <div style={{ background: "#eef5ff", borderRadius: 8, padding: 10, marginBottom: 8 }}>
              <div><b>Summary:</b> {t.ai.summary}</div>
              <div><b>Category:</b> {t.ai.category} · <b>Priority:</b> {t.ai.priority} · <b>Team:</b> {t.ai.assignment_group}</div>
              <ol style={{ margin: "6px 0 0 18px", padding: 0 }}>{t.ai.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
              {t.ai.sources?.length > 0 && (
                <div style={{ marginTop: 6, fontSize: 13, color: "#556" }}>
                  Based on: {t.ai.sources.map((x) => <span key={x.id} style={{ marginRight: 10 }}>KB{x.id} {x.title} ({x.score})</span>)}
                </div>
              )}
            </div>
          )}
          <button style={btn} disabled={busy === `a${t.id}`} onClick={() => run(`a${t.id}`, () => api(`/tickets/${t.id}/analyze`, { method: "POST" }))}>
            {busy === `a${t.id}` ? "Analyzing…" : "AI analyze"}
          </button>
          {!t.sn_number && (
            <button style={btn} disabled={busy === `p${t.id}`} onClick={() => run(`p${t.id}`, () => api(`/tickets/${t.id}/push`, { method: "POST" }))}>
              Create incident
            </button>
          )}
        </div>
      ))}
    </main>
  );
}
