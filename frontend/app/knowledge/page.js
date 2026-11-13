"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

const card = { background: "#fff", borderRadius: 10, padding: 16, boxShadow: "0 1px 3px #0001", marginBottom: 12 };
const btn = { padding: "6px 12px", borderRadius: 6, border: "1px solid #0b6bcb", background: "#0b6bcb", color: "#fff", cursor: "pointer", marginRight: 8 };
const ghost = { ...btn, background: "#fff", color: "#0b6bcb" };
const input = { width: "100%", padding: 8, marginBottom: 8, boxSizing: "border-box" };
const CATEGORIES = ["Network", "Hardware", "Software", "Access", "Email", "General"];

async function api(path, opts) {
  const r = await fetch(`/api${path}`, { headers: { "Content-Type": "application/json" }, ...opts });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || r.statusText);
  return data;
}

export default function Knowledge() {
  const [articles, setArticles] = useState([]);
  const [open, setOpen] = useState(null);
  const [form, setForm] = useState({ title: "", category: "General", body: "" });
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    try { setArticles(await api("/kb")); } catch (e) { setError(e.message); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function run(key, fn) {
    setBusy(key); setError("");
    try { await fn(); } catch (e) { setError(e.message); }
    setBusy(null);
  }

  return (
    <main style={{ maxWidth: 860, margin: "0 auto", padding: 24 }}>
      <Link href="/" style={{ color: "#0b6bcb", textDecoration: "none" }}>← Back to tickets</Link>
      <h1 style={{ marginBottom: 4 }}>Knowledge base</h1>
      <p style={{ marginTop: 0, color: "#556" }}>
        Articles are embedded once. A question retrieves the closest articles and the local AI answers using only those, so every answer shows its sources.
        The same retrieval also grounds the AI analysis of tickets.
      </p>

      <div style={card}>
        <h3 style={{ marginTop: 0 }}>Ask the knowledge base</h3>
        <form onSubmit={(e) => { e.preventDefault(); run("ask", async () => setResult(await api("/kb/ask", { method: "POST", body: JSON.stringify({ question }) }))); }}>
          <input required placeholder="e.g. My VPN fails with authentication timeout" value={question} onChange={(e) => setQuestion(e.target.value)} style={input} />
          <button style={btn} disabled={busy === "ask" || articles.length === 0}>{busy === "ask" ? "Searching…" : "Ask"}</button>
          {articles.length === 0 && <span style={{ color: "#a60" }}>Add articles first.</span>}
        </form>
        {result && (
          <div style={{ marginTop: 12, background: "#eef5ff", borderRadius: 8, padding: 12 }}>
            <div style={{ whiteSpace: "pre-wrap" }}>{result.answer}</div>
            <div style={{ marginTop: 8, color: "#556", fontSize: 13 }}>
              {result.sources.length === 0 ? "No article passed the relevance threshold, so the AI was not called." : (
                <>Sources: {result.sources.map((s) => <span key={s.id} style={{ marginRight: 10 }}>KB{s.id} {s.title} <b>({s.score})</b></span>)}</>
              )}
            </div>
          </div>
        )}
      </div>

      <div style={card}>
        <h3 style={{ marginTop: 0 }}>Add an article</h3>
        <form onSubmit={(e) => { e.preventDefault(); run("add", async () => { await api("/kb", { method: "POST", body: JSON.stringify(form) }); setForm({ title: "", category: "General", body: "" }); await load(); }); }}>
          <input required placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} style={input} />
          <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} style={{ ...input, width: "auto" }}>
            {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
          <textarea required placeholder="Steps or guidance" rows={4} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} style={input} />
          <button style={btn} disabled={busy === "add"}>{busy === "add" ? "Saving…" : "Save article"}</button>
          <button type="button" style={ghost} disabled={busy === "seed"} onClick={() => run("seed", async () => { const r = await api("/kb/seed", { method: "POST" }); setNotice(`Added ${r.added} sample articles (${r.total} total).`); await load(); })}>
            {busy === "seed" ? "Loading…" : "Load sample articles"}
          </button>
          {notice && <span style={{ color: "#1a6" }}>{notice}</span>}
        </form>
      </div>

      {error && <div style={{ ...card, background: "#fdecec", color: "#a11" }}>{error}</div>}

      <h3>Articles ({articles.length})</h3>
      {articles.map((a) => (
        <div key={a.id} style={card}>
          <div style={{ cursor: "pointer" }} onClick={() => setOpen(open === a.id ? null : a.id)}>
            <strong>KB{a.id} · {a.title}</strong>
            <span style={{ marginLeft: 8, color: "#556", fontSize: 13 }}>{a.category}</span>
          </div>
          {open === a.id && (
            <>
              <p style={{ margin: "8px 0", whiteSpace: "pre-wrap" }}>{a.body}</p>
              <button style={{ ...ghost, color: "#d33", borderColor: "#d33" }} onClick={() => run(`d${a.id}`, async () => { await api(`/kb/${a.id}`, { method: "DELETE" }); await load(); })}>Delete</button>
            </>
          )}
        </div>
      ))}
    </main>
  );
}
