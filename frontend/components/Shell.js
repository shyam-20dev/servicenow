"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const NAV = [
  ["/", "Dashboard"],
  ["/report", "Report an Issue"],
  ["/tickets", "Ticket Evaluation"],
  ["/knowledge", "Knowledge Base"],
  ["/assistant", "AI Assistant"],
];
const TITLES = { ...Object.fromEntries(NAV), "/evaluation": "AI Accuracy" };

export default function Shell({ children }) {
  const path = usePathname() || "/";
  const [health, setHealth] = useState(undefined); // undefined = checking, null = unreachable

  useEffect(() => {
    let alive = true;
    const check = () => fetch("/api/health").then((r) => r.json()).then((d) => alive && setHealth(d)).catch(() => alive && setHealth(null));
    check();
    const t = setInterval(check, 30000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const llm = health?.llm;
  const provider = llm?.provider === "gemini" ? "Gemini" : "Ollama";
  const pill = health === undefined ? ["pill", "Checking…"]
    : health === null ? ["pill bad", "Server offline"]
    : llm?.up && llm?.model_ready ? ["pill ok", `Online · ${provider}`]
    : ["pill bad", `${provider} unavailable`];

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="logo">P</div><div><b>ProblemLens</b><span>Service Management</span></div></div>
        <nav className="nav">
          {NAV.map(([href, label]) => (
            <Link key={href} href={href} className={href === "/" ? (path === "/" ? "active" : "") : path.startsWith(href) ? "active" : ""}>{label}</Link>
          ))}
        </nav>
        <div className="foot">AI suggests. A human decides.</div>
      </aside>
      <div className="main">
        <header className="topbar">
          <h1>{TITLES[path] || TITLES["/" + path.split("/")[1]] || "ProblemLens"}</h1>
          <span className={pill[0]} title={llm?.error || (llm ? `Model: ${llm.model}` : "")}>{pill[1]}</span>
        </header>
        <div className="content">
          {health === null && <div className="banner">Cannot reach the ProblemLens server. Is it running?</div>}
          {health && llm && !(llm.up && llm.model_ready) && <div className="banner">The {provider} model is not available: {llm.error || "model not ready"}. AI features will fail until this is fixed.</div>}
          {children}
        </div>
      </div>
    </div>
  );
}
