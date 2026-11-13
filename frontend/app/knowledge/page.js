"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, CATEGORIES } from "../../lib/api";

const KB_CATEGORIES = [...CATEGORIES.filter((c) => c !== "Other"), "General"];

export default function Knowledge() {
  const [articles, setArticles] = useState([]);
  const [open, setOpen] = useState(null);
  const [cat, setCat] = useState("General");
  const [form, setForm] = useState({ title: "", category: "General", body: "" });
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [over, setOver] = useState(false);
  const input = useRef(null);

  const load = useCallback(async () => { try { setArticles(await api("/kb")); } catch (e) { setError(e.message); } }, []);
  useEffect(() => { load(); }, [load]);

  async function uploadFiles(files) {
    setError(""); setMsg("");
    for (const f of files) {
      setBusy(`Indexing ${f.name}…`);
      try {
        const fd = new FormData(); fd.append("file", f); fd.append("category", cat);
        const r = await api("/kb/upload", { method: "POST", body: fd });
        setMsg((m) => `${m}${m ? " · " : ""}${r.filename}: ${r.chunks} passage${r.chunks === 1 ? "" : "s"} indexed`);
      } catch (e) { setError(`${f.name}: ${e.message}`); }
    }
    setBusy(""); if (input.current) input.current.value = ""; load();
  }

  const written = articles.filter((a) => !a.source);
  const files = Object.values(articles.filter((a) => a.source).reduce((acc, a) => {
    (acc[a.source] ||= { name: a.source, category: a.category, parts: [] }).parts.push(a); return acc;
  }, {})).map((f) => ({ ...f, parts: f.parts.sort((x, y) => x.chunk_idx - y.chunk_idx) }));

  return (
    <>
      {error && <div className="banner">{error}</div>}
      {msg && <div className="banner ok">{msg}</div>}

      <div className="card">
        <h2>Upload documents</h2>
        <p className="sub">Add the files the AI Assistant should answer from: .txt, .md, .pdf or .docx, up to 5 MB each. Each file is split into passages and indexed for search. Uploading a file with the same name replaces it.</p>
        <div className={`drop ${over ? "over" : ""}`} onClick={() => input.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); uploadFiles([...e.dataTransfer.files]); }}>
          <b>{busy || "Drop files here, or click to choose"}</b>
          <span className="muted small">.txt · .md · .pdf · .docx</span>
          <input ref={input} type="file" multiple accept=".txt,.md,.pdf,.docx" hidden onChange={(e) => uploadFiles([...e.target.files])} />
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          <span className="small muted">Category for these files:</span>
          <select value={cat} onChange={(e) => setCat(e.target.value)} style={{ width: 150 }}>{KB_CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select>
          <Link href="/assistant" className="btn ghost sm">Ask the AI Assistant →</Link>
        </div>
      </div>

      <div className="card">
        <h2>Uploaded files ({files.length})</h2>
        {files.length === 0 && <div className="empty">No files uploaded yet.</div>}
        {files.map((f) => (
          <div key={f.name} style={{ padding: "12px 0", borderTop: "1px solid #eef0f4" }}>
            <div className="row spread">
              <div style={{ cursor: "pointer" }} onClick={() => setOpen(open === f.name ? null : f.name)}><b>📄 {f.name}</b> <span className="badge">{f.category}</span> <span className="small muted">{f.parts.length} passage{f.parts.length === 1 ? "" : "s"}</span></div>
              <button className="btn danger sm" onClick={async () => { try { await api(`/kb/file?name=${encodeURIComponent(f.name)}`, { method: "DELETE" }); load(); } catch (e) { setError(e.message); } }}>Delete</button>
            </div>
            {open === f.name && f.parts.map((p) => <div key={p.id} className="passage"><div className="small muted">KB{p.id} · part {p.chunk_idx + 1}</div>{p.body}</div>)}
          </div>
        ))}
      </div>

      <div className="card">
        <div className="row spread"><h2>Written articles ({written.length})</h2>
          <button className="btn ghost sm" disabled={busy !== ""} onClick={async () => { setBusy("Loading…"); try { const r = await api("/kb/seed", { method: "POST" }); setMsg(`Added ${r.added} sample articles (${r.total} total).`); load(); } catch (e) { setError(e.message); } setBusy(""); }}>Load sample articles</button>
        </div>
        <p className="sub">Short how-to articles typed in by hand. They are searched together with the uploaded files.</p>
        <form onSubmit={async (e) => { e.preventDefault(); setBusy("Saving…"); try { await api("/kb", { method: "POST", body: JSON.stringify(form) }); setForm({ title: "", category: "General", body: "" }); load(); } catch (er) { setError(er.message); } setBusy(""); }}>
          <div className="grid" style={{ gridTemplateColumns: "1fr 160px", gap: 10 }}>
            <input type="text" required placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{KB_CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select>
          </div>
          <textarea required rows={3} placeholder="Steps or guidance" style={{ marginTop: 10 }} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} />
          <div style={{ marginTop: 10 }}><button className="btn sm" disabled={busy !== ""}>Save article</button></div>
        </form>
        {written.map((a) => (
          <div key={a.id} style={{ padding: "10px 0", borderTop: "1px solid #eef0f4", marginTop: 6 }}>
            <div className="row spread">
              <div style={{ cursor: "pointer" }} onClick={() => setOpen(open === a.id ? null : a.id)}><b>KB{a.id} · {a.title}</b> <span className="badge">{a.category}</span></div>
              <button className="btn danger sm" onClick={async () => { try { await api(`/kb/${a.id}`, { method: "DELETE" }); load(); } catch (e) { setError(e.message); } }}>Delete</button>
            </div>
            {open === a.id && <div className="passage">{a.body}</div>}
          </div>
        ))}
      </div>
    </>
  );
}
