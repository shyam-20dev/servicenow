const STATUS = { open: ["Open", "b-blue"], in_progress: ["In progress", "b-amber"], resolved: ["Resolved", "b-green"], closed: ["Closed", ""] };
const PRIORITY = { Low: "", Medium: "b-blue", High: "b-amber", Critical: "b-red" };
const REVIEW = {
  pending: ["Needs human review", "b-red"], approved: ["Human approved", "b-green"],
  overridden: ["Human overrode AI", "b-purple"], auto: ["Auto-handled", "b-green"],
};

export const StatusBadge = ({ status }) => {
  const [label, cls] = STATUS[status] || [status || "–", ""];
  return <span className={`badge ${cls}`}>{label}</span>;
};
export const PriorityBadge = ({ priority }) => priority ? <span className={`badge ${PRIORITY[priority] || ""}`}>{priority}</span> : null;
export const ReviewBadge = ({ status }) => {
  if (!status) return <span className="badge">Not analysed</span>;
  const [label, cls] = REVIEW[status] || [status, ""];
  return <span className={`badge ${cls}`}>{label}</span>;
};
export const Spinner = () => <span className="spin" style={{ borderColor: "currentColor", borderRightColor: "transparent" }} />;
export const ticketNo = (t) => t.sn_number || `#${t.id}`;
