"""Mock dataset for MAN Logistics POC.

Generates customers, shipments, milestone events, chat threads, tickets,
and agent KPIs. Deterministic via seed.
"""

from __future__ import annotations

import os
import random
from datetime import datetime, timedelta
from typing import Any


CUSTOMER_NAMES = [
    "Aurora Textiles", "Meridian Auto Parts", "Coral Reef Foods", "Northwind Pharma",
    "Brickline Ceramics", "Summit Electronics", "Harbor Bay Coffee", "Vela Fashion House",
    "Ironclad Machinery", "Kite & Co. Apparel", "Terra Mineral Exports", "Saffron Spice Traders",
    "Lumen Lighting", "Oakridge Furniture", "Pacifica Seafoods",
]

ORIGINS = [
    ("Mumbai, IN", "INNSA"), ("Chennai, IN", "INMAA"), ("Shanghai, CN", "CNSHA"),
    ("Singapore, SG", "SGSIN"), ("Hamburg, DE", "DEHAM"), ("Rotterdam, NL", "NLRTM"),
    ("Dubai, AE", "AEJEA"), ("Ho Chi Minh, VN", "VNSGN"),
]

DESTINATIONS = [
    ("New York, US", "USNYC"), ("Los Angeles, US", "USLAX"), ("Felixstowe, UK", "GBFXT"),
    ("Santos, BR", "BRSSZ"), ("Durban, ZA", "ZADUR"), ("Sydney, AU", "AUSYD"),
    ("Toronto, CA", "CATOR"), ("Jebel Ali, AE", "AEJEA"),
]

COMMODITIES = [
    "Cotton textiles", "Auto spare parts", "Frozen seafood", "Generic pharma",
    "Ceramic tiles", "LED panels", "Green coffee beans", "Ready-made garments",
    "Industrial bearings", "Branded apparel", "Iron ore pellets", "Packaged spices",
    "Solar inverters", "Solid wood furniture", "Vacuum-packed fish",
]

CARRIERS = ["Maersk", "MSC", "Hapag-Lloyd", "CMA CGM", "ONE", "Evergreen"]
MODES = ["Sea FCL", "Sea LCL", "Air", "Road"]

# Milestone template per mode
MILESTONES_SEA = [
    ("booking_confirmed", "Booking confirmed", "Origin office"),
    ("pickup_scheduled", "Pickup scheduled", "Shipper warehouse"),
    ("picked_up", "Cargo picked up", "Shipper warehouse"),
    ("arrived_cfs", "Arrived at origin CFS", "Origin CFS"),
    ("customs_export", "Export customs cleared", "Origin port"),
    ("loaded_vessel", "Loaded on vessel", "Origin port"),
    ("in_transit", "Vessel in transit", "High seas"),
    ("arrived_pod", "Arrived at destination port", "Destination port"),
    ("customs_import", "Import customs cleared", "Destination port"),
    ("out_for_delivery", "Out for delivery", "Last-mile hub"),
    ("delivered", "Delivered", "Consignee door"),
]

MILESTONES_AIR = [
    ("booking_confirmed", "Booking confirmed", "Origin office"),
    ("picked_up", "Cargo picked up", "Shipper warehouse"),
    ("arrived_airport", "Arrived at origin airport", "Origin airport"),
    ("customs_export", "Export customs cleared", "Origin airport"),
    ("departed", "Flight departed", "Origin airport"),
    ("arrived_dest", "Flight arrived", "Destination airport"),
    ("customs_import", "Import customs cleared", "Destination airport"),
    ("out_for_delivery", "Out for delivery", "Last-mile hub"),
    ("delivered", "Delivered", "Consignee door"),
]

INTENT_TAGS = [
    "tracking", "eta", "customs", "documents", "pod_request", "reschedule",
    "billing", "damage_claim", "address_change", "pickup_booking", "delay_reason", "general",
]

SCENARIO_CHATS = [
    # (intent, customer_text, agent_reply_template, confidence, needs_human)
    ("tracking", "Where is my shipment {ref}?", "{ref} is currently {last_milestone} at {last_location}. Next event: {next_milestone} on {next_eta}.", 0.95, False),
    ("eta", "What is the ETA for {ref}?", "Latest ETA for {ref} at {destination} is {eta}. I'll notify you if it shifts.", 0.93, False),
    ("customs", "Has {ref} cleared customs?", "{customs_line}", 0.9, False),
    ("documents", "Can you send me the BL for {ref}?", "Sent BL copy for {ref} to {email}. Let me know if you need the original courier too.", 0.88, False),
    ("pod_request", "Need the POD for {ref}", "POD for {ref} is attached. Signed by consignee at {delivered_at}.", 0.9, False),
    ("reschedule", "Can we move pickup for {ref} to next Monday?", None, 0.4, True),
    ("billing", "The invoice amount on {ref} looks wrong.", None, 0.3, True),
    ("damage_claim", "Two cartons in {ref} arrived damaged.", None, 0.2, True),
    ("address_change", "Please change delivery address for {ref}.", None, 0.35, True),
    ("delay_reason", "Why is {ref} delayed?", "{ref} is held at {last_location} due to {delay_reason}. Revised ETA: {eta}.", 0.82, False),
    ("pickup_booking", "Need pickup tomorrow, 3 pallets to Rotterdam.", "Noted. Booking draft created. Operations will confirm slot within the hour.", 0.75, False),
    ("general", "What are your office hours?", "MAN Logistics desk is open 24x7 for shipment queries. Office hours for new bookings: Mon-Sat 09:00-19:00 IST.", 0.9, False),
]

