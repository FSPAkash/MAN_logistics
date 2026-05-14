import { useMemo, useState } from "react";
import { fmtTime, initials, intentLabel } from "../utils";
import { AGENT_LABEL, DECISION_BADGE, DECISION_LABEL, STAGE_DECISION_LABEL } from "../theme";

const STATE_META = {
  auto:     { label: "Auto-sent",    cls: "badge-ok" },
  escalate: { label: "Escalated",    cls: "badge-warn" },
  idle:     { label: "Idle",         cls: "badge-muted" },
};

export function AgentInbox({ customers, shipments, tickets, lastResult, onOpenPhone }) {
  const [selectedId, setSelectedId] = useState(customers[0]?.id || "");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");

  const customerState = useMemo(() => {
    const map = new Map();
    customers.forEach((c) => {
      if (tickets.some((t) => t.customer_id === c.id && t.status === "pending")) {
        map.set(c.id, "escalate");
      } else if (c.active_shipments > 0) {
        map.set(c.id, "auto");
      } else {
        map.set(c.id, "idle");
      }
    });
    return map;
  }, [customers, tickets]);

  const filteredCustomers = useMemo(() => {
    const q = search.trim().toLowerCase();
    let base = customers;
    if (filter !== "all") {
      base = base.filter((c) => customerState.get(c.id) === filter);
    }
    if (!q) return base;
    return base.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        (c.contact_person || "").toLowerCase().includes(q) ||
        (c.country || "").toLowerCase().includes(q)
    );
  }, [customers, search, filter, customerState]);

  const selected = customers.find((c) => c.id === selectedId) || null;
  const customerShipments = useMemo(
    () => shipments.filter((s) => s.customer_id === selectedId).sort((a, b) => new Date(b.last_event_at) - new Date(a.last_event_at)),
    [shipments, selectedId]
  );

  const openTicket = useMemo(
    () => tickets.find((t) => t.customer_id === selectedId && t.status !== "resolved"),
    [tickets, selectedId]
  );

  function lastPreview(c) { return `${c.tier} tier - ${c.active_shipments} active`; }
  function lastTime(c) { return c.country; }

  const counts = useMemo(() => {
    const out = { all: customers.length, auto: 0, escalate: 0, idle: 0 };
    customers.forEach((c) => { out[customerState.get(c.id)] = (out[customerState.get(c.id)] || 0) + 1; });
    return out;
  }, [customers, customerState]);

  return (
    <div className="comms-layout">
      <aside className="chat-list glass-normal">
        <div className="chat-list-head">
          <h3>Conversations</h3>
          <span className="badge badge-info">{filteredCustomers.length}</span>
        </div>
        <div className="inbox-filters">
          {[
            { id: "all", label: `All (${counts.all})` },
            { id: "escalate", label: `Escalated (${counts.escalate || 0})` },
            { id: "auto", label: `Auto (${counts.auto || 0})` },
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
        <div className="chat-list-search">
          <input
            type="search"
            placeholder="Search by name, contact, country..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="chat-list-rows">
          {filteredCustomers.map((c) => {
            const state = customerState.get(c.id) || "idle";
            const meta = STATE_META[state];
            return (
              <button
                key={c.id}
                type="button"
                className={`chat-row ${selectedId === c.id ? "active" : ""}`}
                onClick={() => setSelectedId(c.id)}
              >
                <div className="chat-avatar">{initials(c.name)}</div>
                <div className="chat-row-body">
                  <div className="chat-row-top">
                    <span className="chat-row-name">{c.name}</span>
                    <span className="chat-row-time">{lastTime(c)}</span>
                  </div>
                  <span className="chat-row-preview">{lastPreview(c)}</span>
                  <div className="chat-row-tags">
                    <span className={`badge ${meta.cls}`}>{meta.label}</span>
                    <span className="badge badge-muted">{c.tier}</span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </aside>

      <section className="comms-context glass-normal inbox-detail">
        <header className="inbox-detail-head">
          <div>
            <h3 style={{ margin: 0 }}>{selected?.name || "Pick a conversation"}</h3>
            <div className="chat-sub">
              {selected
                ? `${selected.contact_person} - ${selected.email} - ${selected.tier}`
                : "WhatsApp channel"}
            </div>
          </div>
          <div className="row">
            {openTicket ? <span className="badge badge-warn">Escalated - {intentLabel(openTicket.intent)}</span> : null}
            <span className="agent-pill"><span className="dot" />Agent on</span>
            <button type="button" className="btn-primary btn-small" onClick={onOpenPhone}>
              Open Customer Phone
            </button>
          </div>
        </header>

        <div className="context-block">
          <h4>Last agent decision</h4>
          {lastResult ? (
            <LastRunCard result={lastResult} />
          ) : (
            <p className="dim" style={{ fontSize: 12 }}>
              Send a message from the floating Customer Phone to see how the agent classifies, grounds, and routes it.
            </p>
          )}
        </div>

        <div className="context-block">
          <h4>Tracking data the agent reads</h4>
          {customerShipments.length ? (
            <>
              {customerShipments.slice(0, 1).map((s) => (
                <div key={s.id} className="context-card context-card-primary">
                  <div className="row">
                    <span className="context-ref">{s.ref}</span>
                    <span className="spacer" />
                    <span className="badge badge-muted">{s.mode}</span>
                  </div>
                  <span className="context-route">{s.origin} &rarr; {s.destination}</span>
                  <div className="context-row"><span>Last event</span><strong>{s.last_event_label}</strong></div>
                  <div className="context-row"><span>ETA</span><strong>{fmtTime(s.eta)}</strong></div>
                  {s.delay_reason ? (
                    <div className="context-row" style={{ color: "var(--brick-700)" }}>
                      <span>Delay</span><strong>{s.delay_reason}</strong>
                    </div>
                  ) : null}
                  <div className="cite-row">from tracking @ {fmtTime(s.last_event_at)}</div>
                </div>
              ))}
              {customerShipments.length > 1 ? (
                <div className="ship-more-row">
                  {customerShipments.slice(1, 5).map((s) => (
                    <span key={s.id} className="ship-more-chip">{s.ref}</span>
                  ))}
                  {customerShipments.length > 5 ? (
                    <span className="ship-more-chip dim">+{customerShipments.length - 5}</span>
                  ) : null}
                </div>
              ) : null}
            </>
          ) : (
            <p className="dim" style={{ fontSize: 12 }}>No shipments on file. Agent will reply generally.</p>
          )}
        </div>
      </section>
    </div>
  );
}

function LastRunCard({ result }) {
  const { message, reply, ticket, pipeline = [], decision = "auto_send" } = result;
  return (
    <div className="context-card">
      <div className="row">
        <span className={`badge ${DECISION_BADGE[decision] || "badge-muted"}`}>{DECISION_LABEL[decision] || decision}</span>
        <span className="spacer" />
        <span className="badge badge-muted">{intentLabel(message?.intent)}</span>
      </div>
      <div className="context-row"><span>Confidence</span><strong>{Math.round((message?.confidence || 0) * 100)}%</strong></div>
      {pipeline.length ? (
        <div className="pipeline-mini">
          {pipeline.map((st, i) => (
            <div key={i} className={`pipeline-mini-row stage-${st.agent}`}>
              <span className="pipeline-agent">{AGENT_LABEL[st.agent] || st.agent}</span>
              <span className="pipeline-mini-dec">{STAGE_DECISION_LABEL[st.decision] || st.decision}</span>
            </div>
          ))}
        </div>
      ) : null}
      {reply ? (
        <div className="run-draft">
          <span className="run-draft-label">Sent on WhatsApp</span>
          <p>{reply.text}</p>
        </div>
      ) : null}
      {ticket ? (
        <p className="dim" style={{ fontSize: 12, margin: "6px 0 0" }}>
          Handoff ticket {ticket.id} opened for ops. Customer already acknowledged.
        </p>
      ) : null}
    </div>
  );
}
