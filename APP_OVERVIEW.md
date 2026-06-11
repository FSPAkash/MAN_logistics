# MAN Logistics — Agentic Customer Desk

A proof-of-concept that shows what an **agentic WhatsApp customer-service desk** for a
freight forwarder looks like. Customers message about their shipments; a chain of AI
agents triages, drafts, and either auto-replies or routes to a human team — all grounded
in (mock) shipment tracking data. The dashboard is the operator's window into that
machine: every decision, every tool call, every escalation, and the impact.

It is a **demo / sales artifact**, not production. All data is generated in-memory from a
deterministic seed. Nothing talks to a real carrier, WhatsApp, or ticketing system.

---

## 1. What problem it pretends to solve

A freight forwarder's support team drowns in repetitive WhatsApp messages: "where is my
container", "what's the ETA", "has it cleared customs", "send me the BL". Most of these
are answerable straight from tracking data. A few (damage claims, billing disputes,
address changes, pickup reschedules) genuinely need a human.

The pitch this app dramatizes: put a **multi-agent layer** in front of the desk that

1. **classifies** each inbound message (intent + confidence),
2. **grounds** a reply in live shipment data,
3. **auto-sends** when it's confident and the topic is safe,
4. **asks the customer to clarify** when they have several shipments and didn't say which,
5. **escalates to the right human department** when judgement, verification, or
   compensation is involved,
6. **proactively nudges** customers on tracking events (ETA slips, customs cleared,
   out-for-delivery, delivered) before they even ask.

The dashboard then proves the value: how many messages were handled, how many were
auto-resolved vs escalated, and how much "minion work" (manual reminder calls, status
lookups) was replaced.

---

