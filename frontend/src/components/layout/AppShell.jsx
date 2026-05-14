import { useState } from "react";
import { NAV_ITEMS } from "../../theme";

export function AppShell({
  active,
  onActiveChange,
  generatedAt,
  seedInput,
  onSeedInput,
  onReseed,
  onLogout,
  kpis,
  agentConfig,
  children,
}) {
  const [collapsed, setCollapsed] = useState(false);
  const generatedLabel = generatedAt ? new Date(generatedAt).toLocaleString() : "Loading...";
  const agentPillLabel =
    agentConfig?.backend === "openai"
      ? `AI - ${agentConfig?.classify_model || "gpt-4o-mini"}`
      : "Agent live";

  return (
    <div className="app-root" data-section={active}>
      <div className="aurora-wrap" aria-hidden>
        <div className="mesh mesh-1" />
        <div className="mesh mesh-2" />
        <div className="mesh mesh-3" />
        <div className="mesh mesh-4" />
        <div className="mesh mesh-5" />
        <div className="mesh mesh-6" />
      </div>

      <div className="app-shell-frame">
        <header className="top-bar glass-strong">
          <div className="brand-wrap">
            <button
              type="button"
              className="nav-collapse-btn"
              onClick={() => setCollapsed((v) => !v)}
              aria-label="Toggle sidebar"
              title={collapsed ? "Expand" : "Collapse"}
            >
              {collapsed ? ">" : "<"}
            </button>
            <div className="brand-avatar">M</div>
            <div>
              <p className="brand-title">MAN Comms Console</p>
              <p className="brand-sub">Agentic customer comms layer - POC</p>
            </div>
          </div>

          <div className="top-actions">
            <div className="agent-pill" title={agentConfig?.backend === "openai" ? "OpenAI agent online" : "Agent online"}>
              <span className="dot" />
              {agentPillLabel}
            </div>
            <label className="meta-pill">
              <span className="meta-label">Seed</span>
              <input value={seedInput} onChange={(e) => onSeedInput(e.target.value)} aria-label="Seed" />
            </label>
            <div className="meta-pill" title={generatedLabel}>
              <span className="meta-label">Generated</span>
              <span className="meta-value">{generatedLabel}</span>
            </div>
            <button type="button" className="btn-primary btn-small" onClick={onReseed}>
              Reseed
            </button>
            <button type="button" className="btn-ghost btn-small" onClick={onLogout}>
              Logout
            </button>
          </div>
        </header>

        <div className={`main-layout ${collapsed ? "nav-collapsed" : ""}`}>
          <aside className="left-nav glass-normal">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`nav-item ${active === item.id ? "active" : ""}`}
                onClick={() => onActiveChange(item.id)}
                title={collapsed ? item.label : undefined}
              >
                <span className="nav-glyph">{item.glyph}</span>
                {!collapsed ? <span className="nav-label">{item.label}</span> : null}
              </button>
            ))}
            {!collapsed && kpis ? (
              <div style={{ marginTop: 14, padding: "12px 6px", borderTop: "1px solid rgba(148,188,224,0.2)" }}>
                <div style={{ fontSize: 10, color: "var(--gray-500)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8, paddingLeft: 6 }}>
                  Agent workload
                </div>
                <MiniStat label="Handled" value={kpis.messages_handled} />
                <MiniStat label="Auto-sent" value={kpis.auto_resolved} />
                <MiniStat label="Clarifications" value={kpis.clarifications_open} accent />
                <MiniStat label="Escalations" value={kpis.pending_handoffs} accent />
                <MiniStat label="Hours saved" value={kpis.fte_hours_saved} />
              </div>
            ) : null}
          </aside>
          <main className="content-wrap">{children}</main>
        </div>
      </div>
    </div>
  );
}

function MiniStat({ label, value, accent }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 10px", fontSize: 12, color: accent ? "var(--brick-700)" : "var(--gray-600)" }}>
      <span>{label}</span>
      <strong style={{ color: accent ? "var(--brick-700)" : "var(--blue-900)" }}>{value ?? "-"}</strong>
    </div>
  );
}
