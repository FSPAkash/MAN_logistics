"""OpenAI-backed classifier and reply generator for the logistics agent."""

from __future__ import annotations

import json
import os
from typing import Optional

from openai import OpenAI

_client: Optional[OpenAI] = None

INTENTS = [
    "tracking",
    "eta",
    "customs",
    "documents",
    "pod_request",
    "reschedule",
    "billing",
    "damage_claim",
    "address_change",
    "pickup_booking",
    "delay_reason",
    "general",
]

CLASSIFY_SYSTEM = (
    "You classify customer messages for a freight forwarder's WhatsApp desk. "
    "Return JSON only. Choose exactly one intent from the provided list. "
    "confidence is your calibrated probability that the customer truly wants that intent. "
    "Use lower confidence (<0.6) when the message is ambiguous, emotional, or mixes multiple asks. "
    "Use the supplied account context only as support; do not invent a shipment reference."
)

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": INTENTS},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "shipment_ref_mentioned": {"type": ["string", "null"]},
        "reasoning": {"type": "string"},
    },
    "required": ["intent", "confidence", "shipment_ref_mentioned", "reasoning"],
    "additionalProperties": False,
}

REPLY_SYSTEM = (
    "You are the MAN Logistics WhatsApp agent. "
    "Reply in 1-3 short sentences. Plain text, no markdown, no emojis. "
    "Only state facts from the supplied shipment JSON. "
    "If a field is missing, say so and offer to follow up rather than inventing data. "
    "Never quote raw JSON or field names back to the customer. "
    "Never promise delivery dates earlier than the ETA in the data. "
    "If the lookup context says a requested shipment reference was not found, clearly say that and use the recent shipment list if provided. "
    "If handoff_required is true, acknowledge the request, say the MAN Logistics team will review it, and if verification_required is true say the team must verify before any change is applied."
)


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set")
        _client = OpenAI(api_key=key)
    return _client


def _model_name(env_var: str, default: str) -> str:
    return os.environ.get(env_var, default)


def classify(text: str, context: dict | None = None) -> dict:
    """Returns a structured classification for the customer message."""
    client = _get_client()
    payload = {
        "customer_message": text,
        "context": context or {},
    }
    resp = client.chat.completions.create(
        model=_model_name("MAN_OPENAI_CLASSIFY_MODEL", "gpt-4o-mini"),
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "intent_classification",
                "schema": CLASSIFY_SCHEMA,
                "strict": True,
            },
        },
        messages=[
            {"role": "system", "content": CLASSIFY_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Intents: {', '.join(INTENTS)}\n\n"
                    f"Classification payload:\n{json.dumps(payload, default=str)}"
                ),
            },
        ],
    )
    content = resp.choices[0].message.content or "{}"
    return json.loads(content)


def compose(
    intent: str,
    customer_text: str,
    shipment: dict | None,
    customer: dict | None,
    context: dict | None = None,
) -> str:
    """Generate a grounded customer-facing reply."""
    client = _get_client()
    prompt_context = {
        "intent": intent,
        "customer": {
            "name": customer.get("name") if customer else None,
            "email": customer.get("email") if customer else None,
            "tier": customer.get("tier") if customer else None,
        }
        if customer
        else None,
        "shipment": _trim_shipment(shipment) if shipment else None,
        "lookup_context": context or {},
    }
    resp = client.chat.completions.create(
        model=_model_name("MAN_OPENAI_REPLY_MODEL", "gpt-4o-mini"),
        temperature=0.2,
        messages=[
            {"role": "system", "content": REPLY_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Customer said: {customer_text}\n\n"
                    f"Context JSON:\n{json.dumps(prompt_context, default=str)}\n\n"
                    "Write the agent reply now."
                ),
            },
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def _trim_shipment(shipment: dict) -> dict:
    """Remove the heavy event list to keep prompts small and grounded."""
    keep = {
        "ref",
        "mode",
        "carrier",
        "commodity",
        "origin",
        "destination",
        "status",
        "eta",
        "last_event_label",
        "last_location",
        "last_event_at",
        "next_event_label",
        "next_event_at",
        "delay_minutes",
        "delay_reason",
        "incoterm",
        "documents",
    }
    return {key: value for key, value in shipment.items() if key in keep}
