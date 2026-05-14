import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { AppShell } from "./components/layout/AppShell";
import { SectionPanel } from "./components/sections/SectionPanel";
import { SECTION_SUBTITLES, SECTION_TITLES } from "./theme";
import { AgentInbox } from "./sections/AgentInbox";
import { ProactiveNudges } from "./sections/ProactiveNudges";
import { AgentRuns } from "./sections/AgentRuns";
import { Playbooks } from "./sections/Playbooks";
import { HumanHandoffs } from "./sections/HumanHandoffs";
import { Impact } from "./sections/Impact";
import { Login } from "./components/Login";
import { CustomerPhone } from "./components/CustomerPhone";

export default function App() {
  const [authed, setAuthed] = useState(() => sessionStorage.getItem("man_auth") === "1");
  const [active, setActive] = useState("inbox");
  const [seedInput, setSeedInput] = useState("42");
  const [generatedAt, setGeneratedAt] = useState("");
  const [kpis, setKpis] = useState({});
  const [customers, setCustomers] = useState([]);
  const [shipments, setShipments] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [nudges, setNudges] = useState([]);
  const [runs, setRuns] = useState([]);
  const [agentActions, setAgentActions] = useState([]);
  const [agentConfig, setAgentConfig] = useState(null);
  const [info, setInfo] = useState("");
  const [error, setError] = useState("");
  const [preselectCustomer, setPreselectCustomer] = useState(null);
  const [phoneOpen, setPhoneOpen] = useState(false);
  const [lastResult, setLastResult] = useState(null);

  const loadAll = useCallback(async () => {
    try {
      const [h, c, s, t, a, cfg, ndg, rns] = await Promise.all([
        api.health(),
        api.customers(),
        api.shipments(),
        api.tickets(),
        api.agentActions(),
        api.agentConfig(),
        api.nudges(),
        api.agentRuns({ limit: 200 }),
      ]);
      setGeneratedAt(h.generated_at);
      setKpis(h.kpis || {});
      setCustomers(c.items || []);
      setShipments(s.items || []);
      setTickets(t.items || []);
      setAgentActions(a.items || []);
      setAgentConfig(cfg);
      setNudges(ndg.items || []);
      setRuns(rns.items || []);
    } catch (e) {
      setError(e.message || "Failed to load data.");
    }
  }, []);

  useEffect(() => { if (authed) loadAll(); }, [loadAll, authed]);

  useEffect(() => {
    if (!info) return undefined;
    const timer = setTimeout(() => setInfo(""), 3500);
    return () => clearTimeout(timer);
  }, [info]);

  useEffect(() => {
    if (!error) return undefined;
    const timer = setTimeout(() => setError(""), 5000);
    return () => clearTimeout(timer);
  }, [error]);

  if (!authed) {
    return <Login onAuth={() => setAuthed(true)} />;
  }

  async function handleReseed() {
    try {
      await api.reseed(Number(seedInput) || 42);
      await loadAll();
      setInfo("Demo dataset regenerated.");
    } catch (e) {
      setError(e.message || "Reseed failed.");
    }
  }

  function openInboxFor(customerId) {
    setPreselectCustomer(customerId);
    setActive("inbox");
  }

  const orderedCustomers = preselectCustomer
    ? [
        ...customers.filter((c) => c.id === preselectCustomer),
        ...customers.filter((c) => c.id !== preselectCustomer),
      ]
    : customers;

  return (
    <AppShell
      active={active}
      onActiveChange={(id) => { setActive(id); setPreselectCustomer(null); }}
      generatedAt={generatedAt}
      seedInput={seedInput}
      onSeedInput={setSeedInput}
      onReseed={handleReseed}
      onLogout={() => { sessionStorage.removeItem("man_auth"); setAuthed(false); }}
      kpis={kpis}
      agentConfig={agentConfig}
    >
      <SectionPanel
        title={SECTION_TITLES[active]}
        subtitle={SECTION_SUBTITLES[active]}
        className={active === "inbox" ? "inbox-panel" : ""}
      >
        {active === "inbox" ? (
          <AgentInbox
            key={preselectCustomer || "default"}
            customers={orderedCustomers}
            shipments={shipments}
            tickets={tickets}
            lastResult={lastResult}
            onOpenPhone={() => setPhoneOpen(true)}
          />
        ) : null}
        {active === "nudges" ? (
          <ProactiveNudges
            nudges={nudges}
            agentConfig={agentConfig}
            onAction={loadAll}
            onOpenInbox={openInboxFor}
          />
        ) : null}
        {active === "runs" ? (
          <AgentRuns
            runs={runs}
            customers={customers}
            onOpenInbox={openInboxFor}
          />
        ) : null}
        {active === "handoffs" ? (
          <HumanHandoffs
            tickets={tickets}
            agentConfig={agentConfig}
            onAction={loadAll}
          />
        ) : null}
        {active === "playbook" ? (
          <Playbooks agentConfig={agentConfig} onSaved={loadAll} />
        ) : null}
        {active === "impact" ? (
          <Impact
            kpis={kpis}
            agentActions={agentActions}
            tickets={tickets}
            nudges={nudges}
          />
        ) : null}
      </SectionPanel>

      <div className="toast-stack" aria-live="polite">
        {info ? <p className="info-banner success">{info}</p> : null}
        {error ? <p className="info-banner error">{error}</p> : null}
      </div>

      <button
        type="button"
        className="phone-fab"
        onClick={() => setPhoneOpen(true)}
        title="Open Customer Phone"
      >
        <span className="phone-fab-icon" aria-hidden>{"☎"}</span>
        Customer Phone
      </button>

      <CustomerPhone
        open={phoneOpen}
        onClose={() => setPhoneOpen(false)}
        customers={customers}
        shipments={shipments}
        onResult={setLastResult}
        onAction={loadAll}
      />
    </AppShell>
  );
}
