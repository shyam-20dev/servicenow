"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";

const PRI_COLOR = { Low: "#98a2b3", Medium: "#2f6df6", High: "#d97706", Critical: "#dc2626", "Not analysed": "#d0d5dd" };

function Tile({ label, value, hint, href, alert }) {
  const inner = (<><div className="label">{label}</div><div className="value">{value}</div>{hint && <div className="hint">{hint}</div>}</>);
  return href ? <Link href={href} className={`tile ${alert ? "alert" : ""}`}>{inner}</Link> : <div className={`tile ${alert ? "alert" : ""}`}>{inner}</div>;
}

function Bars({ rows, color }) {
  const real = rows.filter((r) => r.label !== "Not analysed");
  const pending = rows.find((r) => r.label === "Not analysed")?.n || 0;
  const max = Math.max(1, ...real.map((r) => r.n));
  if (!real.length && !pending) return <div className="muted small">No tickets yet.</div>;
  return (
    <div className="bars">
      {real.map((r) => (
        <div className="r" key={r.label}>
          <span>{r.label}</span>
          <div className="track"><div className="fill" style={{ width: `${(100 * r.n) / max}%`, background: color?.(r.label) }} /></div>
          <b>{r.n}</b>
        </div>
      ))}
      {!real.length && <div className="muted small">No AI-analysed tickets yet.</div>}
      {pending > 0 && <div className="muted small" style={{ marginTop: 8 }}>{pending} ticket{pending === 1 ? "" : "s"} not analysed by the AI yet</div>}
    </div>
  );
}

export default function Dashboard() {
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    try { setD(await api("/dashboard")); setError(""); } catch (e) { setError(e.message); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function run(key, fn) {
    setBusy(key); setNote(""); setError("");
    try { await fn(); await load(); } catch (e) { setError(e.message); }
    setBusy("");
  }

  if (!d) return error ? null : <div className="muted">Loading…</div>;
  const s = d.by_status;
  const openCount = (s.open || 0) + (s.in_progress || 0);
  const doneCount = (s.resolved || 0) + (s.closed || 0);

  return (
    <>
      {error && <div className="banner">{error}</div>}
      {d.total === 0 && (
        <div className="banner info">No tickets yet. <Link href="/report"><b>Report an issue</b></Link> to see the AI at work, or load demo data below.</div>
      )}

      <div className="grid g-tiles">
        <Tile label="Total tickets" value={d.total} hint={`${d.analysed} analysed by AI`} href="/tickets" />
        <Tile label="Open / in progress" value={openCount} hint={`${s.in_progress || 0} in progress`} href="/tickets" />
        <Tile label="Resolved / closed" value={doneCount} />
        <Tile label="Needs human review" value={d.pending_review} hint="AI is unsure or the ticket is high impact" href="/tickets?tab=review" alert={d.pending_review > 0} />
        <Tile label="AI override rate" value={d.override_rate == null ? "–" : `${d.override_rate}%`} hint={d.reviewed ? `${d.overridden} of ${d.reviewed} reviewed tickets changed` : "No human reviews yet"} />
        <Tile label="Avg AI analysis time" value={d.avg_ai_seconds == null ? "–" : `${d.avg_ai_seconds}s`} hint={`${d.auto_handled} tickets auto-handled`} />
      </div>

      <div className="grid g-2">
        <div className="card"><h2>Tickets by category</h2><p className="sub">After any human corrections</p><Bars rows={d.by_category} /></div>
        <div className="card"><h2>Tickets by priority</h2><p className="sub">After any human corrections</p><Bars rows={d.by_priority} color={(l) => PRI_COLOR[l]} /></div>
      </div>

      <div className="grid g-2">
        <div className="card">
          <h2>Tickets per day</h2><p className="sub">Last 7 days with activity</p>
          {d.per_day.length === 0 ? <div className="muted small">No data yet.</div> : (
            <div className="cols">
              {d.per_day.map((r) => {
                const max = Math.max(...d.per_day.map((x) => x.n));
                return <div className="c" key={r.day}><b>{r.n}</b><i style={{ height: `${(100 * r.n) / max}%` }} /><span>{r.day.slice(5)}</span></div>;
              })}
            </div>
          )}
        </div>
        <div className="card">
          <div className="row spread"><h2>Incident spikes (Problems)</h2>
            <button className="btn sm" disabled={busy === "detect"} onClick={() => run("detect", async () => { const r = await api("/problems/detect", { method: "POST" }); setNote(`Checked ${r.tickets_considered} recent tickets, found ${r.clusters_found} spike(s).`); })}>{busy === "detect" ? "Detecting…" : "Detect problems"}</button>
          </div>
          <p className="sub">Groups of similar recent tickets that probably share one cause</p>
          {note && <div className="banner ok" style={{ padding: "8px 12px" }}>{note}</div>}
          {d.problems.length === 0 ? <div className="muted small">No Problems detected. Needs 5+ similar tickets within an hour.</div> :
            d.problems.map((p) => (
              <div key={p.id} style={{ padding: "9px 0", borderTop: "1px solid #eef0f4" }}>
                <b>{p.number}</b> · {p.title}
                <div className="small muted">{p.ticket_count} related tickets · <span className="badge b-amber">{p.status}: AI draft</span></div>
              </div>
            ))}
        </div>
      </div>

      <div className="grid g-2">
        <div className="card">
          <h2>Knowledge base</h2>
          <p className="sub">What the AI Assistant can answer from</p>
          <div className="kv"><span className="badge b-blue">{d.kb.files} uploaded files</span><span className="badge">{d.kb.articles} written articles</span><span className="badge">{d.kb.passages} searchable passages</span></div>
          <div className="row" style={{ marginTop: 12 }}><Link className="btn ghost sm" href="/knowledge">Manage knowledge base</Link><Link className="btn ghost sm" href="/assistant">Ask the AI Assistant</Link></div>
        </div>
        <div className="card">
          <h2>AI quality &amp; demo tools</h2>
          <p className="sub">Demo data has hidden labels so the AI can be scored against the truth</p>
          <div className="row">
            <button className="btn sm" disabled={busy === "seed"} onClick={() => run("seed", async () => { const r = await api("/demo/seed", { method: "POST" }); setNote(`Loaded ${r.tickets} demo tickets.`); })}>{busy === "seed" ? "Loading…" : "Load demo data"}</button>
            <button className="btn danger sm" disabled={busy === "clear"} onClick={() => run("clear", async () => { const r = await api("/demo/clear", { method: "POST" }); setNote(`Removed ${r.deleted_tickets} demo tickets.`); })}>Clear demo data</button>
            <Link className="btn ghost sm" href="/evaluation">AI accuracy report →</Link>
          </div>
        </div>
      </div>
    </>
  );
}