DELAY_REASONS = [
    "port congestion", "adverse weather", "vessel schedule revision",
    "customs inspection hold", "equipment shortage at origin",
]

ESCALATION_CATEGORIES = {
    "reschedule": "pickup_change",
    "billing": "billing_dispute",
    "damage_claim": "claim",
    "address_change": "delivery_change",
}
VERIFICATION_REQUIRED_INTENTS = {"address_change", "reschedule", "billing"}

# Default department catalog. Editable at runtime via PUT /api/agent-config.
DEFAULT_DEPARTMENTS = [
    {
        "id": "claims",
        "name": "Claims",
        "description": "Cargo damage, loss, and insurance claims.",
        "sla_hours": 2,
        "members": [
            {"id": "USR-CLM-01", "name": "Priya Menon", "role": "Claims lead"},
            {"id": "USR-CLM-02", "name": "Rahul Das", "role": "Claims analyst"},
        ],
    },
    {
        "id": "billing",
        "name": "Billing",
        "description": "Invoice disputes, credit notes, payment reconciliation.",
        "sla_hours": 4,
        "members": [
            {"id": "USR-BIL-01", "name": "Anika Rao", "role": "Billing lead"},
            {"id": "USR-BIL-02", "name": "Vikas Iyer", "role": "AR specialist"},
        ],
    },
    {
        "id": "operations",
        "name": "Operations",
        "description": "Pickup scheduling, rerouting, address changes, last-mile exceptions.",
        "sla_hours": 2,
        "members": [
            {"id": "USR-OPS-01", "name": "Ken Tanaka", "role": "Ops supervisor"},
            {"id": "USR-OPS-02", "name": "Lena Fischer", "role": "Ops coordinator"},
            {"id": "USR-OPS-03", "name": "Marco Rossi", "role": "Ops coordinator"},
        ],
    },
    {
        "id": "customer_success",
        "name": "Customer Success",
        "description": "Fallback queue for anything the agents cannot confidently answer.",
        "sla_hours": 6,
        "members": [
            {"id": "USR-CS-01", "name": "Zainab Khan", "role": "CS lead"},
            {"id": "USR-CS-02", "name": "Arjun Patel", "role": "CS associate"},
        ],
    },
]

DEFAULT_INTENT_ROUTING = {
    "damage_claim": "claims",
    "billing": "billing",
    "address_change": "operations",
    "reschedule": "operations",
    "pickup_booking": "operations",
    "customs": "operations",
    "documents": "operations",
    "pod_request": "customer_success",
    "delay_reason": "customer_success",
    "tracking": "customer_success",
    "eta": "customer_success",
    "general": "customer_success",
}

DEFAULT_FALLBACK_DEPARTMENT = "customer_success"


def _resolve_department(intent: str, routing: dict | None = None) -> str:
    mapping = routing or DEFAULT_INTENT_ROUTING
    return mapping.get(intent) or DEFAULT_FALLBACK_DEPARTMENT


def _department_by_id(dept_id: str, departments: list[dict] | None = None) -> dict | None:
    for d in (departments or DEFAULT_DEPARTMENTS):
        if d["id"] == dept_id:
            return d
    return None


def _handoff_note(intent: str) -> str:
    if intent == "address_change":
        return "Our team will verify the new delivery details before updating the shipment."
    if intent == "reschedule":
        return "Our team will verify slot availability and confirm before changing the booking."
    if intent == "billing":
        return "Our billing team will review the details before making any correction."
    if intent == "damage_claim":
        return "Our claims team will review the case and guide you on the next steps."
    return "Our MAN Logistics team will review this and get back to you shortly."


