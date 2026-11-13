"use client";
import { useCallback, useEffect, useState } from "react";
import { api, CATEGORIES, fmtDate, GROUPS, PRIORITIES, STATUSES } from "../../lib/api";
import { PriorityBadge, ReviewBadge, StatusBadge, ticketNo } from "../../components/ui";

const PAGE = 15;

function Drawer({ id, onClose, onChanged }) {
  const [t, setT] = useState(null);
  const [ov, setOv] = useState({ category: "", priority: "", assignment_group: "" });
  const [status, setStatus] = useState("open");
  const [notes, setNotes] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    const x = await api(`/tickets/${id}`);
    setT(x); setStatus(x.status); setNotes(x.resolution_notes || "");
    setOv({ category: x.effective?.category || "", priority: x.effective?.priority || "", assignment_group: x.effective?.assignment_group || "" });
  }, [id]);
  useEffect(() => { load().catch((e) => setErr(e.message)); }, [load]);

  async function act(fn, ok) {
    setErr(""); setMsg("");
    try { await fn(); await load(); onChanged(); setMsg(ok); } catch (e) { setErr(e.message); }
  }
  if (!t) return <><div className="overlay" onClick={onClose} /><div className="drawer">{err ? <div className="banner">{err}</div> : "Loading…"}</div></>;
  const ai = t.ai, e = t.effective;
  const aiOf = (k) => ai?.[k];

  return (
    <>
      <div className="overlay" onClick={onClose} />
      <div className="drawer">
        <div className="row spread"><h2>{ticketNo(t)} · {t.short_description}</h2><button className="btn ghost sm" onClick={onClose}>Close</button></div>
        <div className="kv" style={{ marginTop: 8 }}><StatusBadge status={t.status} /><ReviewBadge status={t.review_status} /><span className="muted small">Raised by {t.requester || "Anonymous"} · {fmtDate(t.created_at)}</span></div>
        <p style={{ whiteSpace: "pre-wrap" }}>{t.description}</p>
        {err && <div className="banner">{err}</div>}
        {msg && <div className="banner ok" style={{ padding: "8px 12px" }}>{msg}</div>}

        {t.review_status === "pending" && (
          <div className="banner info"><b>Why a human should look at this</b><ul style={{ margin: "6px 0 0 18px", padding: 0 }}>{t.review_reasons.map((r, i) => <li key={i}>{r}</li>)}</ul></div>
        )}

        <div className="sec">
          <h3>AI analysis</h3>
          {!ai ? <p className="muted">This ticket has not been analysed by the AI.</p> : (
            <>
              <p style={{ margin: "6px 0" }}>{ai.summary}</p>
              <div className="kv"><span className="muted small">AI suggested:</span><span className="badge b-blue">{ai.category}</span><PriorityBadge priority={ai.priority} /><span className="badge">{ai.assignment_group}</span></div>
              {t.review_status === "overridden" && <div className="kv"><span className="muted small">Human decided:</span><span className="badge b-purple">{e.category}</span><PriorityBadge priority={e.priority} /><span className="badge">{e.assignment_group}</span></div>}
              {ai.reasoning && <p className="small muted">Reasoning: {ai.reasoning}</p>}
              <ol style={{ margin: "6px 0 0 18px", padding: 0 }}>{ai.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
              {ai.sources?.length > 0 && <p className="small muted">Based on knowledge base: {ai.sources.map((x) => `${x.title} (${x.score})`).join(" · ")}</p>}
            </>
          )}
        </div>

        {ai && (
          <div className="sec">
            <h3>Human evaluation</h3>
            <p className="sub">Approve the AI&apos;s suggestion, or correct it. Corrections feed the AI override rate on the dashboard.</p>
            <div className="grid" style={{ gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
              <div><label className="f" style={{ marginTop: 0 }}>Category</label><select value={ov.category} onChange={(x) => setOv({ ...ov, category: x.target.value })}>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select></div>
              <div><label className="f" style={{ marginTop: 0 }}>Priority</label><select value={ov.priority} onChange={(x) => setOv({ ...ov, priority: x.target.value })}>{PRIORITIES.map((c) => <option key={c}>{c}</option>)}</select></div>
              <div><label className="f" style={{ marginTop: 0 }}>Team</label><select value={ov.assignment_group} onChange={(x) => setOv({ ...ov, assignment_group: x.target.value })}>{GROUPS.map((c) => <option key={c}>{c}</option>)}</select></div>
            </div>
            <div className="row" style={{ marginTop: 12 }}>
              <button className="btn" onClick={() => act(() => api(`/tickets/${id}/review`, { method: "POST", body: JSON.stringify({ action: "approve" }) }), "Approved the AI suggestion.")}>Approve AI suggestion</button>
              <button className="btn ghost" onClick={() => act(() => api(`/tickets/${id}/review`, { method: "POST", body: JSON.stringify({ action: "override", category: ov.category, priority: ov.priority, assignment_group: ov.assignment_group }) }), "Saved your decision.")}>Save my values</button>
            </div>
          </div>
        )}

        <div className="sec">
          <h3>Status &amp; resolution</h3>
          <div className="grid" style={{ gridTemplateColumns: "180px 1fr", gap: 10, marginTop: 8 }}>
            <select value={status} onChange={(x) => setStatus(x.target.value)}>{STATUSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
            <input type="text" placeholder="Resolution notes (what fixed it)" value={notes} onChange={(x) => setNotes(x.target.value)} />
          </div>
          <div style={{ marginTop: 12 }}><button className="btn" onClick={() => act(() => api(`/tickets/${id}`, { method: "PATCH", body: JSON.stringify({ status, resolution_notes: notes }) }), "Ticket updated.")}>Update ticket</button></div>
          {t.resolved_at && <p className="small muted">Resolved {fmtDate(t.resolved_at)}</p>}
        </div>
      </div>
    </>
  );
}

export default function Tickets() {
  const [tab, setTab] = useState("review");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const [data, setData] = useState({ total: 0, counts: { all: 0, pending: 0, reviewed: 0 }, tickets: [] });
  const [open, setOpen] = useState(null);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => { // honour /tickets?tab=review from the dashboard
    const t = new URLSearchParams(window.location.search).get("tab");
    if (t === "all" || t === "reviewed") setTab(t);
    setReady(true);
  }, []);

  const load = useCallback(async () => {
    const p = new URLSearchParams({ limit: PAGE, offset: page * PAGE });
    if (q) p.set("q", q);
    if (status) p.set("status", status);
    if (tab === "review") p.set("review", "pending");
    if (tab === "reviewed") p.set("review", "reviewed");
    try { setData(await api(`/tickets?${p}`)); setError(""); } catch (e) { setError(e.message); }
  }, [tab, q, status, page]);
  useEffect(() => { if (ready) { const t = setTimeout(load, q ? 250 : 0); return () => clearTimeout(t); } }, [load, ready, q]);

  const pages = Math.max(1, Math.ceil(data.total / PAGE));
  const Tab = ({ id, label, n, warn }) => (
    <button className={`tab ${tab === id ? "on" : ""} ${warn ? "warn" : ""}`} onClick={() => { setTab(id); setPage(0); }}>{label}<span className="n">{n}</span></button>
  );

  return (
    <>
      <div className="tabs">
        <Tab id="review" label="Needs human review" n={data.counts.pending} warn={data.counts.pending > 0} />
        <Tab id="all" label="All tickets" n={data.counts.all} />
        <Tab id="reviewed" label="Human reviewed" n={data.counts.reviewed} />
      </div>
      <div className="card">
        <div className="row spread" style={{ marginBottom: 12 }}>
          <p className="sub" style={{ margin: 0 }}>
            {tab === "review" ? "Tickets the AI is unsure about, or that are high impact. A person should confirm or correct them."
              : tab === "reviewed" ? "Tickets a person has approved or corrected." : "Every ticket raised by everyone, with its current status."}
          </p>
          <div className="row">
            <input type="search" placeholder="Search tickets or people" value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} style={{ width: 230 }} />
            <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(0); }} style={{ width: 150 }}>
              <option value="">All statuses</option>{STATUSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
        </div>
        {error && <div className="banner">{error}</div>}
        {data.tickets.length === 0 ? (
          <div className="empty">{tab === "review" ? "Nothing needs human review right now." : "No tickets found."}</div>
        ) : (
          <div className="tablewrap">
            <table className="t">
              <thead><tr><th>Ticket</th><th>Raised by</th><th>Category</th><th>Priority</th><th>Team</th><th>Status</th><th>Review</th><th>Created</th></tr></thead>
              <tbody>
                {data.tickets.map((t) => (
                  <tr key={t.id} onClick={() => setOpen(t.id)}>
                    <td><b>{ticketNo(t)}</b><div>{t.short_description}</div></td>
                    <td>{t.requester || "–"}</td>
                    <td>{t.effective ? t.effective.category : <span className="muted">–</span>}</td>
                    <td>{t.effective ? <PriorityBadge priority={t.effective.priority} /> : "–"}</td>
                    <td className="small">{t.effective?.assignment_group || "–"}</td>
                    <td><StatusBadge status={t.status} /></td>
                    <td><ReviewBadge status={t.review_status} />{t.review_status === "pending" && <div className="small muted" style={{ maxWidth: 210 }}>{t.review_reasons[0]}</div>}</td>
                    <td className="small muted">{fmtDate(t.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="row spread" style={{ marginTop: 14 }}>
          <span className="small muted">{data.total} ticket{data.total === 1 ? "" : "s"}</span>
          <div className="row"><button className="btn ghost sm" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button><span className="small">Page {page + 1} of {pages}</span><button className="btn ghost sm" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>Next</button></div>
        </div>
      </div>
      {open && <Drawer id={open} onClose={() => setOpen(null)} onChanged={load} />}
    </>
  );
}
