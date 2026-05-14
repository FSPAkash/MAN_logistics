# OpenAI Integration Plan - MAN Logistics POC

## Goal

Replace the keyword-regex agent in `backend/app.py` with an OpenAI-powered classifier + reply generator. Keep deterministic mock data, deterministic escalation routing, and the existing REST contract unchanged so the frontend needs no changes (beyond an optional loading/streaming UX).

## Current state (what gets replaced)

File: `backend/app.py`

- `_classify(text) -> (intent, confidence)` at lines 78-104. Keyword `if/elif`. Returns one of 12 intents.
- `_compose_reply(intent, shipment, customer) -> str` at lines 121-149. Hardcoded f-strings per intent.
- Callers:
  - `POST /api/messages` (lines 220-323) uses both.
  - `POST /api/tickets/<id>/agent-reply` (lines 384-424) uses `_compose_reply` only.

Everything else (data seed, ticket flow, KPI recompute, persistence to `runtime_dataset.json`) stays as-is.

## Architecture

```
Customer message
  -> Flask POST /api/messages
  -> agent.classify(text, context)     # OpenAI call #1 (structured output)
  -> agent.compose(intent, shipment, customer, text)  # OpenAI call #2 (chat completion)
  -> same escalation logic as today (intent in auto_intents AND confidence >= threshold)
  -> persist message + agent_action + optional ticket
```

Two OpenAI calls per incoming message is acceptable for a POC. A single-call variant using tool-calling is in the "Optional: single-call agent" section at the bottom.

## New files

### `backend/agent.py` (new)

All OpenAI wiring. Do not put keys or SDK calls anywhere else.

```python
"""OpenAI-backed classifier and reply generator for the logistics agent."""
from __future__ import annotations

import json
import os
from typing import Optional

from openai import OpenAI

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set")
        _client = OpenAI(api_key=key)
    return _client


MODEL_CLASSIFY = os.environ.get("MAN_OPENAI_CLASSIFY_MODEL", "gpt-4o-mini")
MODEL_REPLY = os.environ.get("MAN_OPENAI_REPLY_MODEL", "gpt-4o-mini")

INTENTS = [
    "tracking", "eta", "customs", "documents", "pod_request",
    "reschedule", "billing", "damage_claim", "address_change",
    "pickup_booking", "delay_reason", "general",
]

CLASSIFY_SYSTEM = (
    "You classify customer messages for a freight forwarder's WhatsApp desk. "
    "Return JSON only. Choose exactly one intent from the provided list. "
    "confidence is your calibrated probability that the customer truly wants that intent. "
    "Use lower confidence (<0.6) when the message is ambiguous, emotional, or mixes multiple asks."
)

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": INTENTS},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "shipment_ref_mentioned": {"type": ["string", "null"]},
        "reasoning": {"type": "string"},
    },
    "required": ["intent", "confidence", "reasoning"],
    "additionalProperties": False,
}


def classify(text: str) -> dict:
    """Returns {intent, confidence, shipment_ref_mentioned, reasoning}."""
    client = _get_client()
    resp = client.chat.completions.create(
        model=MODEL_CLASSIFY,
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "intent_classification", "schema": CLASSIFY_SCHEMA, "strict": True},
        },
        messages=[
            {"role": "system", "content": CLASSIFY_SYSTEM},
            {"role": "user", "content": f"Intents: {', '.join(INTENTS)}\n\nCustomer message:\n{text}"},
        ],
    )
    return json.loads(resp.choices[0].message.content)


REPLY_SYSTEM = (
    "You are the MAN Logistics WhatsApp agent. "
    "Reply in 1-3 short sentences. Plain text, no markdown, no emojis. "
    "Only state facts from the supplied shipment JSON. "
    "If a field is missing, say so and offer to follow up rather than inventing data. "
    "Never quote raw JSON or field names back to the customer. "
    "Never promise delivery dates earlier than the ETA in the data."
)


def compose(intent: str, customer_text: str, shipment: dict | None, customer: dict | None) -> str:
    client = _get_client()
    context = {
        "intent": intent,
        "customer": {
            "name": customer.get("name") if customer else None,
            "email": customer.get("email") if customer else None,
            "tier": customer.get("tier") if customer else None,
        } if customer else None,
        "shipment": _trim_shipment(shipment) if shipment else None,
    }
    resp = client.chat.completions.create(
        model=MODEL_REPLY,
        temperature=0.2,
        messages=[
            {"role": "system", "content": REPLY_SYSTEM},
            {"role": "user", "content": (
                f"Customer said: {customer_text}\n\n"
                f"Context JSON:\n{json.dumps(context, default=str)}\n\n"
                "Write the agent reply now."
            )},
        ],
    )
    return resp.choices[0].message.content.strip()


def _trim_shipment(s: dict) -> dict:
    """Remove heavy fields (full event list) to keep prompt small."""
    keep = {
        "ref", "mode", "carrier", "commodity", "origin", "destination",
        "status", "eta", "last_event_label", "last_location", "last_event_at",
        "next_event_label", "next_event_at", "delay_minutes", "delay_reason",
        "incoterm", "documents",
    }
    return {k: v for k, v in s.items() if k in keep}
```

