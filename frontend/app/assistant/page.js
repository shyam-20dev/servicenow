"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "../../lib/api";

const SUGGESTIONS = ["How do I fix a VPN authentication timeout?", "My laptop keeps restarting. What should I check?", "How do I reset my password?", "Outlook is stuck on disconnected"];

function Sources({ sources }) {
  const [open, setOpen] = useState(null);
  const [more, setMore] = useState(false);
  if (!sources?.length) return null;
  const cited = sources.filter((s) => s.cited), rest = sources.filter((s) => !s.cited);
  const shown = cited.length ? cited : rest;          // nothing cited: show what was retrieved
  const chip = (s) => (
    <span key={s.id} className={`src ${open === s.id ? "on" : ""}`} onClick={() => setOpen(open === s.id ? null : s.id)}>
      {s.source ? "📄" : "📘"} KB{s.id} · {s.title.length > 40 ? s.title.slice(0, 40) + "…" : s.title} <b>{s.score}</b>
    </span>
  );
  return (
    <div style={{ marginTop: 6 }}>
      <div className="small muted">{cited.length ? "Sources used (click to read the passage)" : "Passages considered (click to read)"}</div>
      {shown.map(chip)}
      {cited.length > 0 && rest.length > 0 && (
        <div style={{ marginTop: 6 }}>
          <span className="small muted" style={{ cursor: "pointer" }} onClick={() => setMore(!more)}>{more ? "Hide" : "Also considered"} ({rest.length})</span>
          {more && <div>{rest.map(chip)}</div>}
        </div>
      )}
      {sources.filter((s) => s.id === open).map((s) => <div key={s.id} className="passage">{s.text}</div>)}
    </div>
  );
}

export default function Assistant() {
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState(false);
  const end = useRef(null);

  useEffect(() => { try { setMsgs(JSON.parse(sessionStorage.getItem("pl_chat") || "[]")); } catch {} }, []);
  useEffect(() => {
    try { sessionStorage.setItem("pl_chat", JSON.stringify(msgs)); } catch {}
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, busy]);

  async function ask(q) {
    q = (q ?? text).trim();
    if (!q || busy) return;
    const history = msgs.map((m) => ({ role: m.role === "bot" ? "assistant" : "user", content: m.text }));
    setMsgs((m) => [...m, { role: "user", text: q }]); setText(""); setBusy(true);
    try {
      const r = await api("/assistant/chat", { method: "POST", body: JSON.stringify({ question: q, history }) });
      setMsgs((m) => [...m, { role: "bot", text: r.answer, sources: r.sources, search: r.search_query, asked: q, grounded: r.used_llm }]);
    } catch (e) { setMsgs((m) => [...m, { role: "bot", text: `Sorry, something went wrong: ${e.message}`, error: true }]); }
    setBusy(false);
  }

  return (
    <div className="chatwrap">
      <div className="row spread" style={{ marginBottom: 8 }}>
        <span className="muted small">Answers come only from the documents in the Knowledge Base, with sources.</span>
        <div className="row"><button className="btn ghost sm" onClick={() => setInfo(!info)}>How it works</button>{msgs.length > 0 && <button className="btn ghost sm" onClick={() => setMsgs([])}>Clear chat</button>}</div>
      </div>
      {info && (
        <div className="card" style={{ padding: 14 }}>
          <b>RAG pipeline</b>
          <ol className="small" style={{ margin: "6px 0 0 18px", padding: 0 }}>
            <li><b>Index:</b> uploaded files are split into passages and turned into embeddings.</li>
            <li><b>Rewrite:</b> follow-up questions are rewritten into a standalone search query using the chat history.</li>
            <li><b>Retrieve:</b> the closest passages are found by vector similarity; weak matches are dropped and each file is capped so one document can&apos;t dominate.</li>
            <li><b>Generate:</b> the model answers using only those passages and cites them. If nothing relevant is found, it says so without calling the model.</li>
          </ol>
        </div>
      )}
      <div className="chatbox">
        {msgs.length === 0 && (
          <div className="empty">
            <b style={{ color: "var(--text)", fontSize: 17 }}>Ask about your documents</b>
            <div className="chips" style={{ justifyContent: "center" }}>{SUGGESTIONS.map((s) => <button key={s} className="chip" onClick={() => ask(s)}>{s}</button>)}</div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.text}
            {m.role === "bot" && !m.error && (
              <>
                {m.search && m.search !== m.asked && <div className="small muted" style={{ marginTop: 8 }}>Searched for: “{m.search}”</div>}
                <Sources sources={m.sources} />
                {!m.grounded && <div className="small muted" style={{ marginTop: 6 }}>No document passed the relevance check, so the model was not called.</div>}
              </>
            )}
          </div>
        ))}
        {busy && <div className="msg bot muted">Searching documents…</div>}
        <div ref={end} />
      </div>
      <form className="composer" onSubmit={(e) => { e.preventDefault(); ask(); }}>
        <input type="text" placeholder="Ask a question about your documents…" value={text} onChange={(e) => setText(e.target.value)} disabled={busy} />
        <button className="btn" disabled={busy || !text.trim()}>Send</button>
      </form>
    </div>
  );
}
