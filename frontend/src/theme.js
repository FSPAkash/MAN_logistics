export const NAV_ITEMS = [
  { id: "inbox",     label: "Agent Inbox",      glyph: "IN" },
  { id: "nudges",    label: "Proactive Nudges", glyph: "PN" },
  { id: "runs",      label: "Agent Runs",       glyph: "RN" },
  { id: "handoffs",  label: "Human Handoffs",   glyph: "HH" },
  { id: "playbook",  label: "Agents & Rules",   glyph: "AG" },
  { id: "impact",    label: "Impact",           glyph: "IM" },
];

export const SECTION_TITLES = {
  inbox:     "Agent Inbox",
  nudges:    "Proactive Nudges",
  runs:      "Agent Runs",
  handoffs:  "Human Handoffs",
  playbook:  "Agents & Rules",
  impact:    "Agent Impact",
};

export const SECTION_SUBTITLES = {
  inbox:     "Every customer WhatsApp lands here. A triage agent classifies it, a resolver agent drafts from tracking data, and a supervisor agent either releases the reply or routes it straight to humans. If a customer has multiple active shipments, triage asks them to pick one in chat.",
  nudges:    "Outbound messages the nudge agent fires on tracking events: ETA slips, customs cleared, POD delivery, missing documents. Replaces your team's reminder calls.",
  runs:      "Per-message trace: triage -> resolver -> supervisor. See each agent's tools, reasoning, and how the supervisor overrode or confirmed the resolver's call.",
  handoffs:  "Tickets the supervisor routed to a human. Grouped by department, with SLA clock and assignee. Assign, reply as agent, or resolve directly.",
  playbook:  "The four agents in the system and what each one owns. Intents the resolver auto-handles, intents the supervisor forces to humans, nudge rules, tone per tier. Edits apply immediately.",
  impact:    "Only metric we care about: agent work done. Messages handled, drafts approved, nudges sent, minion hours saved.",
};

export const INTENT_LABEL = {
  tracking: "Tracking",
  eta: "ETA",
  customs: "Customs",
  documents: "Documents",
  pod_request: "POD",
  reschedule: "Reschedule",
  billing: "Billing",
  damage_claim: "Damage Claim",
  address_change: "Address Change",
  pickup_booking: "Pickup",
  delay_reason: "Delay",
  general: "General",
  nudge: "Nudge",
};

export const STATUS_LABEL = {
  booked: "Booked",
  in_transit: "In Transit",
  customs: "At Customs",
  at_destination: "At Destination",
  out_for_delivery: "Out For Delivery",
  delivered: "Delivered",
};

export const DECISION_LABEL = {
  auto_send: "Auto-sent",
  clarify: "Clarified",
  escalate: "Escalated",
};

export const DECISION_BADGE = {
  auto_send: "badge-ok",
  clarify: "badge-info",
  escalate: "badge-warn",
};

export const AGENT_LABEL = {
  triage: "Triage",
  resolver: "Resolver",
  supervisor: "Supervisor",
  nudge: "Nudge",
};

export const STAGE_DECISION_LABEL = {
  clarify: "Asked customer",
  route_to_resolver: "Routed to resolver",
  propose_auto_send: "Proposed auto-send",
  propose_escalate: "Proposed escalate",
  auto_send: "Auto-sent",
  escalate: "Escalated to human",
};
