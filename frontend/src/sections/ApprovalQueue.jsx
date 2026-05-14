import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { fmtTime, fmtRelative, initials, intentLabel } from "../utils";

const STATUS_META = {
  pending:  { label: "Pending",  cls: "badge-warn" },
  approved: { label: "Approved", cls: "badge-ok" },
  edited:   { label: "Edited & sent", cls: "badge-ok" },
  rejected: { label: "Rejected", cls: "badge-err" },
};

export function ApprovalQueue({ approvals, shipments, customers, onAction, onOpenInbox }) {
  const [filter, setFilter] = useState("pending");
  const [selectedId, setSelectedId] = useState(null);
  const [editText, setEditText] = useState("");
  const [busy, setBusy] = useState(false);

  const filtered = useMemo(
    () => (filter === "all" ? approvals : approvals.filter((a) => a.status === filter)),
    [approvals, filter]
  );

  const selected = useMemo(
    () => approvals.find((a) => a.id === selectedId) || filtered[0] || null,
    [approvals, filtered, selectedId]
  );

  useEffect(() => {
    if (selected) setEditText(selected.draft_reply);
  }, [selected?.id]);

  useEffect(() => {
    if (!selectedId && filtered[0]) setSelectedId(filtered[0].id);
  }, [filtered, selectedId]);

  const shipment = useMemo(
    () => (selected?.shipment_ref ? shipments.find((s) => s.ref === selected.shipment_ref) : null),
    [shipments, selected]
  );
  const customer = useMemo(
    () => (selected ? customers.find((c) => c.id === selected.customer_id) : null),
    [customers, selected]
  );

  async function decide(kind) {
    if (!selected || busy) return;
    setBusy(true);
    try {
      await api.decideApproval(selected.id, kind, kind === "edit" ? editText : undefined);
      await onAction();
    } finally {
      setBusy(false);
    }
  }

  const counts = useMemo(() => {
    const c = { pending: 0, approved: 0, edited: 0, rejected: 0 };
    approvals.forEach((a) => { c[a.status] = (c[a.status] || 0) + 1; });
    return c;
  }, [approvals]);

  const draftChanged = selected && editText.trim() !== selected.draft_reply.trim();

  return (
    <div className="approval-layout">
      <div className="approval-list glass-normal">
        <div className="table-controls">
          <div className="inbox-filters">
            {[
              { id: "pending", label: `Pending (${counts.pending || 0})` },
              { id: "approved", label: `Approved (${counts.approved || 0})` },
              { id: "edited", label: `Edited (${counts.edited || 0})` },
              { id: "rejected", label: `Rejected (${counts.rejected || 0})` },
              { id: "all", label: `All (${approvals.length})` },
            ].map((f) => (
              <button
                key={f.id}
                type="button"
                className={`pill-tab ${filter === f.id ? "active" : ""}`}
                onClick={() => setFilter(f.id)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
        <div className="approval-rows">
          {!filtered.length ? <p className="dim" style={{ padding: 14 }}>No drafts in this bucket.</p> : null}
          {filtered.map((a) => (
            <button
              key={a.id}
              type="button"
              className={`approval-card ${selected?.id === a.id ? "active" : ""}`}
              onClick={() => setSelectedId(a.id)}
            >
              <div className="approval-card-top">
                <div className="chat-avatar">{initials(a.customer_name)}</div>
                <div>
                  <div className="approval-card-name">{a.customer_name}</div>
                  <div className="approval-card-sub">{a.customer_tier} - {intentLabel(a.intent)} {a.shipment_ref ? `- ${a.shipment_ref}` : ""}</div>
                </div>
                <span className="spacer" />
                <span className={`badge ${STATUS_META[a.status].cls}`}>{STATUS_META[a.status].label}</span>
              </div>
              <p className="approval-card-customer">"{a.customer_text}"</p>
              <p className="approval-card-draft">{a.draft_reply}</p>
              <div className="approval-card-foot">
                <span>{fmtRelative(a.created_at)}</span>
                <span>Confidence {Math.round(a.confidence * 100)}%</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      <aside className="approval-detail glass-normal">
        {selected ? (
          <>
            <div className="approval-detail-head">
              <div>
                <h3 style={{ margin: 0 }}>{selected.customer_name}</h3>
                <div className="chat-sub">
                  {selected.customer_tier} tier - {intentLabel(selected.intent)}{selected.shipment_ref ? ` - ${selected.shipment_ref}` : ""}
                </div>
              </div>
              <span className={`badge ${STATUS_META[selected.status].cls}`}>{STATUS_META[selected.status].label}</span>
            </div>

            <div className="context-block">
              <h4>Why the supervisor held this</h4>
              <p className="detail-reason">{selected.reason_for_review}</p>
              <p className="dim" style={{ fontSize: 12, margin: "4px 0 0" }}>
                The customer has already received an acknowledgment - this is just the follow-up draft.
              </p>
            </div>

            <div className="context-block">
              <h4>Customer said</h4>
              <div className="customer-quote">"{selected.customer_text}"</div>
            </div>

            <div className="context-block">
              <h4>Agent draft (edit if needed)</h4>
              <textarea
                rows={5}
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                disabled={selected.status !== "pending"}
                style={{ width: "100%" }}
              />
            </div>

            {shipment ? (
              <div className="context-block">
                <h4>Grounded tracking data</h4>
                <div className="context-card">
                  <div className="row">
                    <span className="context-ref">{shipment.ref}</span>
                    <span className="spacer" />
                    <span className="badge badge-muted">{shipment.mode}</span>
                  </div>
                  <span className="context-route">{shipment.origin} &rarr; {shipment.destination}</span>
                  <div className="context-row"><span>Last event</span><strong>{shipment.last_event_label}</strong></div>
                  <div className="context-row"><span>ETA</span><strong>{fmtTime(shipment.eta)}</strong></div>
                  <div className="cite-row">from tracking @ {fmtTime(shipment.last_event_at)}</div>
                </div>
              </div>
            ) : null}

            {selected.status === "pending" ? (
              <div className="detail-actions">
                <button
                  type="button"
                  className="btn-primary btn-small"
                  disabled={busy}
                  onClick={() => decide(draftChanged ? "edit" : "approve")}
                >
                  {draftChanged ? "Save edits & send" : "Approve & send"}
                </button>
                <button type="button" className="btn-brick btn-small" disabled={busy} onClick={() => decide("reject")}>
                  Reject
                </button>
                {customer ? (
                  <button type="button" className="btn-ghost btn-small" onClick={() => onOpenInbox(customer.id)}>
                    Open thread
                  </button>
                ) : null}
              </div>
            ) : (
              <div className="detail-actions">
                {customer ? (
                  <button type="button" className="btn-ghost btn-small" onClick={() => onOpenInbox(customer.id)}>
                    Open thread
                  </button>
                ) : null}
              </div>
            )}
          </>
        ) : (
          <p className="dim">No drafts. Agent caught up.</p>
        )}
      </aside>
    </div>
  );
}
