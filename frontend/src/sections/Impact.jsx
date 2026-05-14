import { fmtRelative, intentLabel } from "../utils";

export function Impact({ kpis, agentActions, tickets, nudges }) {
  const pendingTickets = tickets.filter((t) => t.status !== "resolved").slice(0, 5);
  const recentClarifications = agentActions.filter((a) => a.kind === "clarify_asked").slice(0, 5);
  const nudgesQueued = nudges.filter((n) => n.status !== "sent" && n.status !== "cancelled").slice(0, 5);

  return (
    <div className="stack">
      <div className="kpi-grid">
        <Kpi label="Messages handled" value={kpis.messages_handled} sub="this dataset" />
        <Kpi label="Auto-sent by agent" value={kpis.auto_resolved} sub={`Deflection ${Math.round((kpis.deflection_rate || 0) * 100)}%`} />
        <Kpi label="Clarifications open" value={kpis.clarifications_open} sub="multi-shipment disambiguation" accent />
        <Kpi label="Escalations" value={kpis.pending_handoffs} sub="to human" accent />
        <Kpi label="Proactive nudges sent" value={kpis.nudges_sent} sub={`${kpis.nudges_queued || 0} queued`} />
        <Kpi label="Hours saved" value={kpis.fte_hours_saved} sub={`${kpis.minutes_saved || 0} min minion work replaced`} />
      </div>

      <div className="impact-grid">
        <div className="card glass-normal">
          <h3>What the agent just did</h3>
          <p className="card-sub">Recent actions across inbox, clarifications, nudges, and escalations.</p>
          <div className="activity-feed">
            {agentActions.slice(0, 20).map((a) => (
              <div key={a.id} className="activity-item">
                <div className={`activity-icon ${iconClass(a.kind)}`}>{iconGlyph(a.kind)}</div>
                <div className="activity-body">
                  <strong>{actionLabel(a.kind)} - {intentLabel(a.intent)}</strong>
                  <p>{a.summary}</p>
                  <span className="activity-time">{fmtRelative(a.timestamp)}</span>
                </div>
              </div>
            ))}
            {!agentActions.length ? <p className="dim">No activity yet.</p> : null}
          </div>
        </div>

        <div className="stack">
          <div className="card glass-normal">
            <h3>Clarifications waiting</h3>
            <p className="card-sub">Threads where triage asked the customer to pick a shipment.</p>
            <div className="scroll-list">
              {recentClarifications.length ? recentClarifications.map((a) => (
                <div key={a.id} className="context-card" style={{ marginBottom: 8 }}>
                  <div className="row">
                    <span className="context-ref">{a.customer_id}</span>
                    <span className="spacer" />
                    <span className="badge badge-info">Awaiting choice</span>
                  </div>
                  <div className="context-sub">{intentLabel(a.intent)} {a.shipment_ref ? `- ${a.shipment_ref}` : ""}</div>
                  <p className="impact-quote">{a.summary}</p>
                </div>
              )) : <p className="dim">No open clarifications.</p>}
            </div>
          </div>

          <div className="card glass-normal">
            <h3>Escalations open</h3>
            <div className="scroll-list">
              {pendingTickets.length ? pendingTickets.map((t) => (
                <div key={t.id} className="context-card" style={{ marginBottom: 8 }}>
                  <div className="row">
                    <span className="context-ref">{t.id}</span>
                    <span className="spacer" />
                    <span className="badge badge-warn">{t.category}</span>
                  </div>
                  <div className="context-sub">{t.customer_name} {t.shipment_ref ? `- ${t.shipment_ref}` : ""}</div>
                  <p className="impact-quote">{t.text}</p>
                </div>
              )) : <p className="dim">None open.</p>}
            </div>
          </div>

          <div className="card glass-normal">
            <h3>Next nudges</h3>
            <div className="scroll-list">
              {nudgesQueued.length ? nudgesQueued.map((n) => (
                <div key={n.id} className="context-card" style={{ marginBottom: 8 }}>
                  <div className="row">
                    <span className="context-ref">{n.rule_label}</span>
                    <span className="spacer" />
                    <span className="badge badge-info">{n.shipment_ref}</span>
                  </div>
                  <p className="impact-quote">{n.draft}</p>
                </div>
              )) : <p className="dim">Nothing scheduled.</p>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function actionLabel(kind) {
  if (kind === "auto_reply") return "Auto-reply";
  if (kind === "handoff_ack") return "Handoff ack";
  if (kind === "escalated") return "Escalated";
  if (kind === "clarify_asked") return "Clarify asked";
  if (kind === "nudge_sent") return "Nudge sent";
  return kind;
}
function iconGlyph(kind) {
  if (kind === "auto_reply") return "A";
  if (kind === "nudge_sent") return "N";
  if (kind === "clarify_asked") return "?";
  return "!";
}
function iconClass(kind) {
  if (kind === "auto_reply" || kind === "nudge_sent") return "auto";
  return "esc";
}

function Kpi({ label, value, sub, accent }) {
  return (
    <div className={`kpi-card glass-normal ${accent ? "accent" : ""}`}>
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value ?? "-"}</span>
      {sub ? <span className="kpi-sub">{sub}</span> : null}
    </div>
  );
}
