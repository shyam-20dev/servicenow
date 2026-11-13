export async function api(path, opts = {}) {
  const isForm = opts.body instanceof FormData;
  const r = await fetch(`/api${path}`, {
    ...opts,
    headers: isForm ? opts.headers : { "Content-Type": "application/json", ...(opts.headers || {}) },
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || r.statusText || "Request failed");
  return data;
}

export const CATEGORIES = ["Network", "Hardware", "Software", "Access", "Email", "Other"];
export const PRIORITIES = ["Low", "Medium", "High", "Critical"];
export const GROUPS = ["Network Support", "Hardware Support", "Software Support", "Service Desk"];
export const STATUSES = [["open", "Open"], ["in_progress", "In progress"], ["resolved", "Resolved"], ["closed", "Closed"]];

export function fmtDate(s) {
  if (!s) return "";
  const d = new Date(s.replace(" ", "T") + "Z");
  return d.toLocaleString(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}