### `backend/requirements.txt` (update)

Add:
```
openai>=1.40.0
python-dotenv>=1.0.0
```

### `backend/.env.example` (new)

```
OPENAI_API_KEY=<set-in-render-or-local-env>
MAN_OPENAI_CLASSIFY_MODEL=gpt-4o-mini
MAN_OPENAI_REPLY_MODEL=gpt-4o-mini
MAN_AGENT_BACKEND=openai
MAN_AGENT_CONFIDENCE_THRESHOLD=0.7
```

Add `.env` to `.gitignore` if not already.

## Edits to `backend/app.py`

### 1. Load env at import

Top of file, after `from pathlib import Path`:

```python
from dotenv import load_dotenv
load_dotenv(Path(__file__).with_name(".env"))
```

### 2. Add backend switch

Replace `_classify` and `_compose_reply` with thin dispatchers so the old regex agent stays as a fallback (useful when key missing or during offline demos).

```python
import os
from agent import classify as oai_classify, compose as oai_compose

AGENT_BACKEND = os.environ.get("MAN_AGENT_BACKEND", "regex")  # "openai" | "regex"


def _classify(text: str) -> tuple[str, float]:
    if AGENT_BACKEND == "openai":
        try:
            res = oai_classify(text)
            return res["intent"], float(res["confidence"])
        except Exception as exc:
            app.logger.warning("openai classify failed, falling back: %s", exc)
            return _classify_regex(text)
    return _classify_regex(text)


def _classify_regex(text: str) -> tuple[str, float]:
    # existing body of _classify verbatim
    ...


def _compose_reply(intent: str, shipment: dict | None, customer: dict | None, customer_text: str = "") -> str:
    if AGENT_BACKEND == "openai":
        try:
            return oai_compose(intent, customer_text, shipment, customer)
        except Exception as exc:
            app.logger.warning("openai compose failed, falling back: %s", exc)
    return _compose_reply_template(intent, shipment, customer)


def _compose_reply_template(intent, shipment, customer):
    # existing body of _compose_reply verbatim
    ...
```

Note the added `customer_text` parameter on `_compose_reply`. Callers must be updated:

- `POST /api/messages` (line ~258): `_compose_reply(intent, shipment, customer, customer_text=text)`
- `POST /api/tickets/<id>/agent-reply` (line ~391): `_compose_reply(ticket["intent"], shipment, customer, customer_text=ticket["text"])`

### 3. Richer shipment match

OpenAI returns `shipment_ref_mentioned`. Prefer it over regex in `_find_shipment_for`:

```python
def _find_shipment_for(text: str, customer_id: str | None, ref_hint: str | None = None) -> dict | None:
    ref = (ref_hint or "").upper().strip() or None
    if not ref:
        m = TRACK_RE.search(text)
        ref = m.group(0).upper() if m else None
    if ref:
        for s in STATE["shipments"]:
            if s["ref"].upper() == ref:
                return s
    # customer fallback unchanged
    ...
```

In `POST /api/messages`, call classify first, then pass the hint:

```python
if AGENT_BACKEND == "openai":
    cls = oai_classify(text)
    intent, base_conf = cls["intent"], float(cls["confidence"])
    ref_hint = cls.get("shipment_ref_mentioned")
else:
    intent, base_conf = _classify_regex(text)
    ref_hint = None
shipment = _find_shipment_for(text, customer_id, ref_hint=ref_hint)
```

### 4. Agent config endpoint

`GET /api/agent-config` already returns `confidence_threshold`, `auto_intents`, `escalate_categories`. Add a `backend` field so the frontend can show a "AI: gpt-4o-mini" pill.

In `data_seed.generate_dataset` `agent_config` dict:

```python
"agent_config": {
    ...
    "backend": os.environ.get("MAN_AGENT_BACKEND", "regex"),
    "classify_model": os.environ.get("MAN_OPENAI_CLASSIFY_MODEL", "gpt-4o-mini"),
    "reply_model": os.environ.get("MAN_OPENAI_REPLY_MODEL", "gpt-4o-mini"),
}
```

Also read `MAN_AGENT_CONFIDENCE_THRESHOLD` to override the hardcoded 0.7.

## Frontend changes (optional but recommended)

File: `frontend/src/sections/CustomerChat.jsx`