def _make_agent_config() -> dict:
    return {
        "agent_available": True,
        "backend": os.environ.get("MAN_AGENT_BACKEND", "regex"),
        "classify_model": os.environ.get("MAN_OPENAI_CLASSIFY_MODEL", "gpt-4o-mini"),
        "reply_model": os.environ.get("MAN_OPENAI_REPLY_MODEL", "gpt-4o-mini"),
        "confidence_threshold": float(os.environ.get("MAN_AGENT_CONFIDENCE_THRESHOLD", "0.7")),
        "escalate_categories": list(ESCALATION_CATEGORIES.values()),
        "auto_intents": ["tracking", "eta", "customs", "documents", "pod_request", "delay_reason", "pickup_booking", "general"],
        "hard_escalate_intents": ["damage_claim", "billing", "address_change", "reschedule"],
        "intent_routing": dict(DEFAULT_INTENT_ROUTING),
        "fallback_department": DEFAULT_FALLBACK_DEPARTMENT,
        "departments": [dict(d, members=[dict(m) for m in d["members"]]) for d in DEFAULT_DEPARTMENTS],
        "editable": True,
        "version": 1,
        "updated_at": None,
        "agents": [
            {
                "id": "triage",
                "name": "Triage Agent",
                "role": "Reads the incoming WhatsApp message. Classifies intent. Detects ambiguity: missing shipment ref when customer has multiple active shipments. If ambiguous, asks the customer which shipment(s) they mean.",
                "tools": ["get_customer_shipments"],
                "outputs": ["intent", "confidence", "ambiguous", "candidate_shipments"],
            },
            {
                "id": "resolver",
                "name": "Resolver Agent",
                "role": "Given a clear intent + shipment, pulls live data from tracking tools and drafts the customer reply. Self-scores its confidence.",
                "tools": ["get_shipment", "get_pod", "get_documents", "get_invoice", "get_exceptions"],
                "outputs": ["draft_reply", "grounded_fields", "confidence", "proposed_decision"],
            },
            {
                "id": "supervisor",
                "name": "Supervisor Agent",
                "role": "Second-checks every proposed escalation. Re-reads the tracking data and the draft. If the resolver could have answered from data, overrides back to auto-send. Only escalates what truly needs a human. Always writes a customer-facing acknowledgment even when escalating, so the customer is never left silent.",
                "tools": ["get_shipment", "get_exceptions", "get_invoice"],
                "outputs": ["final_decision", "human_needed_reason", "customer_ack"],
            },
            {
                "id": "nudge",
                "name": "Nudge Agent",
                "role": "Watches tracking events. Fires outbound messages on ETA slip, customs cleared, POD ready, documents missing, out-for-delivery.",
                "tools": ["get_shipment", "get_exceptions"],
                "outputs": ["nudge_draft", "rule_id"],
            },
        ],
        "tone_by_tier": {
            "Platinum": "formal, named greeting, signed off by account manager",
            "Gold": "warm, first-name greeting",
            "Silver": "concise, professional",
            "Standard": "concise, professional",
        },
        "tools": [
            {"name": "get_shipment", "desc": "Fetch live shipment by ref from tracking system"},
            {"name": "get_customer_shipments", "desc": "List recent shipments for a customer"},
            {"name": "get_pod", "desc": "Fetch proof-of-delivery asset"},
            {"name": "get_documents", "desc": "Fetch ready/pending shipment documents"},
            {"name": "get_invoice", "desc": "Fetch invoice line items"},
            {"name": "get_exceptions", "desc": "Fetch delay/hold reasons for a shipment"},
        ],
        "nudge_rules": [
            {"id": "eta_slip", "trigger": "delay_minutes increases > 180", "action": "Notify customer of revised ETA + reason"},
            {"id": "customs_cleared", "trigger": "last_event_code becomes customs_import", "action": "Send cleared + OFD notice"},
            {"id": "pod_ready", "trigger": "status becomes delivered", "action": "Send POD automatically"},
            {"id": "doc_missing", "trigger": "BL not ready 24h before vessel ETD", "action": "Remind shipper for docs"},
            {"id": "ofd_arrival", "trigger": "out_for_delivery set", "action": "Send window + driver contact"},
        ],
    }


def _pick(rng: random.Random, seq: list) -> Any:
    return seq[rng.randrange(len(seq))]


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _make_customers(rng: random.Random) -> list[dict]:
    out = []
    for idx, name in enumerate(CUSTOMER_NAMES, start=1):
        out.append({
            "id": f"CUST-{idx:03d}",
            "name": name,
            "contact_person": _pick(rng, ["Priya Sharma", "Rahul Verma", "Anika Rao", "Ken Tanaka", "Lena Fischer", "Marco Rossi", "Zainab Khan"]),
            "phone": f"+91-9{rng.randint(100000000, 999999999)}",
            "email": f"ops@{name.lower().replace(' & co.', '').replace(' ', '').replace('.', '')}.com",
            "country": _pick(rng, ["IN", "US", "DE", "SG", "AE", "VN"]),
            "tier": _pick(rng, ["Platinum", "Gold", "Silver", "Standard"]),
            "active_shipments": 0,
        })
    return out


def _milestones_for(mode: str) -> list[tuple[str, str, str]]:
    if mode == "Air":
        return MILESTONES_AIR
    return MILESTONES_SEA


