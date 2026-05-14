import { useMemo, useState } from "react";
import { fmtTime, intentLabel } from "../utils";
import { AGENT_LABEL, DECISION_BADGE, DECISION_LABEL, STAGE_DECISION_LABEL } from "../theme";

export function AgentRuns({ runs, customers, onOpenInbox }) {
  const [filter, setFilter] = useState("all");
  const [selectedId, setSelectedId] = useState(runs[0]?.id || null);

  const filtered = useMemo(
    () => (filter === "all" ? runs : runs.filter((r) => r.decision === filter)),
    [runs, filter]
  );

  const selected = useMemo(
    () => runs.find((r) => r.id === selectedId) || filtered[0] || null,
    [runs, filtered, selectedId]
  );

  const customer = selected ? customers.find((c) => c.id === selected.customer_id) : null;

  const counts = useMemo(() => {
    const c = { auto_send: 0, clarify: 0, escalate: 0 };
    runs.forEach((r) => { c[r.decision] = (c[r.decision] || 0) + 1; });
    return c;
  }, [runs]);

  return (
    <div className="runs-layout">
      <div className="runs-list glass-normal">
        <div className="inbox-filters" style={{ padding: 12 }}>
          {[
            { id: "all", label: `All (${runs.length})` },
            { id: "auto_send", label: `Auto (${counts.auto_send || 0})` },
            { id: "clarify", label: `Clarify (${counts.clarify || 0})` },
            { id: "escalate", label: `Escalate (${counts.escalate || 0})` },
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
        <div className="runs-rows">
          {filtered.map((r) => (
            <button
              key={r.id}
              type="button"
              className={`run-row ${selected?.id === r.id ? "active" : ""}`}
              onClick={() => setSelectedId(r.id)}
            >
              <div className="row">
                <span className="run-key">{r.id}</span>
                <span className="spacer" />
                <span className={`badge ${DECISION_BADGE[r.decision] || "badge-muted"}`}>{DECISION_LABEL[r.decision] || r.decision}</span>
              </div>
              <div className="run-row-name">{r.customer_name}</div>
              <div className="run-row-sub">
                {intentLabel(r.intent)} - {Math.round(r.confidence * 100)}% {r.shipment_ref ? `- ${r.shipment_ref}` : ""}
              </div>
              <div className="run-row-time">{fmtTime(r.timestamp)}</div>
            </button>
          ))}
          {!filtered.length ? <p className="dim" style={{ padding: 14 }}>No runs.</p> : null}
        </div>
      </div>

      <aside className="run-detail glass-normal">
        {selected ? (
          <>
            <div className="run-detail-head">
              <div>
                <h3 style={{ margin: 0 }}>{selected.id}</h3>
                <div className="chat-sub">{selected.customer_name} - {fmtTime(selected.timestamp)}</div>
              </div>
              <span className={`badge ${DECISION_BADGE[selected.decision] || "badge-muted"}`}>{DECISION_LABEL[selected.decision] || selected.decision}</span>
            </div>

            <div className="run-kpi-row">
              <div className="run-kpi"><span>Intent</span><strong>{intentLabel(selected.intent)}</strong></div>
              <div className="run-kpi"><span>Confidence</span><strong>{Math.round(selected.confidence * 100)}%</strong></div>
              <div className="run-kpi"><span>Latency</span><strong>{selected.latency_ms} ms</strong></div>
              <div className="run-kpi"><span>Stages</span><strong>{(selected.pipeline || []).length}</strong></div>
            </div>

            <div className="context-block">
              <h4>Pipeline trace</h4>
              <div className="pipeline-stack">
                {(selected.pipeline || []).map((st, i) => (
                  <div key={i} className={`pipeline-stage stage-${st.agent}`}>
                    <div className="pipeline-head">
                      <span className="pipeline-agent">{AGENT_LABEL[st.agent] || st.agent} agent</span>
                      <span className="spacer" />
                      <span className="badge badge-muted">{STAGE_DECISION_LABEL[st.decision] || st.decision}</span>
                      <span className="dim" style={{ fontSize: 11, marginLeft: 8 }}>{st.latency_ms} ms</span>
                    </div>
                    <p className="pipeline-reason">{st.reasoning}</p>
                    {st.tool_calls?.length ? (
                      <div className="tool-stack pipeline-tools">
                        {st.tool_calls.map((t, j) => (
                          <div key={j} className="tool-call">
                            <div className="row">
                              <code>{t.tool}</code>
                              <span className="spacer" />
                              <span className={`badge ${t.ok ? "badge-ok" : "badge-warn"}`}>{t.ok ? "ok" : "fail"}</span>
                              <span className="dim" style={{ fontSize: 11, marginLeft: 8 }}>{t.latency_ms} ms</span>
                            </div>
                            <div className="tool-args">args: {JSON.stringify(t.args)}</div>
                            <div className="tool-result">&rarr; {t.result_summary}</div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {st.output?.ask ? (
                      <div className="pipeline-output">
                        <span className="run-draft-label">Clarifying question sent</span>
                        <p>{st.output.ask}</p>
                      </div>
                    ) : null}
                    {st.output?.draft ? (
                      <div className="pipeline-output">
                        <span className="run-draft-label">Draft</span>
                        <p>{st.output.draft}</p>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>

            {selected.grounded_fields?.length ? (
              <div className="context-block">
                <h4>Fields the reply is grounded in</h4>
                <div className="row" style={{ flexWrap: "wrap" }}>
                  {selected.grounded_fields.map((f) => <span key={f} className="badge badge-info">{f}</span>)}
                </div>
              </div>
            ) : null}

            {customer ? (
              <div className="detail-actions">
                <button type="button" className="btn-ghost btn-small" onClick={() => onOpenInbox(customer.id)}>
                  Open conversation
                </button>
              </div>
            ) : null}
          </>
        ) : (
          <p className="dim">Pick a run.</p>
        )}
      </aside>
    </div>
  );
}
