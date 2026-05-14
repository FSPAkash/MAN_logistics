import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { intentLabel } from "../utils";

const ALL_INTENTS = [
  "tracking", "eta", "customs", "documents", "pod_request", "delay_reason",
  "pickup_booking", "general", "damage_claim", "billing", "address_change", "reschedule",
];

function cloneConfig(cfg) {
  if (!cfg) return null;
  return JSON.parse(JSON.stringify(cfg));
}

function sameJson(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

export function Playbooks({ agentConfig, onSaved }) {
  const [draft, setDraft] = useState(() => cloneConfig(agentConfig));
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");

  useEffect(() => {
    setDraft(cloneConfig(agentConfig));
  }, [agentConfig]);

  const dirty = useMemo(
    () => draft && agentConfig && !sameJson(draft, agentConfig),
    [draft, agentConfig]
  );

  if (!draft) return <p className="dim">Loading playbook...</p>;

  const agents = draft.agents || [];
  const tools = draft.tools || [];
  const rules = draft.nudge_rules || [];
  const tone = draft.tone_by_tier || {};
  const depts = draft.departments || [];
  const routing = draft.intent_routing || {};

  function set(patch) {
    setDraft((prev) => ({ ...prev, ...patch }));
  }

  function toggleAuto(intent, checked) {
    const auto = new Set(draft.auto_intents || []);
    const hard = new Set(draft.hard_escalate_intents || []);
    if (checked) { auto.add(intent); hard.delete(intent); }
    else auto.delete(intent);
    set({ auto_intents: [...auto], hard_escalate_intents: [...hard] });
  }

  function toggleHard(intent, checked) {
    const auto = new Set(draft.auto_intents || []);
    const hard = new Set(draft.hard_escalate_intents || []);
    if (checked) { hard.add(intent); auto.delete(intent); }
    else hard.delete(intent);
    set({ auto_intents: [...auto], hard_escalate_intents: [...hard] });
  }

  function updateRoute(intent, deptId) {
    set({ intent_routing: { ...routing, [intent]: deptId } });
  }

  function updateTone(tier, note) {
    set({ tone_by_tier: { ...tone, [tier]: note } });
  }

  function updateRule(idx, key, val) {
    const next = rules.map((r, i) => (i === idx ? { ...r, [key]: val } : r));
    set({ nudge_rules: next });
  }

  function removeRule(idx) {
    set({ nudge_rules: rules.filter((_, i) => i !== idx) });
  }

  function addRule() {
    const nextId = `rule_${(rules.length || 0) + 1}`;
    set({ nudge_rules: [...rules, { id: nextId, trigger: "", action: "" }] });
  }

  function updateDept(idx, key, val) {
    const next = depts.map((d, i) => (i === idx ? { ...d, [key]: val } : d));
    set({ departments: next });
  }

  function updateMember(dIdx, mIdx, key, val) {
    const next = depts.map((d, i) => {
      if (i !== dIdx) return d;
      const members = (d.members || []).map((m, j) => (j === mIdx ? { ...m, [key]: val } : m));
      return { ...d, members };
    });
    set({ departments: next });
  }

  function removeMember(dIdx, mIdx) {
    const next = depts.map((d, i) => {
      if (i !== dIdx) return d;
      return { ...d, members: (d.members || []).filter((_, j) => j !== mIdx) };
    });
    set({ departments: next });
  }

  function addMember(dIdx) {
    const dept = depts[dIdx];
    const nextIdx = (dept.members || []).length + 1;
    const prefix = dept.id.slice(0, 3).toUpperCase();
    const newMember = { id: `USR-${prefix}-${String(nextIdx).padStart(2, "0")}`, name: "", role: "" };
    updateDept(dIdx, "members", [...(dept.members || []), newMember]);
  }

  function removeDept(idx) {
    if (depts.length <= 1) return;
    const removed = depts[idx].id;
    const next = depts.filter((_, i) => i !== idx);
    const prunedRouting = Object.fromEntries(
      Object.entries(routing).filter(([, v]) => v !== removed)
    );
    set({
      departments: next,
      intent_routing: prunedRouting,
      fallback_department: draft.fallback_department === removed ? next[0].id : draft.fallback_department,
    });
  }

  function addDept() {
    const id = `dept_${Date.now().toString(36)}`;
    set({ departments: [...depts, { id, name: "New Department", description: "", sla_hours: 4, members: [] }] });
  }

  async function save() {
    setErr(""); setOk(""); setSaving(true);
    try {
      const patch = {
        confidence_threshold: draft.confidence_threshold,
        auto_intents: draft.auto_intents,
        hard_escalate_intents: draft.hard_escalate_intents,
        tone_by_tier: draft.tone_by_tier,
        nudge_rules: draft.nudge_rules,
        intent_routing: draft.intent_routing,
        fallback_department: draft.fallback_department,
        departments: draft.departments,
      };
      const updated = await api.updateAgentConfig(patch);
      setDraft(cloneConfig(updated));
      setOk(`Saved. Config v${updated.version}. Agents reloaded.`);
      if (onSaved) onSaved(updated);
    } catch (e) {
      setErr(e.message || "Save failed");
    } finally {
      setSaving(false);
    }
  }

  function discard() {
    setDraft(cloneConfig(agentConfig));
    setErr(""); setOk("");
  }

  const thresholdPct = Math.round((draft.confidence_threshold || 0) * 100);

  return (
    <div className="stack">
      <div className="playbook-toolbar card glass-normal">
        <div>
          <strong>Live playbook</strong>
          <p className="card-sub" style={{ marginTop: 4 }}>
            Edits take effect on save. New inbound messages use the updated rules immediately. Version {draft.version || 1}
            {draft.updated_at ? ` - last updated ${new Date(draft.updated_at).toLocaleString()}` : ""}.
          </p>
        </div>
        <div className="row" style={{ gap: 8 }}>
          {err ? <span className="info-banner error">{err}</span> : null}
          {ok && !dirty ? <span className="info-banner success">{ok}</span> : null}
          <button type="button" className="btn-ghost btn-small" onClick={discard} disabled={!dirty || saving}>Discard</button>
          <button type="button" className="btn-primary btn-small" onClick={save} disabled={!dirty || saving}>
            {saving ? "Saving..." : dirty ? "Save changes" : "Saved"}
          </button>
        </div>
      </div>

      <div className="card glass-normal">
        <h3>Agents in the system</h3>
        <p className="card-sub">
          Four cooperating agents. Triage, resolver, and supervisor run as a pipeline on every inbound message. The nudge agent runs on tracking events.
        </p>
        <div className="agent-grid">
          {agents.map((a) => (
            <div key={a.id} className={`agent-card agent-${a.id}`}>
              <div className="agent-card-head">
                <span className="agent-badge">{a.id}</span>
                <strong>{a.name}</strong>
              </div>
              <p className="agent-role">{a.role}</p>
              <div className="agent-meta">
                <span className="agent-meta-label">Tools</span>
                <div className="row" style={{ flexWrap: "wrap", gap: 4 }}>
                  {(a.tools || []).map((t) => <code key={t} className="agent-tool">{t}</code>)}
                </div>
              </div>
              <div className="agent-meta">
                <span className="agent-meta-label">Outputs</span>
                <span className="agent-outputs">{(a.outputs || []).join(", ")}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="playbook-grid">
        <div className="card glass-normal">
          <h3>Routing policy</h3>
          <p className="card-sub">Check intents the resolver should auto-handle. Mark others as hard-escalate. Supervisor still has final say.</p>

          <div className="policy-row">
            <strong>Confidence threshold</strong>
            <div className="row" style={{ gap: 10, alignItems: "center" }}>
              <input
                type="range"
                min="0" max="100" step="1"
                value={thresholdPct}
                onChange={(e) => set({ confidence_threshold: Number(e.target.value) / 100 })}
              />
              <span className="badge badge-muted">{thresholdPct}%</span>
            </div>
            <p className="dim" style={{ fontSize: 12, marginTop: 4 }}>Below this, resolver proposes escalate.</p>
          </div>

          <div className="policy-row">
            <strong>Resolver auto-handles</strong>
            <div className="chip-picker">
              {ALL_INTENTS.map((i) => {
                const checked = (draft.auto_intents || []).includes(i);
                return (
                  <label key={`auto-${i}`} className={`chip-check ${checked ? "on" : ""}`}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(e) => toggleAuto(i, e.target.checked)}
                    />
                    {intentLabel(i)}
                  </label>
                );
              })}
            </div>
          </div>

          <div className="policy-row">
            <strong>Supervisor forces human</strong>
            <div className="chip-picker">
              {ALL_INTENTS.map((i) => {
                const checked = (draft.hard_escalate_intents || []).includes(i);
                return (
                  <label key={`hard-${i}`} className={`chip-check danger ${checked ? "on" : ""}`}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(e) => toggleHard(i, e.target.checked)}
                    />
                    {intentLabel(i)}
                  </label>
                );
              })}
            </div>
          </div>
        </div>

        <div className="card glass-normal">
          <h3>Intent - department routing</h3>
          <p className="card-sub">When supervisor escalates, route the ticket to this department. Unmapped intents fall back to the default queue.</p>
          <div className="routing-grid">
            <div className="policy-row">
              <strong>Fallback department</strong>
              <select
                value={draft.fallback_department || ""}
                onChange={(e) => set({ fallback_department: e.target.value })}
              >
                {depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>
            <table className="routing-table">
              <thead>
                <tr><th>Intent</th><th>Department</th></tr>
              </thead>
              <tbody>
                {ALL_INTENTS.map((i) => (
                  <tr key={`route-${i}`}>
                    <td>{intentLabel(i)}</td>
                    <td>
                      <select
                        value={routing[i] || ""}
                        onChange={(e) => updateRoute(i, e.target.value)}
                      >
                        <option value="">(fallback)</option>
                        {depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card glass-normal">
          <h3>Departments</h3>
          <p className="card-sub">Who handles escalations, SLA per queue, and team members.</p>
          <div className="dept-editor">
            {depts.map((d, idx) => (
              <div key={d.id} className="dept-edit-card">
                <div className="row" style={{ gap: 8, alignItems: "center" }}>
                  <input
                    className="dept-name-input"
                    value={d.name}
                    onChange={(e) => updateDept(idx, "name", e.target.value)}
                  />
                  <span className="badge badge-muted">{d.id}</span>
                  <span className="spacer" />
                  <label className="sla-input">
                    <span>SLA</span>
                    <input
                      type="number"
                      min="1" max="168"
                      value={d.sla_hours || 4}
                      onChange={(e) => updateDept(idx, "sla_hours", Number(e.target.value))}
                    />
                    <span>h</span>
                  </label>
                  <button type="button" className="btn-ghost btn-small" onClick={() => removeDept(idx)} disabled={depts.length <= 1}>Remove</button>
                </div>
                <textarea
                  className="dept-desc-input"
                  rows={2}
                  placeholder="What this team covers"
                  value={d.description || ""}
                  onChange={(e) => updateDept(idx, "description", e.target.value)}
                />
                <div className="member-list">
                  {(d.members || []).map((m, mIdx) => (
                    <div key={m.id + mIdx} className="member-row">
                      <input
                        placeholder="Name"
                        value={m.name}
                        onChange={(e) => updateMember(idx, mIdx, "name", e.target.value)}
                      />
                      <input
                        placeholder="Role"
                        value={m.role || ""}
                        onChange={(e) => updateMember(idx, mIdx, "role", e.target.value)}
                      />
                      <code className="member-id">{m.id}</code>
                      <button type="button" className="btn-ghost btn-tiny" onClick={() => removeMember(idx, mIdx)}>x</button>
                    </div>
                  ))}
                  <button type="button" className="btn-ghost btn-small" onClick={() => addMember(idx)}>+ Add member</button>
                </div>
              </div>
            ))}
            <button type="button" className="btn-ghost" onClick={addDept}>+ Add department</button>
          </div>
        </div>

        <div className="card glass-normal">
          <h3>Nudge agent rules</h3>
          <p className="card-sub">Event-driven outbound. Fires when the tracking system emits matching events.</p>
          <div className="rule-list">
            {rules.map((r, idx) => (
              <div key={r.id + idx} className="rule-edit-row">
                <input
                  className="rule-id-input"
                  value={r.id}
                  onChange={(e) => updateRule(idx, "id", e.target.value)}
                  placeholder="rule_id"
                />
                <input
                  value={r.trigger || ""}
                  onChange={(e) => updateRule(idx, "trigger", e.target.value)}
                  placeholder="When: tracking event matches..."
                />
                <input
                  value={r.action || ""}
                  onChange={(e) => updateRule(idx, "action", e.target.value)}
                  placeholder="Then: send..."
                />
                <button type="button" className="btn-ghost btn-tiny" onClick={() => removeRule(idx)}>x</button>
              </div>
            ))}
            <button type="button" className="btn-ghost btn-small" onClick={addRule}>+ Add rule</button>
          </div>
        </div>

        <div className="card glass-normal">
          <h3>Tool catalog</h3>
          <p className="card-sub">Read-only adapters. Wire these to the client's tracking API in production.</p>
          <div className="tool-stack">
            {tools.map((t) => (
              <div key={t.name} className="tool-call">
                <div className="row">
                  <code>{t.name}</code>
                  <span className="spacer" />
                  <span className="badge badge-muted">read-only</span>
                </div>
                <div className="tool-result">{t.desc}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card glass-normal">
          <h3>Tone by customer tier</h3>
          <p className="card-sub">Informs draft phrasing only. Does NOT affect routing.</p>
          <div className="rule-list">
            {Object.entries(tone).map(([tier, note]) => (
              <div key={tier} className="tone-row">
                <strong>{tier}</strong>
                <textarea
                  rows={2}
                  value={note}
                  onChange={(e) => updateTone(tier, e.target.value)}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
