import { INTENT_LABEL, STATUS_LABEL } from "./theme";

export function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function fmtRelative(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function initials(name) {
  if (!name) return "?";
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();
}

export function intentLabel(intent) {
  return INTENT_LABEL[intent] || intent || "General";
}

export function statusLabel(status) {
  return STATUS_LABEL[status] || status || "-";
}

export function statusBadge(status) {
  if (status === "delivered") return "badge-ok";
  if (status === "out_for_delivery") return "badge-info";
  if (status === "customs") return "badge-warn";
  if (status === "in_transit") return "badge-info";
  if (status === "booked") return "badge-muted";
  return "badge-muted";
}
