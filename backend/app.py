"""Flask API for MAN Logistics POC.

Serves mock shipment, chat, ticket, and agent-action data from data_seed.
State is in-memory: regenerated on reseed or process restart.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
import json

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

load_dotenv(Path(__file__).with_name(".env"))

try:
    from keep_alive import init_keep_alive
    KEEP_ALIVE_AVAILABLE = True
except ImportError as exc:
    print(f"Keep-alive service not available: {exc}")
    KEEP_ALIVE_AVAILABLE = False

from agent import classify as oai_classify, compose as oai_compose
from data_seed import (
    generate_dataset,
    ESCALATION_CATEGORIES,
    _make_agent_config,
    _resolve_department,
    _department_by_id,
    DEFAULT_FALLBACK_DEPARTMENT,
)

DATASET_FILE = Path(__file__).with_name("runtime_dataset.json")
FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
AGENT_BACKEND = os.environ.get("MAN_AGENT_BACKEND", "regex")
HARD_ESCALATE = {"damage_claim", "billing", "address_change", "reschedule"}

STATE: dict = {}


def _load_state(seed: int = 42) -> dict:
    data = generate_dataset(seed)
    DATASET_FILE.write_text(json.dumps(data, default=str, indent=2), encoding="utf-8")
    return data


def _save_state() -> None:
    DATASET_FILE.write_text(json.dumps(STATE, default=str, indent=2), encoding="utf-8")


def _ensure_state() -> None:
    global STATE
    if STATE:
        return
    if DATASET_FILE.exists():
        try:
            STATE = json.loads(DATASET_FILE.read_text(encoding="utf-8"))
            if not STATE.get("agent_config"):
                STATE["agent_config"] = _make_agent_config()
            required_keys = ("nudges", "approvals", "agent_runs")
            if not all(k in STATE for k in required_keys):
                STATE = _load_state(STATE.get("seed", 42))
            return
        except json.JSONDecodeError:
            pass
    STATE = _load_state(42)


def _config_departments() -> list[dict]:
    cfg = STATE.get("agent_config") or {}
    return cfg.get("departments") or []


def _config_routing() -> dict:
    cfg = STATE.get("agent_config") or {}
    return cfg.get("intent_routing") or {}


def _route_ticket(intent: str) -> tuple[str, dict | None]:
    dept_id = _resolve_department(intent, _config_routing())
    dept = _department_by_id(dept_id, _config_departments())
    return dept_id, dept


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _next_id(prefix: str, collection: list[dict]) -> str:
    nums = [0]
    for row in collection:
        m = re.match(rf"{prefix}-(\d+)", row.get("id", ""))
        if m:
            nums.append(int(m.group(1)))
    return f"{prefix}-{max(nums) + 1:04d}"


def _find(collection: list[dict], id_value: str) -> dict | None:
    for row in collection:
        if row.get("id") == id_value:
            return row
    return None


def _recompute_kpis() -> None:
    from data_seed import _make_kpis  # reuse
    STATE["kpis"] = _make_kpis(
        STATE["shipments"], STATE["messages"], STATE["tickets"], STATE["agent_actions"],
        approvals=STATE.get("approvals", []), nudges=STATE.get("nudges", []),
    )


# ---------------- Agent brain ----------------

TRACK_RE = re.compile(r"\bMAN\d{6}\b", re.IGNORECASE)
SHIPMENT_INTENTS = {"tracking", "eta", "customs", "documents", "pod_request", "delay_reason"}
VERIFICATION_REQUIRED_INTENTS = {"address_change", "reschedule", "billing"}
NULL_LIKE_REFS = {"NULL", "NONE", "NIL", "N/A", "NA", "UNDEFINED"}


def _classify(text: str) -> tuple[str, float]:
    intent, confidence, _ref_hint = _classify_with_hint(text)
    return intent, confidence


def _normalize_ref_hint(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = text.upper()
    if normalized in NULL_LIKE_REFS:
        return None
    match = TRACK_RE.search(normalized)
    return match.group(0).upper() if match else None


def _classify_with_hint(text: str, customer: dict | None = None, recent_shipments: list[dict] | None = None) -> tuple[str, float, str | None]:
    if AGENT_BACKEND == "openai":
        try:
            res = oai_classify(text, context={
                "customer": {
                    "id": customer.get("id") if customer else None,
                    "name": customer.get("name") if customer else None,
                    "tier": customer.get("tier") if customer else None,
                } if customer else None,
                "recent_shipments": recent_shipments or [],
            })
            return res["intent"], float(res["confidence"]), _normalize_ref_hint(res.get("shipment_ref_mentioned"))
        except Exception as exc:
            app.logger.warning("openai classify failed, falling back: %s", exc)
    intent, confidence = _classify_regex(text)
    return intent, confidence, None


def _classify_regex(text: str) -> tuple[str, float]:
    t = text.lower()
    if "invoice" in t and "wrong" in t or "billing" in t:
        return "billing", 0.3
    if "reschedule" in t or "move pickup" in t or "change pickup" in t:
        return "reschedule", 0.3
    if any(k in t for k in ["damage", "damaged", "broken", "missing"]):
        return "damage_claim", 0.2
    if "address" in t and "change" in t:
        return "address_change", 0.35
    if any(k in t for k in ["where is", "track", "status of", "location of", "kidhar"]):
        return "tracking", 0.93
    if "eta" in t or "when will" in t or "arrive" in t:
        return "eta", 0.9
    if "customs" in t or "clearance" in t or "clear" in t:
        return "customs", 0.88
    if "bl " in t or "bill of lading" in t or "invoice" in t and "wrong" not in t:
        return "documents", 0.85
    if "pod" in t or "proof of delivery" in t:
        return "pod_request", 0.9
    if "delay" in t or "late" in t or "why" in t:
        return "delay_reason", 0.82
    if "pickup" in t or "book" in t:
        return "pickup_booking", 0.75
    if "hours" in t or "office" in t:
        return "general", 0.85
    return "general", 0.5


def _customer_shipments(customer_id: str | None) -> list[dict]:
    if not customer_id:
        return []
    return sorted(
        [s for s in STATE["shipments"] if s["customer_id"] == customer_id],
        key=lambda s: s["last_event_at"],
        reverse=True,
    )


def _shipment_summary(shipment: dict) -> dict:
    return {
        "ref": shipment["ref"],
        "status": shipment["status"],
        "origin": shipment["origin"],
        "destination": shipment["destination"],
        "eta": shipment["eta"],
        "last_event_label": shipment["last_event_label"],
        "last_location": shipment["last_location"],
        "delay_reason": shipment.get("delay_reason"),
    }


def _resolve_shipment(text: str, customer_id: str | None, ref_hint: str | None = None) -> tuple[dict | None, dict]:
    requested_ref = _normalize_ref_hint(ref_hint)
    if not requested_ref:
        match = TRACK_RE.search(text)
        requested_ref = match.group(0).upper() if match else None

    customer_shipments = _customer_shipments(customer_id)
    recent_refs = [shipment["ref"] for shipment in customer_shipments[:3]]

    if requested_ref:
        for shipment in STATE["shipments"]:
            if shipment["ref"].upper() == requested_ref:
                return shipment, {
                    "requested_ref": requested_ref,
                    "matched_ref": shipment["ref"],
                    "exact_ref_found": True,
                    "customer_shipment_count": len(customer_shipments),
                    "recent_refs": recent_refs,
                }
        return None, {
            "requested_ref": requested_ref,
            "matched_ref": None,
            "exact_ref_found": False,
            "customer_shipment_count": len(customer_shipments),
            "recent_refs": recent_refs,
        }

    shipment = customer_shipments[0] if customer_shipments else None
    return shipment, {
        "requested_ref": None,
        "matched_ref": shipment["ref"] if shipment else None,
        "exact_ref_found": None,
        "customer_shipment_count": len(customer_shipments),
        "recent_refs": recent_refs,
    }


def _verification_required(intent: str) -> bool:
    return intent in VERIFICATION_REQUIRED_INTENTS


def _handoff_note(intent: str) -> str:
    if intent == "address_change":
        return "Our team will verify the new delivery details before updating the shipment."
    if intent == "reschedule":
        return "Our team will verify slot availability and confirm before changing the booking."
    if intent == "billing":
        return "Our billing team will review the details before making any correction."
    if intent == "damage_claim":
        return "Our claims team will review the case and guide you on the next steps."
    if intent == "pickup_booking":
        return "Our operations team will verify the booking details and confirm the next steps."
    return "Our MAN Logistics team will review this and get back to you shortly."


def _compose_reply(
    intent: str,
    shipment: dict | None,
    customer: dict | None,
    customer_text: str = "",
    lookup_context: dict | None = None,
) -> str:
    if intent in SHIPMENT_INTENTS and not shipment:
        return _compose_reply_template(intent, shipment, customer, customer_text=customer_text, lookup_context=lookup_context)
    if AGENT_BACKEND == "openai":
        try:
            return oai_compose(intent, customer_text, shipment, customer, context=lookup_context)
        except Exception as exc:
            app.logger.warning("openai compose failed, falling back: %s", exc)
    return _compose_reply_template(intent, shipment, customer, customer_text=customer_text, lookup_context=lookup_context)


def _compose_reply_template(
    intent: str,
    shipment: dict | None,
    customer: dict | None,
    customer_text: str = "",
    lookup_context: dict | None = None,
) -> str:
    lookup_context = lookup_context or {}
    requested_ref = lookup_context.get("requested_ref")
    recent_refs = lookup_context.get("recent_refs") or []
    handoff_required = bool(lookup_context.get("handoff_required"))
    verification_required = bool(lookup_context.get("verification_required"))
    handoff_note = lookup_context.get("handoff_note") or _handoff_note(intent)
    ref = shipment["ref"] if shipment else "your shipment"
    if not shipment and intent in SHIPMENT_INTENTS:
        if requested_ref and recent_refs:
            refs = ", ".join(recent_refs)
            return f"I couldn't find shipment {requested_ref} under your account. Your recent shipment references are {refs}. Please send one of those and I can share the latest update."
        if requested_ref:
            return f"I couldn't find shipment {requested_ref} under your account, and I don't see any recent shipments on file for you. Please share the correct booking reference if you have one."
        return "I couldn't find a recent shipment under your account. Please share the booking reference (starts with MAN)."
    if handoff_required:
        ref_text = ref if shipment else (requested_ref or "your shipment")
        if intent == "address_change":
            return f"I've shared your address change request for {ref_text} with the MAN Logistics team. {handoff_note}"
        if intent == "reschedule":
            return f"I've shared your pickup change request for {ref_text} with the MAN Logistics team. {handoff_note}"
        if intent == "billing":
            return f"I've logged your billing query for {ref_text} with the MAN Logistics team. {handoff_note}"
        if intent == "damage_claim":
            return f"I've logged your damage report for {ref_text} with the MAN Logistics team. {handoff_note}"
        if verification_required:
            return f"I've shared your request for {ref_text} with the MAN Logistics team. {handoff_note}"
        return f"I've shared your request for {ref_text} with the MAN Logistics team. They will get back to you shortly."
    if intent == "tracking":
        nxt = f"Next: {shipment['next_event_label']} around {(shipment['next_event_at'] or shipment['eta'])[:16].replace('T', ' ')}." if shipment.get("next_event_label") else "This is the final milestone."
        return f"{ref} is currently '{shipment['last_event_label']}' at {shipment['last_location']}. {nxt}"
    if intent == "eta":
        suffix = f" (revised due to {shipment['delay_reason']})" if shipment.get("delay_reason") else ""
        return f"Latest ETA for {ref} at {shipment['destination']} is {shipment['eta'][:16].replace('T', ' ')}{suffix}."
    if intent == "customs":
        from data_seed import _format_customs_line
        return _format_customs_line(shipment)
    if intent == "documents":
        ready_docs = [d["type"] for d in shipment["documents"] if d["ready"]]
        return f"Documents ready for {ref}: {', '.join(ready_docs) if ready_docs else 'none yet'}. I can email them to {customer['email'] if customer else 'your registered address'}."
    if intent == "pod_request":
        if shipment["status"] == "delivered":
            return f"POD for {ref} is on the way to your email. Delivered at {shipment['eta'][:16].replace('T', ' ')}."
        return f"{ref} hasn't been delivered yet. Current status: {shipment['last_event_label']}. I'll send the POD as soon as delivery is confirmed."
    if intent == "delay_reason":
        if shipment.get("delay_reason"):
            return f"{ref} is delayed due to {shipment['delay_reason']}. Revised ETA: {shipment['eta'][:16].replace('T', ' ')}."
        return f"{ref} is on schedule. Current status: {shipment['last_event_label']} at {shipment['last_location']}."
    if intent == "pickup_booking":
        return "Booking draft created. Operations will confirm the pickup slot within the hour. Please share commodity, weight, and preferred time window."
    if intent == "general":
        return "MAN Logistics desk is available 24x7 for shipment queries. New bookings: Mon-Sat 09:00-19:00 IST."
    return ""


# ---------------- App ----------------

app = Flask(__name__, static_folder=str(FRONTEND_DIST_DIR), static_url_path="")
CORS(app)

# Initialize keep-alive at module import so it also runs under Gunicorn.
if KEEP_ALIVE_AVAILABLE:
    try:
        keep_alive_service = init_keep_alive()
        if keep_alive_service is not None:
            print("Keep-alive service initialized")
    except Exception as exc:
        print(f"Failed to initialize keep-alive: {exc}")


@app.before_request
def _before():
    _ensure_state()


@app.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "generated_at": STATE.get("generated_at"),
        "seed": STATE.get("seed"),
        "kpis": STATE.get("kpis", {}),
    })


@app.post("/api/reseed")
def reseed():
    global STATE
    payload = request.get_json(silent=True) or {}
    seed = int(payload.get("seed", 42))
    STATE = _load_state(seed)
    return jsonify({"ok": True, "seed": seed, "generated_at": STATE["generated_at"]})


@app.get("/api/customers")
def customers():
    return jsonify({"items": STATE["customers"], "total": len(STATE["customers"])})


@app.get("/api/shipments")
def shipments():
    status = request.args.get("status")
    customer_id = request.args.get("customer_id")
    rows = STATE["shipments"]
    if status:
        rows = [r for r in rows if r["status"] == status]
    if customer_id:
        rows = [r for r in rows if r["customer_id"] == customer_id]
    return jsonify({"items": rows, "total": len(rows)})


@app.get("/api/shipments/<shipment_id>")
def shipment_detail(shipment_id: str):
    s = _find(STATE["shipments"], shipment_id)
    if not s:
        return jsonify({"error": "not_found"}), 404
    return jsonify(s)


@app.get("/api/messages")
def messages():
    customer_id = request.args.get("customer_id")
    shipment_id = request.args.get("shipment_id")
    limit = int(request.args.get("limit", "200"))
    rows = STATE["messages"]
    if customer_id:
        rows = [r for r in rows if r["customer_id"] == customer_id]
    if shipment_id:
        rows = [r for r in rows if r.get("shipment_id") == shipment_id]
    return jsonify({"items": rows[-limit:], "total": len(rows)})


@app.post("/api/messages")
def send_message():
    """Customer-side send. Runs triage -> resolver -> supervisor pipeline."""
    payload = request.get_json(silent=True) or {}
    customer_id = payload.get("customer_id")
    text = (payload.get("text") or "").strip()
    if not customer_id or not text:
        return jsonify({"error": "customer_id and text required"}), 400
    customer = _find(STATE["customers"], customer_id)
    if not customer:
        return jsonify({"error": "customer_not_found"}), 404

    recent_shipments = [_shipment_summary(s) for s in _customer_shipments(customer_id)[:3]]
    intent, base_conf, ref_hint = _classify_with_hint(text, customer=customer, recent_shipments=recent_shipments)
    shipment, lookup_context = _resolve_shipment(text, customer_id, ref_hint=ref_hint)
    active_shipments = [s for s in _customer_shipments(customer_id) if s["status"] != "delivered"]
    ref_in_text = bool(lookup_context.get("requested_ref") or (shipment and lookup_context.get("exact_ref_found")))
    shipment_intents = {"tracking", "eta", "customs", "documents", "pod_request", "delay_reason"}
    ambiguous = (
        intent in shipment_intents
        and not ref_in_text
        and len(active_shipments) > 1
    )

    msg_id = _next_id("MSG", STATE["messages"])
    now = _now_iso()
    in_msg = {
        "id": msg_id,
        "shipment_id": shipment["id"] if shipment else None,
        "shipment_ref": shipment["ref"] if shipment else None,
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "direction": "incoming",
        "text": text,
        "timestamp": now,
        "intent": intent,
        "confidence": base_conf,
        "channel": "whatsapp",
        "source": "customer",
    }
    STATE["messages"].append(in_msg)

    pipeline: list[dict] = []
    reply = None
    ticket = None
    final_decision = "auto_send"
    human_reason = None

    # --- Stage 1: Triage ---
    triage_calls = [{
        "tool": "get_customer_shipments",
        "args": {"customer_id": customer_id},
        "ok": True,
        "latency_ms": 42,
        "result_summary": f"{len(active_shipments)} active shipments",
    }]
    if ambiguous:
        refs = [s["ref"] for s in active_shipments[:4]]
        ask_text = (
            f"Happy to help. I see {len(active_shipments)} active shipments on your account: "
            f"{', '.join(refs)}. Which one would you like an update on - or do you want all of them?"
        )
        pipeline.append({
            "agent": "triage",
            "decision": "clarify",
            "reasoning": f"{len(active_shipments)} active shipments, no ref in message. Asking customer which shipment(s).",
            "tool_calls": triage_calls,
            "latency_ms": triage_calls[0]["latency_ms"] + 140,
            "output": {"candidate_refs": refs, "ask": ask_text},
        })
        final_decision = "clarify"
        reply = _emit_reply(
            in_msg,
            ask_text,
            intent,
            base_conf,
            source="agent",
            extra={
                "selector_refs": refs,
                "selector_intent": intent,
                "selector_prompt": "Choose a shipment",
            },
        )
        STATE["agent_actions"].insert(0, _action("clarify_asked", intent, in_msg, customer_id, base_conf, f"Triage asked customer to pick from {len(refs)} shipments."))
    else:
        pipeline.append({
            "agent": "triage",
            "decision": "route_to_resolver",
            "reasoning": f"Intent {intent} at {int(base_conf*100)}% confidence, target shipment {'known' if shipment else 'none needed'}.",
            "tool_calls": triage_calls,
            "latency_ms": triage_calls[0]["latency_ms"] + 120,
            "output": {"intent": intent, "target_ref": shipment["ref"] if shipment else None},
        })

        # --- Stage 2: Resolver ---
        resolver_calls = [{
            "tool": "get_customer_shipments",
            "args": {"customer_id": customer_id},
            "ok": True,
            "latency_ms": 38,
            "result_summary": f"{len(active_shipments)} active",
        }]
        if shipment:
            resolver_calls.append({
                "tool": "get_shipment",
                "args": {"ref": shipment["ref"]},
                "ok": True,
                "latency_ms": 55,
                "result_summary": f"{shipment['last_event_label']} at {shipment['last_location']}",
            })
        threshold = STATE["agent_config"]["confidence_threshold"]
        auto_intents = set(STATE["agent_config"]["auto_intents"])
        resolver_wants_escalate = intent in HARD_ESCALATE or intent not in auto_intents or base_conf < threshold

        lookup_context_full = {
            **lookup_context,
            "handoff_required": False,  # resolver drafts as if answering
            "verification_required": _verification_required(intent),
            "handoff_note": _handoff_note(intent),
        }
        draft_reply = _compose_reply(intent, shipment, customer, customer_text=text, lookup_context=lookup_context_full) or ""
        pipeline.append({
            "agent": "resolver",
            "decision": "propose_escalate" if resolver_wants_escalate else "propose_auto_send",
            "reasoning": (
                f"Intent {intent} not in my auto-handle list or confidence {int(base_conf*100)}% below threshold - proposing escalation."
                if resolver_wants_escalate else
                f"Drafted reply grounded in tracking data. Self-confidence {int(base_conf*100)}%."
            ),
            "tool_calls": resolver_calls,
            "latency_ms": sum(c["latency_ms"] for c in resolver_calls) + 180,
            "output": {"draft": draft_reply, "proposed_decision": "escalate" if resolver_wants_escalate else "auto_send"},
        })

        # --- Stage 3: Supervisor ---
        sup_calls: list[dict] = []
        if resolver_wants_escalate:
            sup_calls.append({
                "tool": "get_shipment" if shipment else "get_customer_shipments",
                "args": {"ref": shipment["ref"]} if shipment else {"customer_id": customer_id},
                "ok": True,
                "latency_ms": 48,
                "result_summary": "second-read for override check",
            })
            if intent in HARD_ESCALATE:
                final_decision = "escalate"
                human_reason = _handoff_note(intent)
                sup_reasoning = f"Confirmed: {intent} requires human judgement (policy/verification/compensation). Writing customer ack."
            elif shipment and base_conf >= 0.55:
                final_decision = "auto_send"
                sup_reasoning = "Override: tracking data does answer this. Releasing draft."
            else:
                final_decision = "escalate"
                human_reason = "Supervisor could not confidently release a grounded answer, so this has been routed to the MAN Logistics team."
                sup_reasoning = "Resolver could not support a safe auto-send. No draft hold allowed, so routing directly to humans."
        else:
            final_decision = "auto_send"
            sup_reasoning = "Draft verified. No override."

        pipeline.append({
            "agent": "supervisor",
            "decision": final_decision,
            "reasoning": sup_reasoning,
            "tool_calls": sup_calls,
            "latency_ms": sum(c["latency_ms"] for c in sup_calls) + 130,
            "output": {"final_decision": final_decision, "human_reason": human_reason},
        })

        # --- Act on supervisor decision ---
        if final_decision == "auto_send":
            reply = _emit_reply(in_msg, draft_reply, intent, base_conf, source="agent")
            STATE["agent_actions"].insert(0, _action("auto_reply", intent, in_msg, customer_id, base_conf, f"Agent auto-replied to {intent}" + (f" on {shipment['ref']}" if shipment else "") + "."))
        else:  # escalate
            ack_text = _handoff_ack(intent, shipment, customer)
            reply = _emit_reply(in_msg, ack_text, intent, base_conf, source="agent")
            dept_id, dept = _route_ticket(intent)
            sla_hours = (dept or {}).get("sla_hours", 4)
            sla_due = (datetime.utcnow() + timedelta(hours=sla_hours)).replace(microsecond=0).isoformat()
            ticket = {
                "id": _next_id("TKT", STATE["tickets"]),
                "message_id": msg_id,
                "shipment_id": shipment["id"] if shipment else None,
                "shipment_ref": shipment["ref"] if shipment else None,
                "customer_id": customer_id,
                "customer_name": customer["name"],
                "intent": intent,
                "category": ESCALATION_CATEGORIES.get(intent, "general"),
                "text": text,
                "timestamp": now,
                "status": "pending",
                "in_progress_at": None,
                "resolved_at": None,
                "priority": "high" if intent in ("damage_claim", "billing") else "normal",
                "sla_due_at": sla_due,
                "sla_hours": sla_hours,
                "verification_required": _verification_required(intent),
                "handoff_note": human_reason or _handoff_note(intent),
                "supervisor_note": "Supervisor confirmed human needed.",
                "department_id": dept_id,
                "department_name": (dept or {}).get("name") or dept_id,
                "assignee": None,
            }
            STATE["tickets"].insert(0, ticket)
            STATE["agent_actions"].insert(0, _action("escalated", intent, in_msg, customer_id, base_conf, f"Supervisor routed {intent} to humans, customer acknowledged."))

    run_id = _next_id("RUN", STATE.get("agent_runs", []))
    STATE.setdefault("agent_runs", []).append({
        "id": run_id,
        "message_id": msg_id,
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "shipment_ref": shipment["ref"] if shipment else None,
        "timestamp": now,
        "intent": intent,
        "confidence": base_conf,
        "pipeline": pipeline,
        "decision": final_decision,
        "reasoning": pipeline[-1]["reasoning"],
        "tool_calls": [tc for st in pipeline for tc in st.get("tool_calls", [])],
        "grounded_fields": [],
        "latency_ms": sum(st["latency_ms"] for st in pipeline),
    })

    _recompute_kpis()
    _save_state()
    return jsonify({
        "message": in_msg,
        "reply": reply,
        "ticket": ticket,
        "pipeline": pipeline,
        "decision": final_decision,
    })


def _emit_reply(in_msg: dict, text: str, intent: str, confidence: float, source: str, extra: dict | None = None) -> dict:
    out_id = _next_id("MSG", STATE["messages"])
    msg = {
        "id": out_id,
        "shipment_id": in_msg.get("shipment_id"),
        "shipment_ref": in_msg.get("shipment_ref"),
        "customer_id": in_msg["customer_id"],
        "customer_name": in_msg["customer_name"],
        "direction": "outgoing",
        "text": text,
        "timestamp": _now_iso(),
        "intent": intent,
        "confidence": confidence,
        "channel": "whatsapp",
        "source": source,
        "reply_to": in_msg["id"],
    }
    if extra:
        msg.update(extra)
    STATE["messages"].append(msg)
    return msg


def _action(kind: str, intent: str, in_msg: dict, customer_id: str, confidence: float, summary: str) -> dict:
    return {
        "id": _next_id("ACT", STATE["agent_actions"]),
        "kind": kind,
        "intent": intent,
        "shipment_id": in_msg.get("shipment_id"),
        "shipment_ref": in_msg.get("shipment_ref"),
        "customer_id": customer_id,
        "confidence": confidence,
        "timestamp": _now_iso(),
        "summary": summary,
    }


def _handoff_ack(intent: str, shipment: dict | None, customer: dict) -> str:
    name = (customer.get("contact_person") or "there").split()[0]
    ref = shipment["ref"] if shipment else "your shipment"
    if intent == "damage_claim":
        return f"Hi {name}, I'm sorry to hear about the damage on {ref}. I've flagged this to our claims team with photos requested. They'll reach out within 2 business hours."
    if intent == "billing":
        return f"Hi {name}, noted on the invoice for {ref}. Our billing team will review and come back to you with the corrected figures shortly."
    if intent == "address_change":
        return f"Hi {name}, I've passed the address change for {ref} to operations. They'll confirm the new delivery slot before we update the shipment."
    if intent == "reschedule":
        return f"Hi {name}, I've sent your pickup reschedule for {ref} to operations. They'll confirm a new slot shortly."
    return f"Hi {name}, I've passed this to the MAN Logistics team. Someone will get back to you shortly."


@app.get("/api/tickets")
def tickets():
    return jsonify({"items": STATE["tickets"], "total": len(STATE["tickets"])})


@app.post("/api/tickets/<ticket_id>/status")
def set_ticket_status(ticket_id: str):
    payload = request.get_json(silent=True) or {}
    status = payload.get("status")
    if status not in ("pending", "in_progress", "resolved"):
        return jsonify({"error": "invalid status"}), 400
    ticket = _find(STATE["tickets"], ticket_id)
    if not ticket:
        return jsonify({"error": "not_found"}), 404
    ticket["status"] = status
    now = _now_iso()
    if status == "in_progress" and not ticket.get("in_progress_at"):
        ticket["in_progress_at"] = now
    if status == "resolved":
        ticket["resolved_at"] = now
    _recompute_kpis()
    _save_state()
    return jsonify(ticket)


@app.post("/api/tickets/<ticket_id>/reply")
def reply_ticket(ticket_id: str):
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text required"}), 400
    ticket = _find(STATE["tickets"], ticket_id)
    if not ticket:
        return jsonify({"error": "not_found"}), 404
    msg_id = _next_id("MSG", STATE["messages"])
    msg = {
        "id": msg_id,
        "shipment_id": ticket["shipment_id"],
        "shipment_ref": ticket["shipment_ref"],
        "customer_id": ticket["customer_id"],
        "customer_name": ticket["customer_name"],
        "direction": "outgoing",
        "text": text,
        "timestamp": _now_iso(),
        "intent": ticket["intent"],
        "confidence": 1.0,
        "channel": "whatsapp",
        "source": "office",
        "reply_to": ticket["message_id"],
    }
    STATE["messages"].append(msg)
    ticket["status"] = "resolved"
    ticket["resolved_at"] = msg["timestamp"]
    _recompute_kpis()
    _save_state()
    return jsonify({"message": msg, "ticket": ticket})


@app.post("/api/tickets/<ticket_id>/agent-reply")
def agent_reply_ticket(ticket_id: str):
    ticket = _find(STATE["tickets"], ticket_id)
    if not ticket:
        return jsonify({"error": "not_found"}), 404
    shipment = _find(STATE["shipments"], ticket["shipment_id"]) if ticket.get("shipment_id") else None
    customer = _find(STATE["customers"], ticket["customer_id"])
    lookup_context = {
        "requested_ref": ticket.get("shipment_ref"),
        "matched_ref": ticket.get("shipment_ref"),
        "exact_ref_found": True if ticket.get("shipment_ref") else None,
        "customer_shipment_count": len(_customer_shipments(ticket["customer_id"])),
        "recent_refs": [shipment["ref"] for shipment in _customer_shipments(ticket["customer_id"])[:3]],
        "handoff_required": True,
        "verification_required": bool(ticket.get("verification_required")),
        "handoff_note": ticket.get("handoff_note") or _handoff_note(ticket["intent"]),
    }
    text = _compose_reply(
        ticket["intent"],
        shipment,
        customer,
        customer_text=ticket["text"],
        lookup_context=lookup_context,
    ) or "Noted. Our office will follow up shortly."
    msg_id = _next_id("MSG", STATE["messages"])
    msg = {
        "id": msg_id,
        "shipment_id": ticket["shipment_id"],
        "shipment_ref": ticket["shipment_ref"],
        "customer_id": ticket["customer_id"],
        "customer_name": ticket["customer_name"],
        "direction": "outgoing",
        "text": text,
        "timestamp": _now_iso(),
        "intent": ticket["intent"],
        "confidence": 0.75,
        "channel": "whatsapp",
        "source": "agent",
        "reply_to": ticket["message_id"],
    }
    STATE["messages"].append(msg)
    if ticket["status"] == "pending":
        ticket["status"] = "in_progress"
        ticket["in_progress_at"] = ticket.get("in_progress_at") or msg["timestamp"]
    STATE["agent_actions"].insert(0, {
        "id": _next_id("ACT", STATE["agent_actions"]),
        "kind": "handoff_ack",
        "intent": ticket["intent"],
        "shipment_id": ticket["shipment_id"],
        "shipment_ref": ticket["shipment_ref"],
        "customer_id": ticket["customer_id"],
        "confidence": 0.75,
        "timestamp": msg["timestamp"],
        "summary": f"Agent replied on escalated {ticket['intent']} ticket {ticket_id} while keeping it open for review.",
    })
    _recompute_kpis()
    _save_state()
    return jsonify({"message": msg, "ticket": ticket})


@app.get("/api/broadcasts")
def broadcasts():
    return jsonify({"items": STATE["broadcasts"], "total": len(STATE["broadcasts"])})


@app.get("/api/agent-actions")
def agent_actions():
    return jsonify({"items": STATE["agent_actions"][:100], "total": len(STATE["agent_actions"])})


@app.get("/api/agent-config")
def agent_config():
    return jsonify(STATE["agent_config"])


@app.get("/api/kpis")
def kpis():
    return jsonify(STATE.get("kpis", {}))


@app.get("/api/nudges")
def nudges():
    return jsonify({"items": STATE.get("nudges", []), "total": len(STATE.get("nudges", []))})


@app.post("/api/nudges/<nudge_id>/send")
def send_nudge(nudge_id: str):
    n = _find(STATE.get("nudges", []), nudge_id)
    if not n:
        return jsonify({"error": "not_found"}), 404
    n["status"] = "sent"
    customer = _find(STATE["customers"], n["customer_id"])
    shipment_id = None
    for s in STATE["shipments"]:
        if s["ref"] == n.get("shipment_ref"):
            shipment_id = s["id"]
            break
    msg_id = _next_id("MSG", STATE["messages"])
    msg = {
        "id": msg_id,
        "shipment_id": shipment_id,
        "shipment_ref": n.get("shipment_ref"),
        "customer_id": n["customer_id"],
        "customer_name": customer["name"] if customer else n["customer_name"],
        "direction": "outgoing",
        "text": n["draft"],
        "timestamp": _now_iso(),
        "intent": "nudge",
        "confidence": 1.0,
        "channel": n.get("channel", "whatsapp"),
        "source": "agent",
        "nudge_id": nudge_id,
    }
    STATE["messages"].append(msg)
    STATE["agent_actions"].insert(0, {
        "id": _next_id("ACT", STATE["agent_actions"]),
        "kind": "nudge_sent",
        "intent": n.get("rule_id"),
        "shipment_id": shipment_id,
        "shipment_ref": n.get("shipment_ref"),
        "customer_id": n["customer_id"],
        "confidence": 1.0,
        "timestamp": msg["timestamp"],
        "summary": f"Proactive nudge sent: {n['rule_label']} on {n.get('shipment_ref') or 'account'}.",
    })
    _recompute_kpis()
    _save_state()
    return jsonify({"nudge": n, "message": msg})


@app.post("/api/nudges/<nudge_id>/cancel")
def cancel_nudge(nudge_id: str):
    n = _find(STATE.get("nudges", []), nudge_id)
    if not n:
        return jsonify({"error": "not_found"}), 404
    n["status"] = "cancelled"
    _recompute_kpis()
    _save_state()
    return jsonify(n)


@app.get("/api/approvals")
def approvals():
    return jsonify({"items": STATE.get("approvals", []), "total": len(STATE.get("approvals", []))})


@app.post("/api/approvals/<approval_id>/decide")
def decide_approval(approval_id: str):
    payload = request.get_json(silent=True) or {}
    decision = payload.get("decision")  # approve | edit | reject
    edited_text = (payload.get("text") or "").strip()
    if decision not in ("approve", "edit", "reject"):
        return jsonify({"error": "invalid decision"}), 400
    a = _find(STATE.get("approvals", []), approval_id)
    if not a:
        return jsonify({"error": "not_found"}), 404
    now = _now_iso()
    a["reviewed_at"] = now
    if decision == "reject":
        a["status"] = "rejected"
        _recompute_kpis()
        _save_state()
        return jsonify({"approval": a, "message": None})
    text = edited_text if decision == "edit" and edited_text else a["draft_reply"]
    a["status"] = "edited" if decision == "edit" else "approved"
    a["final_text"] = text
    shipment_id = None
    for s in STATE["shipments"]:
        if s["ref"] == a.get("shipment_ref"):
            shipment_id = s["id"]
            break
    msg_id = _next_id("MSG", STATE["messages"])
    msg = {
        "id": msg_id,
        "shipment_id": shipment_id,
        "shipment_ref": a.get("shipment_ref"),
        "customer_id": a["customer_id"],
        "customer_name": a["customer_name"],
        "direction": "outgoing",
        "text": text,
        "timestamp": now,
        "intent": a["intent"],
        "confidence": a["confidence"],
        "channel": "whatsapp",
        "source": "agent_approved",
        "approval_id": approval_id,
        "reply_to": a["message_id"],
    }
    STATE["messages"].append(msg)
    STATE["agent_actions"].insert(0, {
        "id": _next_id("ACT", STATE["agent_actions"]),
        "kind": "approval_sent",
        "intent": a["intent"],
        "shipment_id": shipment_id,
        "shipment_ref": a.get("shipment_ref"),
        "customer_id": a["customer_id"],
        "confidence": a["confidence"],
        "timestamp": now,
        "summary": f"Approved draft sent to {a['customer_name']}" + (f" on {a['shipment_ref']}" if a.get('shipment_ref') else "") + ".",
    })
    _recompute_kpis()
    _save_state()
    return jsonify({"approval": a, "message": msg})


@app.get("/api/departments")
def departments():
    cfg = STATE.get("agent_config") or {}
    depts = [dict(d) for d in cfg.get("departments", [])]
    counts: dict[str, dict[str, int]] = {d["id"]: {"pending": 0, "in_progress": 0, "resolved": 0, "sla_breached": 0} for d in depts}
    now_iso = _now_iso()
    for t in STATE.get("tickets", []):
        did = t.get("department_id") or cfg.get("fallback_department") or DEFAULT_FALLBACK_DEPARTMENT
        if did not in counts:
            counts[did] = {"pending": 0, "in_progress": 0, "resolved": 0, "sla_breached": 0}
        status = t.get("status", "pending")
        if status in counts[did]:
            counts[did][status] += 1
        if status != "resolved" and t.get("sla_due_at") and t["sla_due_at"] < now_iso:
            counts[did]["sla_breached"] += 1
    for d in depts:
        d["counts"] = counts.get(d["id"], {"pending": 0, "in_progress": 0, "resolved": 0, "sla_breached": 0})
    return jsonify({"items": depts, "total": len(depts), "fallback": cfg.get("fallback_department") or DEFAULT_FALLBACK_DEPARTMENT})


@app.put("/api/agent-config")
def update_agent_config():
    payload = request.get_json(silent=True) or {}
    cfg = STATE.get("agent_config") or _make_agent_config()

    # editable fields only; reject anything else silently
    ALL_INTENTS = {
        "tracking", "eta", "customs", "documents", "pod_request", "delay_reason",
        "pickup_booking", "general", "damage_claim", "billing", "address_change", "reschedule",
    }

    if "confidence_threshold" in payload:
        try:
            val = float(payload["confidence_threshold"])
        except (TypeError, ValueError):
            return jsonify({"error": "confidence_threshold must be number"}), 400
        if not 0.0 <= val <= 1.0:
            return jsonify({"error": "confidence_threshold must be between 0 and 1"}), 400
        cfg["confidence_threshold"] = round(val, 2)

    if "auto_intents" in payload:
        vals = payload["auto_intents"] or []
        if not isinstance(vals, list) or any(v not in ALL_INTENTS for v in vals):
            return jsonify({"error": "auto_intents invalid"}), 400
        cfg["auto_intents"] = list(dict.fromkeys(vals))

    if "hard_escalate_intents" in payload:
        vals = payload["hard_escalate_intents"] or []
        if not isinstance(vals, list) or any(v not in ALL_INTENTS for v in vals):
            return jsonify({"error": "hard_escalate_intents invalid"}), 400
        cfg["hard_escalate_intents"] = list(dict.fromkeys(vals))

    # prevent an intent from being in both lists
    overlap = set(cfg.get("auto_intents", [])) & set(cfg.get("hard_escalate_intents", []))
    if overlap:
        return jsonify({"error": f"intent cannot be both auto and hard-escalate: {sorted(overlap)}"}), 400

    if "tone_by_tier" in payload:
        tones = payload["tone_by_tier"] or {}
        if not isinstance(tones, dict):
            return jsonify({"error": "tone_by_tier must be object"}), 400
        cleaned = {str(k): str(v)[:400] for k, v in tones.items() if str(v).strip()}
        cfg["tone_by_tier"] = cleaned

    if "nudge_rules" in payload:
        rules = payload["nudge_rules"] or []
        if not isinstance(rules, list):
            return jsonify({"error": "nudge_rules must be list"}), 400
        cleaned_rules = []
        seen_ids = set()
        for r in rules:
            if not isinstance(r, dict):
                continue
            rid = str(r.get("id") or "").strip()
            trigger = str(r.get("trigger") or "").strip()
            action = str(r.get("action") or "").strip()
            if not rid or not trigger or not action:
                return jsonify({"error": "each nudge_rule needs id, trigger, action"}), 400
            if rid in seen_ids:
                return jsonify({"error": f"duplicate rule id: {rid}"}), 400
            seen_ids.add(rid)
            cleaned_rules.append({"id": rid, "trigger": trigger[:300], "action": action[:300]})
        cfg["nudge_rules"] = cleaned_rules

    if "intent_routing" in payload:
        routing = payload["intent_routing"] or {}
        if not isinstance(routing, dict):
            return jsonify({"error": "intent_routing must be object"}), 400
        dept_ids = {d["id"] for d in cfg.get("departments", [])}
        cleaned_routing = {}
        for intent, did in routing.items():
            if intent not in ALL_INTENTS:
                return jsonify({"error": f"unknown intent: {intent}"}), 400
            did_str = str(did)
            if did_str not in dept_ids:
                return jsonify({"error": f"unknown department: {did_str}"}), 400
            cleaned_routing[intent] = did_str
        cfg["intent_routing"] = cleaned_routing

    if "fallback_department" in payload:
        did = str(payload["fallback_department"])
        dept_ids = {d["id"] for d in cfg.get("departments", [])}
        if did not in dept_ids:
            return jsonify({"error": f"unknown fallback_department: {did}"}), 400
        cfg["fallback_department"] = did

    if "departments" in payload:
        depts = payload["departments"] or []
        if not isinstance(depts, list) or not depts:
            return jsonify({"error": "departments must be non-empty list"}), 400
        cleaned_depts = []
        seen = set()
        for d in depts:
            if not isinstance(d, dict):
                continue
            did = str(d.get("id") or "").strip().lower().replace(" ", "_")
            name = str(d.get("name") or "").strip()
            if not did or not name:
                return jsonify({"error": "each department needs id and name"}), 400
            if did in seen:
                return jsonify({"error": f"duplicate department id: {did}"}), 400
            seen.add(did)
            try:
                sla = int(d.get("sla_hours") or 4)
            except (TypeError, ValueError):
                sla = 4
            members_in = d.get("members") or []
            members_out = []
            for m in members_in:
                if not isinstance(m, dict):
                    continue
                mid = str(m.get("id") or "").strip()
                mname = str(m.get("name") or "").strip()
                if not mid or not mname:
                    continue
                members_out.append({"id": mid, "name": mname, "role": str(m.get("role") or "").strip()})
            cleaned_depts.append({
                "id": did,
                "name": name,
                "description": str(d.get("description") or "").strip(),
                "sla_hours": max(1, min(sla, 168)),
                "members": members_out,
            })
        cfg["departments"] = cleaned_depts
        # prune routing that now references removed departments
        valid = {x["id"] for x in cleaned_depts}
        cfg["intent_routing"] = {k: v for k, v in (cfg.get("intent_routing") or {}).items() if v in valid}
        if cfg.get("fallback_department") not in valid:
            cfg["fallback_department"] = cleaned_depts[0]["id"]

    cfg["version"] = int(cfg.get("version") or 1) + 1
    cfg["updated_at"] = _now_iso()
    STATE["agent_config"] = cfg
    _save_state()
    return jsonify(cfg)


@app.post("/api/tickets/<ticket_id>/assign")
def assign_ticket(ticket_id: str):
    payload = request.get_json(silent=True) or {}
    ticket = _find(STATE["tickets"], ticket_id)
    if not ticket:
        return jsonify({"error": "not_found"}), 404
    cfg = STATE.get("agent_config") or {}
    depts = cfg.get("departments") or []
    dept_ids = {d["id"]: d for d in depts}

    if "department_id" in payload:
        did = str(payload["department_id"])
        if did not in dept_ids:
            return jsonify({"error": "unknown department"}), 400
        dept = dept_ids[did]
        ticket["department_id"] = did
        ticket["department_name"] = dept.get("name") or did
        ticket["sla_hours"] = dept.get("sla_hours", ticket.get("sla_hours", 4))
        # recompute SLA from ticket timestamp so reroute doesn't cheat the clock
        try:
            anchor = datetime.fromisoformat(ticket["timestamp"])
        except Exception:
            anchor = datetime.utcnow()
        ticket["sla_due_at"] = (anchor + timedelta(hours=ticket["sla_hours"])).replace(microsecond=0).isoformat()
        # drop assignee if they're not in the new department
        current = ticket.get("assignee")
        if current and current.get("id") not in {m["id"] for m in dept.get("members", [])}:
            ticket["assignee"] = None

    if "assignee_id" in payload:
        aid = payload["assignee_id"]
        if aid in (None, ""):
            ticket["assignee"] = None
        else:
            did = ticket.get("department_id") or cfg.get("fallback_department") or DEFAULT_FALLBACK_DEPARTMENT
            dept = dept_ids.get(did)
            member = None
            for m in (dept or {}).get("members", []):
                if m["id"] == aid:
                    member = m
                    break
            if not member:
                return jsonify({"error": "assignee not in department"}), 400
            ticket["assignee"] = {"id": member["id"], "name": member["name"]}
            if ticket["status"] == "pending":
                ticket["status"] = "in_progress"
                ticket["in_progress_at"] = _now_iso()

    _recompute_kpis()
    _save_state()
    return jsonify(ticket)


@app.get("/api/agent-runs")
def agent_runs():
    limit = int(request.args.get("limit", "200"))
    rows = STATE.get("agent_runs", [])
    return jsonify({"items": rows[-limit:][::-1], "total": len(rows)})


@app.get("/api/agent-runs/<run_id>")
def agent_run_detail(run_id: str):
    r = _find(STATE.get("agent_runs", []), run_id)
    if not r:
        return jsonify({"error": "not_found"}), 404
    return jsonify(r)


@app.get("/")
def frontend_index():
    if (FRONTEND_DIST_DIR / "index.html").exists():
        return app.send_static_file("index.html")
    return jsonify({"status": "frontend_not_built"}), 503


@app.get("/<path:path>")
def frontend_assets(path: str):
    if path.startswith("api/"):
        return jsonify({"error": "not_found"}), 404
    asset_path = FRONTEND_DIST_DIR / path
    if asset_path.exists() and asset_path.is_file():
        return send_from_directory(FRONTEND_DIST_DIR, path)
    if (FRONTEND_DIST_DIR / "index.html").exists():
        return app.send_static_file("index.html")
    return jsonify({"error": "not_found"}), 404


if __name__ == "__main__":
    _ensure_state()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5001")), debug=True)