def _make_shipments(rng: random.Random, customers: list[dict], now: datetime) -> list[dict]:
    shipments = []
    for idx in range(1, 36):
        mode = _pick(rng, MODES)
        origin, origin_code = _pick(rng, ORIGINS)
        destination, dest_code = _pick(rng, DESTINATIONS)
        while destination == origin:
            destination, dest_code = _pick(rng, DESTINATIONS)
        customer = customers[idx - 1] if idx <= len(customers) else _pick(rng, customers)
        carrier = _pick(rng, CARRIERS)
        commodity = _pick(rng, COMMODITIES)
        tpl = _milestones_for(mode)
        total_days = rng.randint(6, 34) if mode != "Air" else rng.randint(2, 6)
        booked_at = now - timedelta(days=rng.randint(0, total_days + 5))
        eta = booked_at + timedelta(days=total_days)

        progress_idx = rng.randint(0, len(tpl) - 1)
        events = []
        # spread events across booked_at..eta
        step = (eta - booked_at) / max(len(tpl) - 1, 1)
        for i, (code, label, loc_hint) in enumerate(tpl):
            ts = booked_at + step * i
            completed = i <= progress_idx
            location = loc_hint
            if "origin" in loc_hint.lower() or "shipper" in loc_hint.lower():
                location = f"{loc_hint} ({origin})"
            if "destination" in loc_hint.lower() or "consignee" in loc_hint.lower() or "last-mile" in loc_hint.lower():
                location = f"{loc_hint} ({destination})"
            events.append({
                "code": code,
                "label": label,
                "location": location,
                "timestamp": _iso(ts),
                "completed": completed,
            })

        last_event = events[progress_idx]
        next_event = events[progress_idx + 1] if progress_idx + 1 < len(events) else None
        status_map = {
            "booking_confirmed": "booked",
            "pickup_scheduled": "booked",
            "picked_up": "in_transit",
            "arrived_cfs": "in_transit",
            "customs_export": "customs",
            "loaded_vessel": "in_transit",
            "in_transit": "in_transit",
            "arrived_airport": "in_transit",
            "departed": "in_transit",
            "arrived_dest": "in_transit",
            "arrived_pod": "at_destination",
            "customs_import": "customs",
            "out_for_delivery": "out_for_delivery",
            "delivered": "delivered",
        }
        status = status_map.get(last_event["code"], "in_transit")

        delay_minutes = 0
        delay_reason = None
        if rng.random() < 0.35 and status not in ("delivered",):
            delay_minutes = rng.choice([360, 720, 1440, 2880])
            delay_reason = _pick(rng, DELAY_REASONS)
            eta = eta + timedelta(minutes=delay_minutes)

        ref = f"MAN{rng.randint(100000, 999999)}"
        shipments.append({
            "id": f"SHP-{idx:03d}",
            "ref": ref,
            "customer_id": customer["id"],
            "customer_name": customer["name"],
            "mode": mode,
            "carrier": carrier,
            "commodity": commodity,
            "origin": origin,
            "origin_code": origin_code,
            "destination": destination,
            "destination_code": dest_code,
            "booked_at": _iso(booked_at),
            "eta": _iso(eta),
            "status": status,
            "last_event_code": last_event["code"],
            "last_event_label": last_event["label"],
            "last_location": last_event["location"],
            "last_event_at": last_event["timestamp"],
            "next_event_code": next_event["code"] if next_event else None,
            "next_event_label": next_event["label"] if next_event else None,
            "next_event_at": next_event["timestamp"] if next_event else None,
            "weight_kg": rng.randint(80, 22000),
            "volume_cbm": round(rng.uniform(1.0, 68.0), 2),
            "containers": rng.choice([1, 1, 1, 2, 3]) if mode.startswith("Sea") else 0,
            "incoterm": _pick(rng, ["FOB", "CIF", "DAP", "DDP", "EXW"]),
            "invoice_value_usd": rng.randint(4200, 480000),
            "delay_minutes": delay_minutes,
            "delay_reason": delay_reason,
            "documents": [
                {"type": "Commercial Invoice", "ready": True},
                {"type": "Packing List", "ready": True},
                {"type": "Bill of Lading", "ready": last_event["code"] in ("loaded_vessel", "in_transit", "arrived_pod", "customs_import", "out_for_delivery", "delivered")},
                {"type": "Certificate of Origin", "ready": rng.random() < 0.7},
                {"type": "POD", "ready": status == "delivered"},
            ],
            "events": events,
        })
        customer["active_shipments"] += 1 if status != "delivered" else 0
    return shipments


def _format_customs_line(shipment: dict) -> str:
    code = shipment["last_event_code"]
    ref = shipment["ref"]
    if code in ("customs_import", "out_for_delivery", "delivered"):
        return f"Yes, {ref} cleared import customs at {shipment['destination']}. Out for delivery or already delivered."
    if code == "customs_export":
        return f"{ref} cleared export customs at {shipment['origin']}. Vessel loading next."
    if code == "arrived_pod":
        return f"{ref} has arrived at {shipment['destination']}. Import customs filing is in progress."
    return f"{ref} has not reached customs yet. Current status: {shipment['last_event_label']} at {shipment['last_location']}."


def _chat_reply(scenario: tuple, shipment: dict, customer: dict) -> tuple[str | None, dict]:
    intent, _text, reply_tpl, confidence, needs_human = scenario
    if not reply_tpl:
        return None, {"intent": intent, "confidence": confidence, "needs_human": needs_human}
    ctx = {
        "ref": shipment["ref"],
        "last_milestone": shipment["last_event_label"].lower(),
        "last_location": shipment["last_location"],
        "next_milestone": shipment.get("next_event_label") or "delivery",
        "next_eta": (shipment.get("next_event_at") or shipment["eta"])[:16].replace("T", " "),
        "destination": shipment["destination"],
        "eta": shipment["eta"][:16].replace("T", " "),
        "email": customer["email"],
        "customs_line": _format_customs_line(shipment),
        "delivered_at": shipment["eta"][:16].replace("T", " "),
        "delay_reason": shipment.get("delay_reason") or "a routing update",
    }
    try:
        return reply_tpl.format(**ctx), {"intent": intent, "confidence": confidence, "needs_human": needs_human}
    except KeyError:
        return reply_tpl, {"intent": intent, "confidence": confidence, "needs_human": needs_human}


