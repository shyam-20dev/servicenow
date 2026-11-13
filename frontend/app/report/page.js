"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, fmtDate } from "../../lib/api";
import { PriorityBadge, ReviewBadge, Spinner, StatusBadge, ticketNo } from "../../components/ui";

function Progress({ t }) {
  const analyzing = t.pipeline === "analyzing", creating = t.pipeline === "creating_incident", failed = t.pipeline === "error";
  const aiDone = !!t.ai, incDone = !!t.sn_number;
  const cls = (done, running, fail) => (done ? "done" : fail ? "fail" : running ? "run" : "");
  return (
    <div className="steps">
      <div className="step done"><div className="dot">✓</div>Submitted</div>
      <div className={`step ${cls(aiDone, analyzing, failed && !aiDone)}`}><div className="dot">{aiDone ? "✓" : failed && !aiDone ? "!" : analyzing ? <Spinner /> : "2"}</div>AI analysis</div>
      <div className={`step ${cls(incDone, creating, failed && aiDone && !incDone)}`}><div className="dot">{incDone ? "✓" : creating ? <Spinner /> : "3"}</div>Incident created</div>
      <div className={`step ${t.status === "resolved" || t.status === "closed" ? "done" : incDone ? "run" : ""}`}><div className="dot">{t.status === "resolved" || t.status === "closed" ? "✓" : "4"}</div>{t.status === "resolved" || t.status === "closed" ? "Resolved" : "Awaiting support"}</div>
    </div>
  );
}

function Result({ t }) {
  const e = t.effective, ai = t.ai;
  return (
    <>
      <Progress t={t} />
      {t.pipeline === "error" && <div className="banner" style={{ margin: "0 0 12px" }}>Automatic processing stopped: {t.pipeline_error}. A support engineer can still pick this up.</div>}
      <div className="kv"><b>{ticketNo(t)}</b><StatusBadge status={t.status} /><ReviewBadge status={t.review_status} /></div>
      {ai && (
        <div className="box">
          <div><b>AI summary:</b> {ai.summary}</div>
          <div className="kv"><span className="badge b-blue">{e.category}</span><PriorityBadge priority={e.priority} /><span className="badge">{e.assignment_group}</span></div>
          <div className="small muted" style={{ marginTop: 8 }}>Suggested troubleshooting while you wait:</div>
          <ol>{ai.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
          {ai.sources?.length > 0 && <div className="small muted" style={{ marginTop: 8 }}>Based on: {ai.sources.map((x) => `${x.title} (${x.score})`).join(" · ")}</div>}
        </div>
      )}
      {t.review_status === "pending" && (
        <div className="banner info" style={{ margin: "12px 0 0" }}><b>A support engineer will review this ticket.</b> {t.review_reasons.join(" · ")}</div>
      )}
    </>
  );
}

export default function Report() {
  const [name, setName] = useState("");
  const [form, setForm] = useState({ short_description: "", description: "" });
  const [current, setCurrent] = useState(null);
  const [mine, setMine] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { try { setName(localStorage.getItem("pl_name") || ""); } catch {} }, []);

  const loadMine = useCallback(async (who) => {
    if (!who) return setMine([]);
    try { setMine((await api(`/tickets?requester=${encodeURIComponent(who)}&limit=8`)).tickets); } catch {}
  }, []);
  useEffect(() => { loadMine(name.trim()); }, [name, loadMine]);

  const processing = (t) => t && (t.pipeline === "analyzing" || t.pipeline === "creating_incident");
  useEffect(() => {
    if (!processing(current)) return;
    const timer = setInterval(async () => {
      try { const t = await api(`/tickets/${current.id}`); setCurrent(t); if (!processing(t)) loadMine(name.trim()); } catch {}
    }, 2000);
    return () => clearInterval(timer);
  }, [current, name, loadMine]);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const who = name.trim() || "Anonymous";
      try { localStorage.setItem("pl_name", name.trim()); } catch {}
      const t = await api("/tickets", { method: "POST", body: JSON.stringify({ ...form, requester: who }) });
      setCurrent(t); setForm({ short_description: "", description: "" }); loadMine(who);
    } catch (err) { setError(err.message); }
    setBusy(false);
  }

  return (
    <div className="grid g-2" style={{ alignItems: "start" }}>
      <div>
        <form className="card" onSubmit={submit}>
          <h2>Report an issue</h2>
          <p className="sub">Describe the problem. The AI analyses it, an incident is created, and you can follow its status here.</p>
          <label className="f">Your name</label>
          <input type="text" placeholder="e.g. Asha Rao" value={name} onChange={(e) => setName(e.target.value)} />
          <label className="f">What is the problem?</label>
          <input type="text" required placeholder="e.g. Cannot connect to the VPN" value={form.short_description} onChange={(e) => setForm({ ...form, short_description: e.target.value })} />
          <label className="f">Details</label>
          <textarea required rows={5} placeholder="What happened, since when, what you already tried, how it affects your work" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          {error && <div className="banner" style={{ marginTop: 12 }}>{error}</div>}
          <div style={{ marginTop: 16 }}><button className="btn" disabled={busy}>{busy ? "Submitting…" : "Submit ticket"}</button></div>
        </form>

        <div className="card">
          <h2>Your tickets</h2>
          <p className="sub">{name.trim() ? `Raised by ${name.trim()}` : "Enter your name above to see your tickets"}</p>
          {name.trim() && mine.length === 0 && <div className="muted small">No tickets yet.</div>}
          {mine.map((t) => (
            <div key={t.id} style={{ padding: "10px 0", borderTop: "1px solid #eef0f4", cursor: "pointer" }} onClick={() => setCurrent(t)}>
              <div className="row spread"><b>{t.short_description}</b><StatusBadge status={t.status} /></div>
              <div className="small muted">{ticketNo(t)} · {fmtDate(t.created_at)}{processing(t) ? " · analysing…" : ""}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>{current ? current.short_description : "Ticket status"}</h2>
        {!current ? <div className="empty">Submit a ticket to see the AI analysis and incident status here.</div> : (
          <>
            <p className="sub">{current.description}</p>
            <Result t={current} />
            <div style={{ marginTop: 14 }}><Link href="/tickets" className="small">Support view: Ticket Evaluation →</Link></div>
          </>
        )}
      </div>
    </div>
  );
}
