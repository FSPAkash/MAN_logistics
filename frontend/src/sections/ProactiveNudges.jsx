import { useMemo, useState } from "react";
import { api } from "../api";
import { fmtTime, fmtRelative, initials } from "../utils";

const STATUS_META = {
  scheduled:        { label: "Scheduled",        cls: "badge-info" },
  pending_approval: { label: "Needs approval",   cls: "badge-warn" },
  sent:             { label: "Sent",             cls: "badge-ok" },
  cancelled:        { label: "Cancelled",        cls: "badge-muted" },
};

export function ProactiveNudges({ nudges, agentConfig, onAction, onOpenInbox }) {
  const [ruleFilter, setRuleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [busyId, setBusyId] = useState(null);

  const ruleIds = useMemo(() => Array.from(new Set(nudges.map((n) => n.rule_id))), [nudges]);
  const filtered = useMemo(() => {
    return nudges.filter((n) => {
      if (ruleFilter !== "all" && n.rule_id !== ruleFilter) return false;
      if (statusFilter !== "all" && n.status !== statusFilter) return false;
      return true;
    });
  }, [nudges, ruleFilter, statusFilter]);

  async function send(id) {
    setBusyId(id);
    try { await api.sendNudge(id); await onAction(); } finally { setBusyId(null); }
  }
  async function cancel(id) {
    setBusyId(id);
    try { await api.cancelNudge(id); await onAction(); } finally { setBusyId(null); }
  }

  const counts = useMemo(() => {
    const c = { scheduled: 0, pending_approval: 0, sent: 0, cancelled: 0 };
    nudges.forEach((n) => { c[n.status] = (c[n.status] || 0) + 1; });
    return c;
  }, [nudges]);

  return (
    <div className="stack">
      <div className="nudge-rule-strip">
        {(agentConfig?.nudge_rules || []).map((r) => (
          <div key={r.id} className="nudge-rule-card">
            <strong>{r.id}</strong>
            <span>{r.trigger}</span>
            <em>&rarr; {r.action}</em>
          </div>
        ))}
      </div>

      <div className="table-controls">
        <div className="table-filter-grid">
          <label className="field-inline">
            <span>Rule</span>
            <select value={ruleFilter} onChange={(e) => setRuleFilter(e.target.value)}>
              <option value="all">All</option>
              {ruleIds.map((id) => <option key={id} value={id}>{id}</option>)}
            </select>
          </label>
          <div className="inbox-filters">
            {[
              { id: "all", label: `All (${nudges.length})` },
              { id: "scheduled", label: `Scheduled (${counts.scheduled || 0})` },
              { id: "pending_approval", label: `Approval (${counts.pending_approval || 0})` },
              { id: "sent", label: `Sent (${counts.sent || 0})` },
            ].map((f) => (
              <button
                key={f.id}
                type="button"
                className={`pill-tab ${statusFilter === f.id ? "active" : ""}`}
                onClick={() => setStatusFilter(f.id)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="nudge-grid">
        {!filtered.length ? <p className="dim">No nudges in this slice.</p> : null}
        {filtered.map((n) => {
          const meta = STATUS_META[n.status] || STATUS_META.scheduled;
          return (
            <div key={n.id} className="nudge-card glass-normal">
              <div className="nudge-card-top">
                <div className="chat-avatar">{initials(n.customer_name)}</div>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div className="nudge-card-name">{n.customer_name}</div>
                  <div className="chat-sub">{n.shipment_ref} - {n.rule_label}</div>
                </div>
                <span className={`badge ${meta.cls}`}>{meta.label}</span>
              </div>
              <div className="nudge-trigger">
                <span className="run-draft-label">Trigger</span>
                <p>{n.trigger}</p>
              </div>
              <div className="nudge-draft">
                <span className="run-draft-label">Draft on WhatsApp</span>
                <p>{n.draft}</p>
              </div>
              <div className="nudge-foot">
                <span>{n.status === "sent" ? `Sent ${fmtRelative(n.scheduled_at)}` : `Scheduled ${fmtTime(n.scheduled_at)}`}</span>
                <div className="row">
                  <button type="button" className="btn-ghost btn-small" onClick={() => onOpenInbox(n.customer_id)}>Thread</button>
                  {n.status !== "sent" && n.status !== "cancelled" ? (
                    <>
                      <button type="button" className="btn-primary btn-small" disabled={busyId === n.id} onClick={() => send(n.id)}>
                        Send now
                      </button>
                      <button type="button" className="btn-brick btn-small" disabled={busyId === n.id} onClick={() => cancel(n.id)}>
                        Cancel
                      </button>
                    </>
                  ) : null}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