def _make_chat_threads(rng: random.Random, customers: list[dict], shipments: list[dict], now: datetime) -> tuple[list[dict], list[dict], list[dict]]:
    """Returns (messages, tickets, agent_actions)."""
    messages: list[dict] = []
    tickets: list[dict] = []
    actions: list[dict] = []
    msg_seq = 0
    tkt_seq = 0
    act_seq = 0

    # ensure every customer has >=1 thread
    for customer in customers:
        cust_shipments = [s for s in shipments if s["customer_id"] == customer["id"]]
        if not cust_shipments:
            cust_shipments = [_pick(rng, shipments)]
        turns = rng.randint(2, 5)
        base_time = now - timedelta(hours=rng.randint(1, 96))
        for _ in range(turns):
            shipment = _pick(rng, cust_shipments)
            scenario = _pick(rng, SCENARIO_CHATS)
            intent, text_tpl, _reply_tpl, confidence, needs_human = scenario
            customer_text = text_tpl.format(ref=shipment["ref"])
            msg_seq += 1
            base_time += timedelta(minutes=rng.randint(3, 240))
            in_msg = {
                "id": f"MSG-{msg_seq:04d}",
                "shipment_id": shipment["id"],
                "shipment_ref": shipment["ref"],
                "customer_id": customer["id"],
                "customer_name": customer["name"],
                "direction": "incoming",
                "text": customer_text,
                "timestamp": _iso(base_time),
                "intent": intent,
                "confidence": confidence,
                "channel": "whatsapp",
                "source": "customer",
            }
            messages.append(in_msg)

            reply_text, meta = _chat_reply(scenario, shipment, customer)
            if reply_text and not needs_human:
                msg_seq += 1
                base_time += timedelta(seconds=rng.randint(8, 45))
                out_msg = {
                    "id": f"MSG-{msg_seq:04d}",
                    "shipment_id": shipment["id"],
                    "shipment_ref": shipment["ref"],
                    "customer_id": customer["id"],
                    "customer_name": customer["name"],
                    "direction": "outgoing",
                    "text": reply_text,
                    "timestamp": _iso(base_time),
                    "intent": intent,
                    "confidence": meta["confidence"],
                    "channel": "whatsapp",
                    "source": "agent",
                    "reply_to": in_msg["id"],
                }
                messages.append(out_msg)
                act_seq += 1
                actions.append({
                    "id": f"ACT-{act_seq:04d}",
                    "kind": "auto_reply",
                    "intent": intent,
                    "shipment_id": shipment["id"],
                    "shipment_ref": shipment["ref"],
                    "customer_id": customer["id"],
                    "confidence": meta["confidence"],
                    "timestamp": out_msg["timestamp"],
                    "summary": f"Agent auto-replied to {intent} query on {shipment['ref']}.",
                })
            else:
                tkt_seq += 1
                status = _pick(rng, ["pending", "in_progress", "resolved"])
                in_progress_at = None
                resolved_at = None
                if status in ("in_progress", "resolved"):
                    in_progress_at = _iso(base_time + timedelta(minutes=rng.randint(5, 60)))
                if status == "resolved":
                    resolved_at = _iso(base_time + timedelta(hours=rng.randint(1, 24)))
                dept_id = _resolve_department(intent)
                dept = _department_by_id(dept_id) or {"sla_hours": 4, "members": []}
                assignee = None
                if status in ("in_progress", "resolved") and dept["members"]:
                    m = _pick(rng, dept["members"])
                    assignee = {"id": m["id"], "name": m["name"]}
                tickets.append({
                    "id": f"TKT-{tkt_seq:04d}",
                    "message_id": in_msg["id"],
                    "shipment_id": shipment["id"],
                    "shipment_ref": shipment["ref"],
                    "customer_id": customer["id"],
                    "customer_name": customer["name"],
                    "intent": intent,
                    "category": ESCALATION_CATEGORIES.get(intent, "general"),
                    "text": customer_text,
                    "timestamp": in_msg["timestamp"],
                    "status": status,
                    "in_progress_at": in_progress_at,
                    "resolved_at": resolved_at,
                    "priority": _pick(rng, ["low", "normal", "high"]) if intent not in ("damage_claim", "billing") else "high",
                    "sla_due_at": _iso(base_time + timedelta(hours=dept.get("sla_hours", 4))),
                    "sla_hours": dept.get("sla_hours", 4),
                    "verification_required": intent in VERIFICATION_REQUIRED_INTENTS,
                    "handoff_note": _handoff_note(intent),
                    "department_id": dept_id,
                    "department_name": dept.get("name") or dept_id,
                    "assignee": assignee,
                })
                act_seq += 1
                actions.append({
                    "id": f"ACT-{act_seq:04d}",
                    "kind": "escalated",
                    "intent": intent,
                    "shipment_id": shipment["id"],
                    "shipment_ref": shipment["ref"],
                    "customer_id": customer["id"],
                    "confidence": meta["confidence"],
                    "timestamp": in_msg["timestamp"],
                    "summary": f"Escalated {intent} on {shipment['ref']} - confidence {int(meta['confidence']*100)}% below threshold.",
                })

    messages.sort(key=lambda m: m["timestamp"])
    tickets.sort(key=lambda t: t["timestamp"], reverse=True)
    actions.sort(key=lambda a: a["timestamp"], reverse=True)
    return messages, tickets, actions


def _tool_calls_for(intent: str, shipment: dict | None, customer: dict) -> list[dict]:
    calls = [{
        "tool": "get_customer_shipments",
        "args": {"customer_id": customer["id"]},
        "ok": True,
        "latency_ms": 42,
        "result_summary": f"{len([1])} recent shipments",
    }]
    if shipment:
        calls.append({
            "tool": "get_shipment",
            "args": {"ref": shipment["ref"]},
            "ok": True,
            "latency_ms": 58,
            "result_summary": f"{shipment['last_event_label']} at {shipment['last_location']}",
        })
    if intent == "customs" and shipment:
        calls.append({"tool": "get_exceptions", "args": {"ref": shipment["ref"]}, "ok": True, "latency_ms": 37, "result_summary": "no holds"})
    if intent == "documents" and shipment:
        calls.append({"tool": "get_documents", "args": {"ref": shipment["ref"]}, "ok": True, "latency_ms": 29, "result_summary": f"{sum(1 for d in shipment['documents'] if d['ready'])}/{len(shipment['documents'])} ready"})
    if intent == "pod_request" and shipment:
        calls.append({"tool": "get_pod", "args": {"ref": shipment["ref"]}, "ok": shipment["status"] == "delivered", "latency_ms": 44, "result_summary": "POD available" if shipment["status"] == "delivered" else "not delivered yet"})
    if intent == "delay_reason" and shipment:
        calls.append({"tool": "get_exceptions", "args": {"ref": shipment["ref"]}, "ok": True, "latency_ms": 41, "result_summary": shipment.get("delay_reason") or "on time"})
    if intent == "billing" and shipment:
        calls.append({"tool": "get_invoice", "args": {"ref": shipment["ref"]}, "ok": True, "latency_ms": 61, "result_summary": "line items fetched"})
    return calls