Current `handleSend` awaits `api.sendMessage` then reloads the thread. With OpenAI this takes ~1-3s. Two polish items:

1. Optimistic append of the customer's message before the await, so the bubble appears instantly.
2. A "typing" indicator while `sending === true` (simple 3-dot bubble in agent-blue).

File: `frontend/src/components/layout/AppShell.jsx`

The agent-pill currently says "Agent live". When `agentConfig.backend === "openai"`, change to `AI - {classify_model}`.

No other frontend edits required. The REST contract is unchanged.

## Escalation policy (unchanged but restated)

In `POST /api/messages`:

```
needs_human = intent not in auto_intents OR confidence < threshold
```

`auto_intents` = `["tracking", "eta", "customs", "documents", "pod_request", "delay_reason", "pickup_booking", "general"]`

Hard-escalate list (always ticket, never auto-reply even if OpenAI reports 0.99 confidence):

```
HARD_ESCALATE = {"damage_claim", "billing", "address_change", "reschedule"}
if intent in HARD_ESCALATE: needs_human = True
```

Add this check right after classify in `POST /api/messages`. This protects against the LLM over-confidently answering a damage claim.

## Error handling

- Missing `OPENAI_API_KEY`: `agent.py` raises at first call. `_classify` and `_compose_reply` catch and fall back to regex. Log once at warning level.
- OpenAI 429 / 5xx: same path. Fall back, log. Do not retry inside the request handler (blocks user).
- Malformed JSON from classify: `json.loads` raises -> fallback. JSON schema strict mode in the payload makes this rare with current models.
- Shipment ref hallucinated by LLM: `_find_shipment_for` verifies the ref exists in `STATE["shipments"]`; missing -> falls back to customer's most recent shipment.

## Security and secrets

- Key lives in `backend/.env` only. `.env` is gitignored.
- Never log the full API key. `app.logger.warning` on failure must stringify the exception only (OpenAI client masks the key in its error messages).
- Never echo the customer message or LLM reply into server logs at INFO level in production. POC is fine at DEBUG during local dev.
- CORS already restricted to local dev origin via `flask_cors`. Keep it that way.

## Cost and latency

- Classify + reply with `gpt-4o-mini`: approx 400-800 input tokens, 60-120 output tokens per turn. Roughly sub-cent per message.
- Latency: 0.8s-2.5s end-to-end for both calls sequentially. Acceptable with the optimistic UI.
- If latency matters: run classify and the fallback shipment lookup in parallel with a speculative compose; discard compose if escalation wins. Skip for v1.

## Testing checklist

1. `OPENAI_API_KEY` unset, `MAN_AGENT_BACKEND=regex`: existing behavior, no OpenAI calls.
2. `MAN_AGENT_BACKEND=openai`, valid key:
   - "Where is MAN123456?" -> intent=tracking, auto-reply grounded in that shipment.
   - "Two cartons arrived damaged" -> intent=damage_claim, ticket created, no auto-reply even if confidence high.
   - "Can you move pickup to next Monday?" -> intent=reschedule, ticket.
   - "Invoice looks wrong" -> intent=billing, ticket.
   - Message with no ref, customer has shipments -> uses most recent shipment.
   - Message with no ref, customer has no shipments -> agent says it cannot find a shipment.
3. `MAN_AGENT_BACKEND=openai` with invalid key: first call fails, logs warning, regex fallback serves reply. No 500 to client.
4. Reseed (`POST /api/reseed`) still works; does not touch OpenAI.
5. Ticket `/agent-reply` endpoint produces an LLM-composed reply.

## Files to create or modify - summary

| File | Action |
|------|--------|
| `backend/agent.py` | create |
| `backend/app.py` | edit: load_dotenv, dispatcher for `_classify` / `_compose_reply`, pass `customer_text`, hard-escalate list, use `ref_hint` |
| `backend/requirements.txt` | add `openai`, `python-dotenv` |
| `backend/.env.example` | create |
| `backend/.env` | create locally, gitignored |
| `backend/.gitignore` (or repo root) | ensure `.env` excluded |
| `backend/data_seed.py` | expose `backend` + model names in `agent_config` |
| `frontend/src/sections/CustomerChat.jsx` | optional: optimistic bubble + typing indicator |
| `frontend/src/components/layout/AppShell.jsx` | optional: show model name in agent pill |

## Optional: single-call agent (deferred)

Replace classify+compose with one `chat.completions.create` using OpenAI tool-calling. Tools: `lookup_shipment(ref)`, `lookup_customer_latest_shipment(customer_id)`, `escalate(category, reason)`, `reply(text, confidence)`. Model decides which tools to call. Cleaner, but harder to keep deterministic escalation. Punt to v2.
