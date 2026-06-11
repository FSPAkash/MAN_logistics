import { useState } from "react";
import { NAV_ITEMS } from "../../theme";
import manLogo from "../../assets/MAN_logo.png";
import fsLogo from "../../assets/FS.png";

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
  const agentPillLabel = agentConfig?.backend === "openai" ? "AI" : "Agent live";

  return (
    <div className="app-root" data-section={active}>
      <div className="app-shell-frame">
        <header className="top-bar">
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
            <div className="brand-logo">
              <img src={manLogo} alt="MAN Logistics" />
            </div>
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
              <div style={{ marginTop: 14, padding: "12px 6px", borderTop: "1px solid var(--line-2)" }}>
                <div style={{ fontSize: 10, color: "var(--gray-500)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8, paddingLeft: 6, fontWeight: 600 }}>
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

        <footer className="statusbar">
          <span className="dot" aria-hidden />
          <span>CONNECTED</span>
          <span className="sep" aria-hidden />
          <label style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span className="meta-label">Seed</span>
            <input
              value={seedInput}
              onChange={(e) => onSeedInput(e.target.value)}
              aria-label="Seed"
              style={{ width: 64, height: 20, padding: "0 6px", fontSize: 11 }}
            />
          </label>
          <span className="sep" aria-hidden />
          <span title={generatedLabel}>GENERATED {generatedLabel}</span>
          <span className="right">
            <span className="powered-label">Powered by</span>
            <img className="powered-logo" src={fsLogo} alt="Findability Sciences" />
          </span>
        </footer>
      </div>
    </div>
  );
}

function MiniStat({ label, value, accent }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "5px 8px", fontSize: 11.5 }}>
      <span style={{ color: "var(--gray-500)" }}>{label}</span>
      <strong style={{ color: accent ? "var(--brick-700)" : "var(--blue-900)", fontVariantNumeric: "tabular-nums" }}>{value ?? "-"}</strong>
    </div>
  );
}