HARD_ESCALATE = {"damage_claim", "billing", "address_change", "reschedule"}


def _make_agent_runs(messages: list[dict], shipments: list[dict], customers: list[dict]) -> list[dict]:
    ship_by_id = {s["id"]: s for s in shipments}
    cust_by_id = {c["id"]: c for c in customers}
    ship_by_customer: dict[str, list[dict]] = {}
    for s in shipments:
        ship_by_customer.setdefault(s["customer_id"], []).append(s)

    runs: list[dict] = []
    for idx, msg in enumerate([m for m in messages if m["direction"] == "incoming"], start=1):
        shipment = ship_by_id.get(msg.get("shipment_id"))
        customer = cust_by_id.get(msg["customer_id"])
        if not customer:
            continue
        intent = msg["intent"]
        confidence = msg["confidence"]
        active_shipments = [s for s in ship_by_customer.get(customer["id"], []) if s["status"] != "delivered"]
        ref_in_text = bool(msg.get("shipment_ref"))
        ambiguous = (
            intent in {"tracking", "eta", "customs", "documents", "pod_request", "delay_reason"}
            and not ref_in_text
            and len(active_shipments) > 1
        )

        pipeline = _build_pipeline(
            intent=intent,
            confidence=confidence,
            customer=customer,
            shipment=shipment,
            ambiguous=ambiguous,
            active_shipments=active_shipments,
            rng=random.Random(idx),
        )
        final_stage = pipeline[-1]
        total_latency = sum(st["latency_ms"] for st in pipeline)
        runs.append({
            "id": f"RUN-{idx:04d}",
            "message_id": msg["id"],
            "customer_id": customer["id"],
            "customer_name": customer["name"],
            "shipment_ref": msg.get("shipment_ref"),
            "timestamp": msg["timestamp"],
            "intent": intent,
            "confidence": confidence,
            "pipeline": pipeline,
            "decision": final_stage["decision"],
            "reasoning": final_stage["reasoning"],
            "tool_calls": [tc for st in pipeline for tc in st.get("tool_calls", [])],
            "grounded_fields": _grounded_fields(intent, shipment),
            "latency_ms": total_latency,
        })
    return runs


def _build_pipeline(*, intent: str, confidence: float, customer: dict, shipment: dict | None,
                    ambiguous: bool, active_shipments: list[dict], rng: random.Random) -> list[dict]:
    stages: list[dict] = []

    triage_calls = [{
        "tool": "get_customer_shipments",
        "args": {"customer_id": customer["id"]},
        "ok": True,
        "latency_ms": rng.randint(30, 55),
        "result_summary": f"{len(active_shipments)} active shipments",
    }]
    if ambiguous:
        refs = ", ".join(s["ref"] for s in active_shipments[:4])
        stages.append({
            "agent": "triage",
            "decision": "clarify",
            "reasoning": f"{len(active_shipments)} active shipments on file, customer did not name one. Asking which shipment(s) they want an update on.",
            "tool_calls": triage_calls,
            "latency_ms": sum(c["latency_ms"] for c in triage_calls) + rng.randint(80, 180),
            "output": {"candidate_refs": [s["ref"] for s in active_shipments[:4]], "ask": f"Which shipment - {refs}? Or all of them?"},
        })
        return stages

    stages.append({
        "agent": "triage",
        "decision": "route_to_resolver",
        "reasoning": f"Intent classified as {intent} at {int(confidence*100)}% confidence. Clear target shipment, handing to resolver.",
        "tool_calls": triage_calls,
        "latency_ms": sum(c["latency_ms"] for c in triage_calls) + rng.randint(80, 180),
        "output": {"intent": intent, "confidence": confidence},
    })

    resolver_calls = _tool_calls_for(intent, shipment, customer)
    resolver_proposed = "escalate" if (intent in HARD_ESCALATE or confidence < 0.7) else "auto_send"
    stages.append({
        "agent": "resolver",
        "decision": resolver_proposed,
        "reasoning": (
            f"No tracking answer covers {intent}; proposing escalation." if resolver_proposed == "escalate"
            else f"Drafted reply grounded in {', '.join(_grounded_fields(intent, shipment)) or 'tracking data'}. Self-confidence {int(confidence*100)}%."
        ),
        "tool_calls": resolver_calls,
        "latency_ms": sum(c["latency_ms"] for c in resolver_calls) + rng.randint(120, 260),
        "output": {"proposed_decision": resolver_proposed},
    })

    sup_calls: list[dict] = []
    if resolver_proposed == "escalate":
        sup_calls.append({
            "tool": "get_shipment" if shipment else "get_customer_shipments",
            "args": {"ref": shipment["ref"]} if shipment else {"customer_id": customer["id"]},
            "ok": True,
            "latency_ms": rng.randint(35, 70),
            "result_summary": "re-read for override check",
        })
        if intent in HARD_ESCALATE:
            final = "escalate"
            reasoning = f"Confirmed: {intent} needs human judgement (policy, verification, or compensation). Writing customer acknowledgment and routing to ops."
        elif confidence >= 0.55 and shipment:
            final = "auto_send"
            reasoning = "Override: tracking data does answer this. Resolver was over-cautious. Releasing draft as auto-send."
        else:
            final = "escalate"
            reasoning = "Supervisor would not release a weak answer. No draft holds allowed, so this run routes directly to humans."
    else:
        final = "auto_send"
        reasoning = "Draft verified against tracking data. No override needed."

    stages.append({
        "agent": "supervisor",
        "decision": final,
        "reasoning": reasoning,
        "tool_calls": sup_calls,
        "latency_ms": sum(c["latency_ms"] for c in sup_calls) + rng.randint(90, 200),
        "output": {"final_decision": final},
    })
    return stages


