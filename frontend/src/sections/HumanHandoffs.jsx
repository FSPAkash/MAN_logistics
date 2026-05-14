import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { fmtRelative, intentLabel } from "../utils";

function slaLabel(dueIso, status) {
  if (!dueIso || status === "resolved") return null;
  const due = new Date(dueIso).getTime();
  const now = Date.now();
  const diffMin = Math.round((due - now) / 60000);
  if (diffMin < 0) {
    const hrs = Math.round(-diffMin / 60);
    return { tone: "err", text: hrs >= 1 ? `Breached ${hrs}h ago` : `Breached ${-diffMin}m ago` };
  }
  if (diffMin < 60) return { tone: "warn", text: `Due in ${diffMin}m` };
  const hrs = Math.round(diffMin / 60);
  return { tone: "info", text: `Due in ${hrs}h` };
}

function statusBadgeClass(status) {
  if (status === "resolved") return "badge-ok";
  if (status === "in_progress") return "badge-info";
  return "badge-warn";
}

export function HumanHandoffs({ tickets, agentConfig, onAction }) {
  const [departments, setDepartments] = useState([]);
  const [activeDept, setActiveDept] = useState(null);
  const [selectedTicketId, setSelectedTicketId] = useState(null);
  const [filter, setFilter] = useState("open"); // open | all | mine (mine not wired without auth)
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function refreshDepts() {
    try {
      const d = await api.departments();
      setDepartments(d.items || []);
      if (!activeDept && d.items?.length) setActiveDept(d.items[0].id);
    } catch (e) {
      setErr(e.message || "Failed to load departments");
    }
  }

  useEffect(() => { refreshDepts(); /* eslint-disable-next-line */ }, []);
  useEffect(() => { refreshDepts(); /* eslint-disable-next-line */ }, [agentConfig?.version]);

  const deptMap = useMemo(() => {
    const m = {};
    departments.forEach((d) => { m[d.id] = d; });
    return m;
  }, [departments]);

  const fallbackId = agentConfig?.fallback_department || departments[0]?.id;

  const byDept = useMemo(() => {
    const out = {};
    departments.forEach((d) => { out[d.id] = []; });
    tickets.forEach((t) => {
      const did = t.department_id || fallbackId;
      if (!out[did]) out[did] = [];
      out[did].push(t);
    });
    Object.keys(out).forEach((did) => {
      out[did].sort((a, b) => {
        const statusRank = { pending: 0, in_progress: 1, resolved: 2 };
        const sa = statusRank[a.status] ?? 0;
        const sb = statusRank[b.status] ?? 0;
        if (sa !== sb) return sa - sb;
        return (a.sla_due_at || "").localeCompare(b.sla_due_at || "");
      });
    });
    return out;
  }, [tickets, departments, fallbackId]);

  const effectiveActive = activeDept && deptMap[activeDept] ? activeDept : departments[0]?.id;
  const ticketsForDept = (byDept[effectiveActive] || []).filter((t) => filter === "all" ? true : t.status !== "resolved");
  const selectedTicket = ticketsForDept.find((t) => t.id === selectedTicketId) || ticketsForDept[0] || null;

  async function assignMember(ticketId, assigneeId) {
    setBusy(true); setErr("");
    try {
      await api.assignTicket(ticketId, { assignee_id: assigneeId || null });
      if (onAction) await onAction();
      await refreshDepts();
    } catch (e) {
      setErr(e.message || "Assign failed");
    } finally {
      setBusy(false);
    }
  }

  async function reroute(ticketId, deptId) {
    setBusy(true); setErr("");
    try {
      await api.assignTicket(ticketId, { department_id: deptId });
      if (onAction) await onAction();
      await refreshDepts();
    } catch (e) {
      setErr(e.message || "Reroute failed");
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(ticketId, status) {
    setBusy(true); setErr("");
    try {
      await api.setTicketStatus(ticketId, status);
      if (onAction) await onAction();
      await refreshDepts();
    } catch (e) {
      setErr(e.message || "Status update failed");
    } finally {
      setBusy(false);
    }
  }

  async function agentDraft(ticketId) {
    setBusy(true); setErr("");
    try {
      await api.agentReplyTicket(ticketId);
      if (onAction) await onAction();
      await refreshDepts();
    } catch (e) {
      setErr(e.message || "Agent reply failed");
    } finally {
      setBusy(false);
    }
  }

  async function sendReply(ticketId, text) {
    setBusy(true); setErr("");
    try {
      await api.replyTicket(ticketId, text);
      if (onAction) await onAction();
      await refreshDepts();
    } catch (e) {
      setErr(e.message || "Send failed");
    } finally {
      setBusy(false);
    }
  }

  if (!departments.length) {
    return <p className="dim">Loading departments...</p>;
  }

  return (
    <div className="handoffs-layout">
      <aside className="handoffs-rail">
        <div className="row" style={{ gap: 6, marginBottom: 8 }}>
          <button
            type="button"
            className={`btn-tab ${filter === "open" ? "on" : ""}`}
            onClick={() => setFilter("open")}
          >Open</button>
          <button
            type="button"
            className={`btn-tab ${filter === "all" ? "on" : ""}`}
            onClick={() => setFilter("all")}
          >All</button>
        </div>
        {departments.map((d) => {
          const c = d.counts || {};
          const open = (c.pending || 0) + (c.in_progress || 0);
          return (
            <button
              key={d.id}
              type="button"
              className={`dept-tab ${effectiveActive === d.id ? "active" : ""}`}
              onClick={() => { setActiveDept(d.id); setSelectedTicketId(null); }}
            >
              <div className="dept-tab-head">
                <strong>{d.name}</strong>
                <span className="dept-count">{open}</span>
              </div>
              <div className="dept-tab-sub">
                {c.sla_breached ? <span className="badge badge-err">{c.sla_breached} breached</span> : null}
                <span className="dim" style={{ fontSize: 11 }}>{d.members?.length || 0} on team - SLA {d.sla_hours}h</span>
              </div>
            </button>
          );
        })}
      </aside>

      <section className="handoffs-queue">
        <header className="queue-head">
          <div>
            <h3>{deptMap[effectiveActive]?.name || "Queue"}</h3>
            <p className="card-sub">{deptMap[effectiveActive]?.description}</p>
          </div>
        </header>
        {err ? <p className="info-banner error">{err}</p> : null}
        <div className="queue-list">
          {ticketsForDept.length === 0 ? <p className="dim">No tickets in this queue.</p> : null}
          {ticketsForDept.map((t) => {
            const sla = slaLabel(t.sla_due_at, t.status);
            return (
              <button
                key={t.id}
                type="button"
                className={`queue-item ${selectedTicket?.id === t.id ? "active" : ""}`}
                onClick={() => setSelectedTicketId(t.id)}
              >
                <div className="row">
                  <span className="queue-ref">{t.shipment_ref || t.id}</span>
                  <span className={`badge ${statusBadgeClass(t.status)}`}>{t.status.replace("_", " ")}</span>
                  <span className="spacer" />
                  {sla ? <span className={`badge badge-${sla.tone}`}>{sla.text}</span> : null}
                </div>
                <div className="queue-item-body">
                  <strong>{t.customer_name}</strong>
                  <span className="dim"> - {intentLabel(t.intent)}</span>
                </div>
                <p className="queue-text">{t.text}</p>
                <div className="row queue-meta">
                  <span className="dim">{fmtRelative(t.timestamp)}</span>
                  <span className="spacer" />
                  {t.assignee ? <span className="badge badge-muted">{t.assignee.name}</span> : <span className="badge badge-warn">Unassigned</span>}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      <section className="handoffs-detail">
        {selectedTicket ? (
          <TicketDetail
            ticket={selectedTicket}
            departments={departments}
            busy={busy}
            onAssign={(mid) => assignMember(selectedTicket.id, mid)}
            onReroute={(did) => reroute(selectedTicket.id, did)}
            onStatus={(s) => setStatus(selectedTicket.id, s)}
            onAgentDraft={() => agentDraft(selectedTicket.id)}
            onSend={(text) => sendReply(selectedTicket.id, text)}
          />
        ) : (
          <p className="dim">Select a ticket to work it.</p>
        )}
      </section>
    </div>
  );
}

function TicketDetail({ ticket, departments, busy, onAssign, onReroute, onStatus, onAgentDraft, onSend }) {
  const [replyText, setReplyText] = useState("");
  const dept = departments.find((d) => d.id === ticket.department_id) || departments[0];
  const sla = slaLabel(ticket.sla_due_at, ticket.status);
  const isResolved = ticket.status === "resolved";

  useEffect(() => { setReplyText(""); }, [ticket.id]);

  return (
    <div className="stack">
      <div className="card glass-normal">
        <div className="row">
          <strong>{ticket.shipment_ref || ticket.id}</strong>
          <span className="spacer" />
          <span className={`badge ${statusBadgeClass(ticket.status)}`}>{ticket.status.replace("_", " ")}</span>
          {sla ? <span className={`badge badge-${sla.tone}`}>{sla.text}</span> : null}
        </div>
        <p className="card-sub" style={{ marginTop: 4 }}>
          {ticket.customer_name} - {intentLabel(ticket.intent)}{ticket.category ? ` - ${ticket.category}` : ""}
        </p>
        <p className="impact-quote" style={{ marginTop: 8 }}>{ticket.text}</p>
        {ticket.handoff_note ? (
          <p className="dim" style={{ fontSize: 12, marginTop: 6 }}>Handoff note: {ticket.handoff_note}</p>
        ) : null}
        {ticket.supervisor_note ? (
          <p className="dim" style={{ fontSize: 12 }}>Supervisor: {ticket.supervisor_note}</p>
        ) : null}
      </div>

      <div className="card glass-normal">
        <h4>Routing</h4>
        <div className="detail-row">
          <label>Department</label>
          <select
            value={ticket.department_id || ""}
            onChange={(e) => onReroute(e.target.value)}
            disabled={busy || isResolved}
          >
            {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </div>
        <div className="detail-row">
          <label>Assignee</label>
          <select
            value={ticket.assignee?.id || ""}
            onChange={(e) => onAssign(e.target.value)}
            disabled={busy || isResolved}
          >
            <option value="">Unassigned</option>
            {(dept?.members || []).map((m) => (
              <option key={m.id} value={m.id}>{m.name}{m.role ? ` - ${m.role}` : ""}</option>
            ))}
          </select>
        </div>
        <div className="row" style={{ gap: 8, marginTop: 8, flexWrap: "wrap" }}>
          <button type="button" className="btn-ghost btn-small" onClick={() => onStatus("pending")} disabled={busy || ticket.status === "pending"}>Mark pending</button>
          <button type="button" className="btn-ghost btn-small" onClick={() => onStatus("in_progress")} disabled={busy || ticket.status === "in_progress"}>Mark in progress</button>
          <button type="button" className="btn-primary btn-small" onClick={() => onStatus("resolved")} disabled={busy || isResolved}>Mark resolved</button>
        </div>
      </div>

      <div className="card glass-normal">
        <h4>Reply to customer</h4>
        <textarea
          className="reply-box"
          rows={4}
          placeholder="Write a reply, or click 'Draft from agent' to let the resolver propose one."
          value={replyText}
          onChange={(e) => setReplyText(e.target.value)}
          disabled={busy || isResolved}
        />
        <div className="row" style={{ gap: 8, marginTop: 8 }}>
          <button type="button" className="btn-ghost btn-small" onClick={onAgentDraft} disabled={busy || isResolved}>Draft from agent</button>
          <span className="spacer" />
          <button
            type="button"
            className="btn-primary btn-small"
            onClick={() => { if (replyText.trim()) onSend(replyText.trim()); }}
            disabled={busy || isResolved || !replyText.trim()}
          >
            Send &amp; resolve
          </button>
        </div>
      </div>
    </div>
  );
}
