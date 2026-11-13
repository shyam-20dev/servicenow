"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

const card = { background: "#fff", borderRadius: 10, padding: 16, boxShadow: "0 1px 3px #0001", marginBottom: 12 };
const btn = { padding: "6px 12px", borderRadius: 6, border: "1px solid #0b6bcb", background: "#0b6bcb", color: "#fff", cursor: "pointer", marginRight: 8 };
const th = { textAlign: "left", padding: "6px 8px", borderBottom: "1px solid #dde", fontWeight: 600 };
const td = { padding: "6px 8px", borderBottom: "1px solid #eef" };

async function api(path, opts) {
  const r = await fetch(`/api${path}`, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || r.statusText);
  return data;
}

const pct = (v) => (v === null || v === undefined ? "–" : `${v}%`);
const color = (v) => (v === null || v === undefined ? "#889" : v >= 80 ? "#1a9d4b" : v >= 50 ? "#d9822b" : "#d33");

function Tile({ label, value, hint }) {
  return (
    <div style={{ ...card, flex: "1 1 160px", marginBottom: 0 }}>
      <div style={{ color: "#556", fontSize: 13 }}>{label}</div>
      <div style={{ fontSize: 30, fontWeight: 700, color: color(typeof value === "number" ? value : null) }}>{typeof value === "number" ? `${value}%` : value ?? "–"}</div>
      {hint && <div style={{ color: "#889", fontSize: 12 }}>{hint}</div>}
    </div>
  );
}

export default function Evaluation() {
  const [m, setM] = useState(null);
  const [n, setN] = useState(20);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setM(await api("/evaluation")); } catch (e) { setError(e.message); }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!m?.job?.running) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [m?.job?.running, load]);

  async function start() {
    setError("");
    try { await api(`/evaluation/run?n=${n}`, { method: "POST" }); await load(); } catch (e) { setError(e.message); }
  }

  const tr = m?.triage, cl = m?.clustering, job = m?.job;

  return (
    <main style={{ maxWidth: 860, margin: "0 auto", padding: 24 }}>
      <Link href="/" style={{ color: "#0b6bcb", textDecoration: "none" }}>← Back to tickets</Link>
      <h1 style={{ marginBottom: 4 }}>Evaluation</h1>
      <p style={{ marginTop: 0, color: "#556" }}>
        How good is the AI? Synthetic tickets carry ground-truth labels, so the AI's answers can be scored.
      </p>

      <div style={card}>
        <b>Triage test</b> — run the AI on
        <select value={n} onChange={(e) => setN(+e.target.value)} disabled={job?.running} style={{ margin: "0 8px", padding: 4 }}>
          {[10, 20, 40].map((x) => <option key={x}>{x}</option>)}
        </select>
        labelled tickets (about 10–15 s each).
        <div style={{ marginTop: 10 }}>
          <button style={btn} onClick={start} disabled={job?.running}>{job?.running ? "Running…" : "Run evaluation"}</button>
          {job?.running && <span>{job.done} / {job.total} done{job.failed ? `, ${job.failed} failed` : ""}</span>}
        </div>
        {job?.running && (
          <div style={{ height: 6, background: "#e3e8ef", borderRadius: 3, marginTop: 8 }}>
            <div style={{ height: 6, borderRadius: 3, background: "#0b6bcb", width: `${(100 * job.done) / (job.total || 1)}%` }} />
          </div>
        )}
        {error && <div style={{ color: "#a11", marginTop: 8 }}>{error}</div>}
      </div>

      {tr && tr.n === 0 && (
        <div style={card}>No evaluated tickets yet. On the home page click <b>Load demo data</b>, then come back and click <b>Run evaluation</b>.</div>
      )}

      {tr && tr.n > 0 && (
        <>
          <h3>AI triage ({tr.n} tickets scored)</h3>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
            <Tile label="Category correct" value={tr.category_acc} />
            <Tile label="Priority correct" value={tr.priority_acc} />
            <Tile label="Team correct" value={tr.group_acc} />
            <Tile label="Avg time per ticket" value={tr.avg_latency_s != null ? `${tr.avg_latency_s}s` : "–"} />
          </div>
          <div style={card}>
            <div style={{ color: "#556", marginBottom: 6 }}>
              Invalid answers replaced by a safe default: <b>{pct(tr.corrected_pct)}</b> of tickets.
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead><tr><th style={th}>True category</th><th style={th}>Tickets</th><th style={th}>Correct</th><th style={th}>Accuracy</th></tr></thead>
              <tbody>
                {tr.per_category.map((r) => (
                  <tr key={r.category}><td style={td}>{r.category}</td><td style={td}>{r.n}</td><td style={td}>{r.correct}</td>
                    <td style={{ ...td, color: color(r.acc), fontWeight: 600 }}>{pct(r.acc)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          {tr.mistakes.length > 0 && (
            <div style={card}>
              <b>Recent category mistakes</b>
              <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 6 }}>
                <thead><tr><th style={th}>Ticket</th><th style={th}>True</th><th style={th}>AI said</th></tr></thead>
                <tbody>
                  {tr.mistakes.map((x) => (
                    <tr key={x.id}><td style={td}>#{x.id} {x.text}</td><td style={td}>{x.true}</td><td style={{ ...td, color: "#d33" }}>{x.predicted}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {cl && (
        <>
          <h3>Problem detection (clustering)</h3>
          {cl.spike_tickets === 0 ? (
            <div style={card}>No demo data loaded. Click <b>Load demo data</b> then <b>Detect problems</b> on the home page.</div>
          ) : cl.problems.length === 0 ? (
            <div style={card}>{cl.spike_tickets} hidden spike tickets exist, but detection hasn't run yet. Click <b>Detect problems</b> on the home page.</div>
          ) : (
            <>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
                <Tile label="Spike tickets found" value={cl.recall} hint={`${cl.detected} of ${cl.spike_tickets}`} />
                <Tile label="Group purity" value={cl.precision} hint="tickets in a Problem that truly belong to a spike" />
              </div>
              <div style={card}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead><tr><th style={th}>Problem</th><th style={th}>Tickets</th><th style={th}>Actual cause</th><th style={th}>Purity</th></tr></thead>
                  <tbody>
                    {cl.problems.map((p) => (
                      <tr key={p.number}><td style={td}>{p.number} {p.title}</td><td style={td}>{p.tickets}</td><td style={td}>{p.dominant}</td>
                        <td style={{ ...td, color: color(p.purity), fontWeight: 600 }}>{pct(p.purity)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </main>
  );
}
