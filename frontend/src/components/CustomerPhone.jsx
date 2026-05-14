import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { fmtTime } from "../utils";

function useDraggable(initial) {
  const [pos, setPos] = useState(initial);
  const dragRef = useRef(null);

  function onMouseDown(e) {
    if (e.target.closest(".phone-popup-no-drag")) return;
    const startX = e.clientX;
    const startY = e.clientY;
    const startPos = { ...pos };
    dragRef.current = { startX, startY, startPos };

    function onMove(ev) {
      const dx = ev.clientX - dragRef.current.startX;
      const dy = ev.clientY - dragRef.current.startY;
      const maxX = window.innerWidth - 100;
      const maxY = window.innerHeight - 60;
      setPos({
        x: Math.max(0, Math.min(maxX, dragRef.current.startPos.x + dx)),
        y: Math.max(0, Math.min(maxY, dragRef.current.startPos.y + dy)),
      });
    }
    function onUp() {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  return { pos, onMouseDown };
}

export function CustomerPhone({ open, onClose, customers, shipments, onResult, onAction }) {
  const initialPos = useMemo(() => ({
    x: Math.max(20, window.innerWidth - 360),
    y: Math.max(20, window.innerHeight - 600),
  }), []);
  const { pos, onMouseDown } = useDraggable(initialPos);
  const [selectedId, setSelectedId] = useState("");
  const [thread, setThread] = useState([]);
  const [threadLoading, setThreadLoading] = useState(false);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const threadRef = useRef(null);

  useEffect(() => {
    if (open && !selectedId && customers.length) {
      setSelectedId(customers[0].id);
    }
  }, [open, customers, selectedId]);

  const selected = customers.find((c) => c.id === selectedId) || null;

  const customerShipments = useMemo(
    () => shipments.filter((s) => s.customer_id === selectedId)
      .sort((a, b) => new Date(b.last_event_at) - new Date(a.last_event_at)),
    [shipments, selectedId]
  );
  const primaryShipment = customerShipments[0] || null;

  async function loadThread(customerId) {
    if (!customerId) return;
    setThreadLoading(true);
    try {
      const res = await api.messages({ customer_id: customerId, limit: 200 });
      setThread(res.items || []);
    } finally {
      setThreadLoading(false);
    }
  }

  useEffect(() => { if (open) loadThread(selectedId); }, [selectedId, open]);

  useEffect(() => {
    if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight;
  }, [thread]);

  async function sendCustomerMessage(text, optimisticMeta = {}) {
    if (!text || !selectedId || sending) return;
    const customerId = selectedId;
    const optimistic = {
      id: `TMP-${Date.now()}`,
      shipment_id: optimisticMeta.shipment_id ?? primaryShipment?.id ?? null,
      shipment_ref: optimisticMeta.shipment_ref ?? primaryShipment?.ref ?? null,
      customer_id: customerId,
      customer_name: selected?.name || "Customer",
      direction: "incoming",
      text,
      timestamp: new Date().toISOString(),
      channel: "whatsapp",
      source: "customer",
    };
    setThread((prev) => [...prev, optimistic]);
    setDraft("");
    setSending(true);
    try {
      const res = await api.sendMessage({ customer_id: customerId, text });
      onResult && onResult(res);
      await loadThread(customerId);
      onAction && onAction();
    } catch (_err) {
      setDraft(text);
      await loadThread(customerId);
    } finally {
      setSending(false);
    }
  }

  async function handleSend(e) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || !selectedId || sending) return;
    await sendCustomerMessage(text);
  }

  function selectorMessage(ref, intent) {
    if (intent === "eta") return `What is the ETA for ${ref}?`;
    if (intent === "customs") return `Has ${ref} cleared customs?`;
    if (intent === "documents") return `Can you send me the documents for ${ref}?`;
    if (intent === "pod_request") return `Need POD for ${ref}.`;
    if (intent === "delay_reason") return `Why is ${ref} delayed?`;
    return `Give me details about shipment ${ref}.`;
  }

  async function handleSelectorPick(ref, intent) {
    await sendCustomerMessage(selectorMessage(ref, intent), { shipment_ref: ref });
  }

  const suggestedPrompts = useMemo(() => {
    if (!primaryShipment) {
      return [
        "Need pickup tomorrow, 3 pallets to Rotterdam.",
        "What are your office hours?",
      ];
    }
    const ref = primaryShipment.ref;
    return [
      `Where is my shipment ${ref}?`,
      `What is the ETA for ${ref}?`,
      `Has ${ref} cleared customs?`,
      `Can you send me the BL for ${ref}?`,
      `Need POD for ${ref}.`,
      `Please change delivery address for ${ref}.`,
    ];
  }, [primaryShipment]);

  if (!open) return null;

  return (
    <div
      className="phone-frame floating"
      style={{ left: pos.x, top: pos.y }}
    >
      <div className="phone-screen">
        <div className="wa-header" onMouseDown={onMouseDown}>
          <div className="wa-avatar" />
          <div className="wa-header-info">
            <div className="wa-name">MAN Logistics</div>
            <select
              className="wa-customer-picker phone-popup-no-drag"
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
            >
              {customers.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <button
            type="button"
            className="wa-close-btn phone-popup-no-drag"
            onClick={onClose}
            aria-label="Close"
          >x</button>
        </div>
            <div className="wa-thread" ref={threadRef}>
              {threadLoading ? <p className="wa-queue-empty">Loading thread...</p> : null}
              {!threadLoading && !thread.length ? (
                <p className="wa-queue-empty">No messages yet. Send one below as {selected?.name || "customer"}.</p>
              ) : null}
              {thread.map((m) => {
                const mine = m.direction === "incoming";
                return (
                  <div key={m.id} className={`wa-bubble ${mine ? "outgoing" : "incoming"}`}>
                    <div>{m.text}</div>
                    {!mine && Array.isArray(m.selector_refs) && m.selector_refs.length ? (
                      <div className="wa-selector-wrap">
                        <div className="wa-selector-label">{m.selector_prompt || "Choose a shipment"}</div>
                        <div className="wa-selector-pills">
                          {m.selector_refs.map((ref) => (
                            <button
                              key={ref}
                              type="button"
                              className="wa-selector-pill"
                              disabled={sending}
                              onClick={() => handleSelectorPick(ref, m.selector_intent)}
                            >
                              {ref}
                            </button>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    <div className="wa-meta-row">
                      {!mine ? (
                        <span className="wa-src">
                          {m.source === "office" ? "Office" : m.source === "agent_approved" ? "Agent (approved)" : m.source === "agent" ? "Agent" : "System"}
                        </span>
                      ) : null}
                      <span className="wa-time">{fmtTime(m.timestamp)}</span>
                    </div>
                  </div>
                );
              })}
              {sending ? (
                <div className="wa-bubble incoming wa-typing">
                  <div className="typing-dots" aria-hidden="true"><span /><span /><span /></div>
                </div>
              ) : null}
            </div>
        <div className="wa-prompts-row phone-popup-no-drag">
          {suggestedPrompts.map((p) => (
            <button key={p} type="button" className="wa-prompt-chip" onClick={() => setDraft(p)}>
              {p.length > 32 ? p.slice(0, 30) + "..." : p}
            </button>
          ))}
        </div>
        <form className="wa-input-bar" onSubmit={handleSend}>
          <input
            className="wa-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={selected ? `Type as ${selected.name}...` : "Pick a customer first"}
            disabled={!selected || sending}
          />
          <button type="submit" className="wa-send-btn" disabled={!selected || sending || !draft.trim()}>
            <span>&gt;</span>
          </button>
        </form>
      </div>
    </div>
  );
}