## 2. Architecture at a glance

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (React + Vite SPA)                                  │
│  - AppShell: titlebar, left nav, statusbar                   │
│  - 6 sections (Inbox, Nudges, Runs, Handoffs, Rules, Impact) │
│  - Floating "Customer Phone" (WhatsApp simulator)            │
└───────────────┬─────────────────────────────────────────────┘
                │  fetch() → /api/*   (JSON over HTTP)
┌───────────────▼─────────────────────────────────────────────┐
│  Flask backend (app.py)                                      │
│  - In-memory STATE dict (the whole "database")               │
│  - Agent pipeline: triage → resolver → supervisor            │
│  - REST endpoints for every section                          │
│  - Serves the built frontend (frontend/dist) in prod         │
├──────────────────────────────────────────────────────────────┤
│  data_seed.py   deterministic mock dataset generator         │
│  agent.py       optional OpenAI classify + compose           │
│  keep_alive.py  self-ping so a free-tier host doesn't sleep  │
└──────────────────────────────────────────────────────────────┘
```

- **State is in-memory.** `STATE` is one Python dict holding customers, shipments,
  messages, tickets, agent actions, nudges, approvals, agent runs, KPIs, and the editable
  agent config. It is regenerated on reseed or process restart, and mirrored to
  `backend/runtime_dataset.json` so a restart can reload the last state.
- **No real database, no real queue, no real WhatsApp.** The "WhatsApp phone" is a React
  component; sending a message just POSTs to `/api/messages`.
- **Two agent backends.** `MAN_AGENT_BACKEND=regex` (default) uses keyword rules;
  `MAN_AGENT_BACKEND=openai` calls OpenAI for classification and reply composition, with
  automatic fallback to the regex/template path on any error.

---

## 3. Tech stack

| Layer | Tech |
|---|---|
| Frontend | React 18, Vite 5, plain CSS (no framework). Manrope font. |
| Backend | Python, Flask 3, flask-cors, gunicorn (prod) |
| AI (optional) | OpenAI Python SDK (`gpt-4o-mini` by default) |
| State | In-memory dict + JSON file mirror |
| Styling | "Industrial-window" design language (see `DESIGN_LANGUAGE.md`): white paper, hairline borders, uppercase micro-labels, mono numbers; MAN red as accent, navy blue as strong-secondary |

---

## 4. The agent pipeline (the core idea)

Every inbound customer message runs through a **three-stage pipeline**. This is the heart
of the product. Implemented for live sends in `app.py::send_message`; the seeded
historical runs are reconstructed by `data_seed.py::_build_pipeline` with the same logic.

### Stage 1 — Triage
- Tool call: `get_customer_shipments(customer_id)`.
- Classifies intent + confidence (regex rules or OpenAI).
- **Ambiguity check:** if the intent is shipment-specific (tracking / eta / customs /
  documents / pod_request / delay_reason), the customer named **no** reference, and they
  have **more than one** active shipment → triage **does not guess**. It replies asking
  the customer to pick a shipment (the reply carries `selector_refs` so the phone shows
  tappable chips). Decision: `clarify`. Pipeline stops here.
- Otherwise → `route_to_resolver`.

### Stage 2 — Resolver
- Tool calls: `get_customer_shipments`, and `get_shipment(ref)` when a shipment is known.
- **Resolves the target shipment** (`_resolve_shipment`): exact `MAN######` reference if
  present in the text/hint, else the customer's most recent shipment. Records whether the
  requested ref was found.
- **Drafts a grounded reply** (`_compose_reply`): per-intent template (or OpenAI compose),
  built only from real shipment fields — last event, location, ETA, customs status,
  document readiness, delay reason, etc. If a requested ref isn't on the account, it says
  so and lists the customer's recent refs instead of hallucinating.
- **Proposes** a decision:
  - `propose_escalate` if the intent is hard-escalate (damage_claim, billing,
    address_change, reschedule), or not in the configured `auto_intents`, or confidence is
    below the configured `confidence_threshold`.
  - `propose_auto_send` otherwise.

### Stage 3 — Supervisor
- The check on the resolver. Does a second read and can **override**.
- If resolver proposed escalate:
  - **Hard-escalate intent** → confirms escalation, writes a customer acknowledgment, and
    opens a ticket. Decision: `escalate`.
  - **Otherwise**, if a shipment is known and confidence ≥ 0.55 → **override to
    `auto_send`** ("tracking data does answer this; resolver was over-cautious").
  - Else → `escalate` (no weak auto-sends, no held drafts).
- If resolver proposed auto-send → `auto_send` ("draft verified, no override").

### What each decision does
| Decision | Effect |
|---|---|
| `auto_send` | Outgoing agent message appended to the thread (`source: "agent"`). Logs an `auto_reply` action. |
| `clarify` | Outgoing agent message with shipment-picker chips. Logs a `clarify_asked` action. |
| `escalate` | Outgoing **acknowledgment** to the customer + a **ticket** opened, routed to a department by intent, with an SLA clock. Logs an `escalated` action. |

Every send also writes an **agent run** (full pipeline trace: per-stage reasoning, tool
calls, latencies, outputs) and recomputes KPIs.

### Confidence & routing knobs (editable at runtime)
- `confidence_threshold` (0–1): below this the resolver proposes escalation.
- `auto_intents`: intents the resolver may auto-handle.
- `hard_escalate_intents`: intents the supervisor always forces to a human.
- `intent_routing`: intent → department.
- `fallback_department`: catch-all queue.
- `tone_by_tier`, `nudge_rules`, `departments` (+ members + SLA hours).

All of these are edited from the **Agents & Rules** tab and applied immediately to new
messages (no restart).

---

## 5. The data model (mock dataset)

Generated by `data_seed.py::generate_dataset(seed)`. Deterministic per seed; all relative
timestamps anchor to **real "now"** so the demo never looks stale after a reseed.

- **Customers (15):** name, contact person, phone, email, country, tier (Platinum / Gold /
  Silver / Standard), active shipment count.
- **Shipments (35):** `MAN######` ref, mode (Sea FCL/LCL, Air, Road), carrier, commodity,
  origin/destination (UN/LOCODEs), booked date, ETA, current status, a full **milestone
  event list** (booking → pickup → customs → vessel/flight → arrival → out-for-delivery →
  delivered), last/next event, weight, volume, containers, incoterm, invoice value,
  documents (Invoice, Packing List, BL, Certificate of Origin, POD) with ready flags, and
  ~35% get a delay (reason + minutes, pushing the ETA).
- **Chat threads:** built from 12 scenario templates (one per intent). Auto-handled
  intents get a customer message + a grounded agent reply; human-needed intents
  (reschedule, billing, damage_claim, address_change) get a message + an open **ticket**
  instead.
- **Tickets:** id, message, shipment, customer, intent, category, status (pending /
  in_progress / resolved), priority, **SLA due time** (anchored to the ticket timestamp +
  the department's SLA hours), handoff note, department + assignee.
- **Agent actions:** the activity log (`auto_reply`, `clarify_asked`, `escalated`,
  `nudge_sent`, `approval_sent`, `handoff_ack`).
- **Agent runs:** one per inbound message, with the full reconstructed pipeline trace.
- **Nudges:** proactive outbound drafts fired by tracking events — ETA slip, customs
  cleared, out-for-delivery, POD/delivered. Status: scheduled / pending_approval / sent /
  cancelled. **Sent nudges are also merged into the customer's thread** as outgoing
  messages (`source: "nudge"`) so they appear in the conversation, not just the board.
- **Broadcasts:** bulk announcements (port congestion, holiday cutoffs, etc.).
- **KPIs:** messages handled, auto-resolved, deflection rate, pending approvals/handoffs,
  clarifications open, nudges sent/queued, average confidence, escalations, SLA breaches,
  minutes/FTE-hours saved, handoffs by department.

---

## 6. The dashboard, section by section

The shell (`AppShell.jsx`) is a faux desktop window: titlebar with the **MAN logo**, a
left nav, and a **statusbar** showing the live dot, the seed input, the dataset
"generated" timestamp, and a "Powered by **Findability Sciences**" logo. A draggable
floating **Customer Phone** button sits bottom-right.

### Agent Inbox (`AgentInbox.jsx`)
The default view. Left: a conversation list (filter All / Escalated / Auto, searchable).
Right, **per selected customer**:
- **Last agent decision** — reconstructed from that customer's own latest thread (or the
  live sim result if you just sent one as them): decision badge, confidence, the
  triage→resolver→supervisor mini-pipeline, the sent WhatsApp draft (for auto-handled),
  and the routed ticket with its real department/assignee/handoff note (for escalated).
- **Tracking data the agent reads** — the primary shipment card the resolver grounds on,
  plus chips for the customer's other shipments.
- **Proactive nudges** — all nudges fired for this customer (scheduled and sent) with
  status badges.

"Open Customer Phone" launches the WhatsApp simulator pre-pointed at that customer.

### Proactive Nudges (`ProactiveNudges.jsx`)
The outbound board. Cards per nudge: rule label, trigger, the WhatsApp draft, status.
Filter by rule and status. Actions: **Send now** (materializes it into the thread and
logs an action) or **Cancel**. A "Thread" link jumps to that customer in the inbox.

### Agent Runs (`AgentRuns.jsx`)
The audit trail. A list of runs; selecting one shows the full pipeline trace — each
agent's reasoning, the tools it called (with args, latency, result summary), the proposed
vs final decision, grounded fields, and total latency. This is the "show your work" view.

### Human Handoffs (`HumanHandoffs.jsx`)
The escalation desk. Tickets grouped **by department** (Claims, Billing, Operations,
Customer Success), each with live counts and SLA-breach counts. Per ticket: the customer
message, intent, **SLA clock** ("Due in 3h" / "Breached 2h ago"), priority, assignee.
Operator actions: assign to a department/person, **agent-reply** (the agent drafts a
holding response while keeping the ticket open), reply-and-resolve, or set status.

### Agents & Rules (`Playbooks.jsx`)
The control panel for the whole agent layer:
- The four agents and what each owns (triage, resolver, supervisor, nudge).
- **Routing policy:** confidence threshold slider, which intents the resolver
  auto-handles, which the supervisor forces to humans.
- **Intent → department routing** table + fallback queue.
- **Departments editor:** add/rename departments, set SLA hours, manage members.
- **Nudge rules**, **tool catalog** (read-only adapters), **tone by tier**.
- Edits are validated server-side and bump a config version; new messages use them
  immediately.

### Impact (`Impact.jsx`)
The value story. KPI tiles (handled, auto-sent + deflection %, clarifications open,
escalations, nudges sent, hours saved) over a recent-activity feed, open clarifications,
and queued nudges.

### Customer Phone (`CustomerPhone.jsx`)
A draggable WhatsApp phone mock. Pick a customer, type or tap a suggested prompt, send.
The message POSTs to `/api/messages`, runs the real pipeline, and the agent's
reply/clarification/acknowledgment streams back into the thread. This is how you *drive* a
live agent run for the demo. Sent nudges and office/approved replies also render here with
labeled senders.

---

## 7. API surface (Flask, `app.py`)

| Method & path | Purpose |
|---|---|
| `GET /api/health` | status, generated_at, seed, KPIs |
| `POST /api/reseed` | regenerate the whole dataset for a seed |
| `GET /api/customers` | all customers |
| `GET /api/shipments` `/<id>` | shipments (filter by status/customer), detail |
| `GET /api/messages` | thread messages (filter by customer/shipment) |
| `POST /api/messages` | **customer send → runs the agent pipeline** |
| `GET /api/tickets` | escalation tickets |
| `POST /api/tickets/<id>/status` | set pending/in_progress/resolved |
| `POST /api/tickets/<id>/reply` | human reply (resolves the ticket) |
| `POST /api/tickets/<id>/agent-reply` | agent drafts a holding reply, keeps ticket open |
| `POST /api/tickets/<id>/assign` | route to department / assignee (recomputes SLA) |
| `GET /api/departments` | departments with live ticket counts + SLA breaches |
| `GET /api/agent-actions` | activity log |
| `GET /api/agent-runs` `/<id>` | pipeline traces |
| `GET /api/nudges` | proactive nudges |
| `POST /api/nudges/<id>/send` `/cancel` | send (into thread) / cancel a nudge |
| `GET /api/approvals` | draft approvals (queue exists; seed currently empty) |
| `POST /api/approvals/<id>/decide` | approve / edit / reject a draft |
| `GET /api/agent-config` | the editable playbook |
| `PUT /api/agent-config` | update threshold, intents, routing, departments, tone, rules (validated) |
| `GET /api/broadcasts` | bulk announcements |
| `GET /api/kpis` | KPI block |
| `GET /` and `/<path>` | serve the built SPA (prod) |

Frontend access is centralized in `frontend/src/api.js`.

---

## 8. Configuration (env)

Set in `backend/.env` (see `.env.example`):

| Var | Default | Effect |
|---|---|---|
| `MAN_AGENT_BACKEND` | `regex` | `regex` keyword rules, or `openai` for LLM classify+compose |
| `OPENAI_API_KEY` | — | required when backend is `openai` |
| `MAN_OPENAI_CLASSIFY_MODEL` | `gpt-4o-mini` | classifier model |
| `MAN_OPENAI_REPLY_MODEL` | `gpt-4o-mini` | reply composer model |
| `MAN_AGENT_CONFIDENCE_THRESHOLD` | `0.7` | initial auto-send threshold |
| `PORT` | `5001` | Flask port |
| (keep-alive vars) | — | self-ping for free-tier hosting, see `KEEP_ALIVE_IMPLEMENTATION.md` |

When OpenAI is selected, the classifier returns strict JSON (intent, calibrated
confidence, mentioned ref, reasoning) and the composer is constrained to plain text
grounded only in the supplied shipment JSON — never inventing fields, never promising
dates earlier than the ETA. Any OpenAI failure silently falls back to the regex/template
path, so the demo never breaks.

---

## 9. Running it

**Backend**
```
cd backend
pip install -r requirements.txt
python app.py            # dev, port 5001
# or: gunicorn app:app   # prod
```

**Frontend**
```
cd frontend
npm install
npm run dev              # Vite dev server (proxies /api to the backend)
npm run build            # outputs frontend/dist, which Flask serves in prod
```

**Login:** demo gate, username `demo` / password `fs1234` (client-side only, in
`Login.jsx` — it's a demo, not real auth).

**Reseed:** change the seed in the statusbar and hit Reseed, or `POST /api/reseed`. Fresh
deterministic dataset, timestamps re-anchored to now.

---

## 10. Honest limitations (it's a POC)

- In-memory state; concurrent users share one mutable `STATE`. Not multi-tenant.
- Login is hardcoded client-side. No sessions, no roles.
- "Tools" are mock lookups against the seed, not real carrier/WMS integrations.
- The approvals queue is wired end-to-end but seeded empty (`_make_approvals` returns
  `[]`); drafts only appear if created via the API.
- The regex classifier is intentionally simple; OpenAI mode is the "real" classifier.
- Latencies in pipeline traces are synthetic numbers for visual texture.

---

## 11. File map

```
backend/
  app.py            Flask app, agent pipeline, all REST endpoints, SPA serving
  data_seed.py      deterministic mock dataset + seeded pipeline reconstruction
  agent.py          OpenAI classify() + compose() (optional backend)
  keep_alive.py     self-ping service for free-tier hosting
  requirements.txt  flask, flask-cors, gunicorn, openai, python-dotenv, requests
  runtime_dataset.json   last generated state (auto-written; safe to delete)

frontend/src/
  App.jsx                  top-level state, data loading, section routing
  api.js                   all backend calls
  theme.js                 nav items, labels, badge maps
  utils.js                 time/intent/status formatting helpers
  index.css                the whole design system
  components/
    Login.jsx              demo login gate (MAN logo + FS "powered by")
    CustomerPhone.jsx      draggable WhatsApp simulator
    layout/AppShell.jsx    titlebar + nav + statusbar window chrome
  sections/
    AgentInbox.jsx         conversations, per-customer agent decision + tracking + nudges
    ProactiveNudges.jsx    outbound nudge board
    AgentRuns.jsx          pipeline-trace audit view
    HumanHandoffs.jsx      escalation tickets by department, SLA, assignment
    Playbooks.jsx          agents & rules editor (the control panel)
    Impact.jsx             KPIs + activity
```

---

*This document describes behavior as implemented. For the visual design spec see
`DESIGN_LANGUAGE.md`; for hosting keep-alive see `KEEP_ALIVE_IMPLEMENTATION.md`; for the
OpenAI wiring rationale see `OPENAI_INTEGRATION_PLAN.md`.*