def _grounded_fields(intent: str, shipment: dict | None) -> list[str]:
    if not shipment:
        return []
    if intent == "tracking":
        return ["last_event_label", "last_location", "next_event_label", "next_event_at"]
    if intent == "eta":
        return ["eta", "destination", "delay_reason"]
    if intent == "customs":
        return ["last_event_code", "destination", "origin"]
    if intent == "documents":
        return ["documents"]
    if intent == "pod_request":
        return ["status", "eta"]
    if intent == "delay_reason":
        return ["delay_reason", "eta", "last_event_label"]
    return []


def _make_approvals(rng: random.Random, messages: list[dict], customers: list[dict], shipments: list[dict], now: datetime) -> list[dict]:
    return []


def _approval_draft(intent: str, shipment: dict | None, customer: dict) -> str:
    name = customer["contact_person"].split()[0]
    if not shipment:
        return f"Hi {name}, could you share the booking reference? I'll pull the latest status and come back to you right away."
    ref = shipment["ref"]
    if intent == "tracking":
        return f"Hi {name}, {ref} is currently '{shipment['last_event_label']}' at {shipment['last_location']}. Next milestone: {shipment.get('next_event_label') or 'delivery'}. I'll keep you posted."
    if intent == "eta":
        return f"Hi {name}, latest ETA for {ref} at {shipment['destination']} is {shipment['eta'][:16].replace('T',' ')}. Let me know if you'd like live notifications."
    if intent == "customs":
        return f"Hi {name}, sharing an update on {ref}: {_format_customs_line(shipment)}"
    if intent == "documents":
        ready = [d["type"] for d in shipment["documents"] if d["ready"]]
        return f"Hi {name}, ready docs for {ref}: {', '.join(ready) or 'none yet'}. I can email to {customer['email']} now."
    if intent == "delay_reason":
        return f"Hi {name}, {ref} is running late due to {shipment.get('delay_reason') or 'a schedule revision'}. Revised ETA: {shipment['eta'][:16].replace('T',' ')}."
    return f"Hi {name}, noted on {ref}. I'll pull the details and get back within the hour."


def _make_nudges(rng: random.Random, shipments: list[dict], now: datetime) -> list[dict]:
    out: list[dict] = []
    idx = 0
    for s in shipments:
        if s["delay_minutes"] > 180 and s["status"] != "delivered":
            idx += 1
            out.append({
                "id": f"NDG-{idx:03d}",
                "rule_id": "eta_slip",
                "rule_label": "ETA slip alert",
                "shipment_ref": s["ref"],
                "customer_id": s["customer_id"],
                "customer_name": s["customer_name"],
                "trigger": f"Delay grew to {s['delay_minutes']//60}h due to {s['delay_reason']}",
                "draft": f"Heads up: {s['ref']} ETA shifted to {s['eta'][:16].replace('T',' ')} due to {s['delay_reason']}. We'll keep monitoring and update you.",
                "status": _pick(rng, ["scheduled", "sent", "sent", "pending_approval"]),
                "scheduled_at": _iso(now + timedelta(minutes=rng.randint(5, 60))),
                "channel": "whatsapp",
            })
        if s["last_event_code"] == "customs_import":
            idx += 1
            out.append({
                "id": f"NDG-{idx:03d}",
                "rule_id": "customs_cleared",
                "rule_label": "Customs cleared",
                "shipment_ref": s["ref"],
                "customer_id": s["customer_id"],
                "customer_name": s["customer_name"],
                "trigger": "Import customs cleared event",
                "draft": f"{s['ref']} has cleared import customs at {s['destination']}. Out for delivery shortly.",
                "status": "sent",
                "scheduled_at": s["last_event_at"],
                "channel": "whatsapp",
            })
        if s["status"] == "out_for_delivery":
            idx += 1
            out.append({
                "id": f"NDG-{idx:03d}",
                "rule_id": "ofd_arrival",
                "rule_label": "Out-for-delivery window",
                "shipment_ref": s["ref"],
                "customer_id": s["customer_id"],
                "customer_name": s["customer_name"],
                "trigger": "Shipment marked out_for_delivery",
                "draft": f"{s['ref']} is out for delivery today. Driver will call ~30 min before arrival.",
                "status": _pick(rng, ["scheduled", "sent"]),
                "scheduled_at": _iso(now + timedelta(minutes=rng.randint(10, 120))),
                "channel": "whatsapp",
            })
        if s["status"] == "delivered":
            idx += 1
            out.append({
                "id": f"NDG-{idx:03d}",
                "rule_id": "pod_ready",
                "rule_label": "POD auto-send",
                "shipment_ref": s["ref"],
                "customer_id": s["customer_id"],
                "customer_name": s["customer_name"],
                "trigger": "Delivery confirmed",
                "draft": f"{s['ref']} delivered. POD attached for your records.",
                "status": "sent",
                "scheduled_at": s["eta"],
                "channel": "whatsapp",
            })
    return out[:40]


def _make_broadcasts(rng: random.Random, customers: list[dict], shipments: list[dict], now: datetime) -> list[dict]:
    out = []
    templates = [
        ("ETA revision", "{ref}: revised ETA {eta}. Reason: {reason}."),
        ("Customs cleared", "{ref}: import customs cleared. Out for delivery next."),
        ("Port congestion advisory", "Heads-up: {origin} facing congestion. Expect 24-48h impact on affected bookings."),
        ("Holiday schedule", "Office closed on upcoming public holiday. Auto-tracking continues 24x7."),
    ]
    for i, (title, tpl) in enumerate(templates, start=1):
        shipment = _pick(rng, shipments)
        out.append({
            "id": f"BRD-{i:02d}",
            "title": title,
            "body": tpl.format(ref=shipment["ref"], eta=shipment["eta"][:16].replace("T", " "), reason=shipment.get("delay_reason") or "schedule revision", origin=shipment["origin"]),
            "sent_at": _iso(now - timedelta(hours=rng.randint(1, 72))),
            "audience": _pick(rng, ["All customers", "Ocean FCL customers", "Platinum tier", "Affected shipments only"]),
            "read_rate": round(rng.uniform(0.35, 0.92), 2),
        })
    return out


def _make_kpis(shipments: list[dict], messages: list[dict], tickets: list[dict], actions: list[dict], approvals: list[dict] | None = None, nudges: list[dict] | None = None) -> dict:
    approvals = approvals or []
    nudges = nudges or []
    auto_replies = sum(1 for a in actions if a["kind"] == "auto_reply")
    escalations = sum(1 for a in actions if a["kind"] == "escalated")
    total_customer = sum(1 for m in messages if m.get("source") == "customer")
    deflection = round(auto_replies / total_customer, 3) if total_customer else 0
    pending_tkts = sum(1 for t in tickets if t["status"] == "pending")
    pending_approvals = sum(1 for a in approvals if a["status"] == "pending")
    clarifications_open = 0
    for msg in messages:
        if msg.get("source") != "agent" or not msg.get("selector_refs"):
            continue
        responded = any(
            later.get("source") == "customer"
            and later.get("customer_id") == msg.get("customer_id")
            and later.get("timestamp", "") > msg.get("timestamp", "")
            for later in messages
        )
        if not responded:
            clarifications_open += 1
    dept_counts: dict[str, int] = {}
    for t in tickets:
        if t["status"] == "resolved":
            continue
        did = t.get("department_id") or DEFAULT_FALLBACK_DEPARTMENT
        dept_counts[did] = dept_counts.get(did, 0) + 1
    sla_breached = 0
    now_iso = datetime.utcnow().replace(microsecond=0).isoformat()
    for t in tickets:
        if t["status"] == "resolved":
            continue
        if t.get("sla_due_at") and t["sla_due_at"] < now_iso:
            sla_breached += 1
    nudges_sent = sum(1 for n in nudges if n["status"] == "sent")
    avg_confidence = round(sum(a["confidence"] for a in actions if a["kind"] == "auto_reply") / max(auto_replies, 1), 2)
    # ~90s saved per auto-reply + nudge sent (minion task replaced)
    minutes_saved = round((auto_replies + nudges_sent) * 1.5, 1)
    return {
        "messages_handled": total_customer,
        "auto_resolved": auto_replies,
        "deflection_rate": deflection,
        "pending_approvals": pending_approvals,
        "clarifications_open": clarifications_open,
        "pending_handoffs": pending_tkts,
        "nudges_sent": nudges_sent,
        "nudges_queued": sum(1 for n in nudges if n["status"] in ("scheduled", "pending_approval")),
        "agent_confidence_avg": avg_confidence,
        "escalations": escalations,
        "minutes_saved": minutes_saved,
        "fte_hours_saved": round(minutes_saved / 60, 1),
        "handoffs_by_department": dept_counts,
        "sla_breached": sla_breached,
    }


def generate_dataset(seed: int = 42) -> dict[str, Any]:
    rng = random.Random(seed)
    now = datetime(2026, 4, 20, 10, 30, 0)
    customers = _make_customers(rng)
    shipments = _make_shipments(rng, customers, now)
    messages, tickets, actions = _make_chat_threads(rng, customers, shipments, now)
    broadcasts = _make_broadcasts(rng, customers, shipments, now)
    nudges = _make_nudges(rng, shipments, now)
    approvals = _make_approvals(rng, messages, customers, shipments, now)
    agent_runs = _make_agent_runs(messages, shipments, customers)
    kpis = _make_kpis(shipments, messages, tickets, actions, approvals=approvals, nudges=nudges)
    return {
        "generated_at": _iso(datetime.utcnow().replace(microsecond=0)),
        "seed": seed,
        "customers": customers,
        "shipments": shipments,
        "messages": messages,
        "tickets": tickets,
        "agent_actions": actions,
        "broadcasts": broadcasts,
        "nudges": nudges,
        "approvals": approvals,
        "agent_runs": agent_runs,
        "kpis": kpis,
        "agent_config": _make_agent_config(),
    }


if __name__ == "__main__":
    import json
    data = generate_dataset(42)
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in data.items()}, indent=2, default=str))
