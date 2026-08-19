"""Event logging service.

Every webhook and background action writes a row to the append-only
public.events table. The table shape comes from the canonical schema
migration (20250101000000_schema.sql):

    events (
      id          uuid primary key default gen_random_uuid(),
      client_id   uuid references public.clients (id) on delete cascade,
      event_type  text not null,
      payload     jsonb not null default '{}'::jsonb,
      created_at  timestamptz not null default now()
    )

client_id is nullable on purpose. System-level events, such as a generic
webhook post that maps to no client, land with client_id set to None.

All writes run through the FastAPI backend on the Supabase service role,
which bypasses row-level security, so this module never needs a user
session. Inbound activity written here shows only in the events log and
the admin activity view, never on the client dashboard.

You can inject your own Supabase client in tests through the `client`
argument on every public function, so no test needs a live database.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from supabase import Client, create_client

logger = logging.getLogger(__name__)

# Event type constants. Routers and services import these instead of
# writing raw strings, so the events log stays queryable and consistent.
EVENT_INBOUND_SMS = "inbound_sms_received"
EVENT_INBOUND_CALL = "inbound_call_received"
EVENT_GENERIC_WEBHOOK = "generic_webhook_received"
EVENT_STRIPE_WEBHOOK = "stripe_webhook_received"
EVENT_STRIPE_DUPLICATE = "stripe_webhook_duplicate_skipped"

_supabase: Optional[Client] = None


def _get_supabase() -> Client:
    """Return the module-level Supabase client, creating it on first use.

    The service role key stays in the environment file, never in code.
    """
    global _supabase
    if _supabase is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        _supabase = create_client(url, key)
    return _supabase


def log_event(
    event_type: str,
    payload: Optional[dict[str, Any]] = None,
    client_id: Optional[str] = None,
    client: Optional[Client] = None,
) -> dict[str, Any]:
    """Insert one row into public.events and return the inserted row.

    Args:
        event_type: One of the EVENT_* constants above, or any short
            snake_case label for a new event kind.
        payload: JSON-safe dict stored in the jsonb payload column.
            Defaults to an empty object, matching the column default.
        client_id: Owning client's uuid as a string, or None for a
            system-level event.
        client: Optional Supabase client override for tests.

    Raises:
        Exception: Propagates any database error to the caller after
            logging it, so webhook routers can decide how to respond.
    """
    db = client or _get_supabase()
    row = {
        "client_id": client_id,
        "event_type": event_type,
        "payload": payload or {},
    }
    try:
        result = db.table("events").insert(row).execute()
    except Exception:
        logger.exception(
            "event insert failed: event_type=%s client_id=%s",
            event_type,
            client_id,
        )
        raise
    inserted: dict[str, Any] = result.data[0] if result.data else row
    logger.info(
        "event logged: event_type=%s client_id=%s event_id=%s",
        event_type,
        client_id,
        inserted.get("id"),
    )
    return inserted


def log_inbound_sms(
    client_id: str,
    from_number: str,
    to_number: str,
    body: Optional[str],
    twilio_message_sid: Optional[str],
    message_id: Optional[str] = None,
    client: Optional[Client] = None,
) -> dict[str, Any]:
    """Log the event that pairs with an inbound messages row.

    The messages row itself is written by the SMS webhook router through
    the inbound routing service. This call records the matching activity
    entry so the admin view and events log show the delivery.
    """
    payload: dict[str, Any] = {
        "direction": "inbound",
        "from_number": from_number,
        "to_number": to_number,
        "body": body,
        "twilio_message_sid": twilio_message_sid,
    }
    if message_id is not None:
        payload["message_id"] = message_id
    return log_event(
        event_type=EVENT_INBOUND_SMS,
        payload=payload,
        client_id=client_id,
        client=client,
    )


def log_inbound_call(
    from_number: str,
    to_number: str,
    twilio_call_sid: Optional[str],
    client_id: Optional[str] = None,
    client: Optional[Client] = None,
) -> dict[str, Any]:
    """Log an inbound voice call.

    The voice webhook answers with a short default greeting and hangs up,
    so the event row is the only durable record of the call. client_id is
    optional because a call can arrive on a number that maps to no active
    client, and that still deserves a system-level entry.
    """
    payload = {
        "direction": "inbound",
        "channel": "voice",
        "from_number": from_number,
        "to_number": to_number,
        "twilio_call_sid": twilio_call_sid,
    }
    return log_event(
        event_type=EVENT_INBOUND_CALL,
        payload=payload,
        client_id=client_id,
        client=client,
    )


def log_generic_webhook(
    source: str,
    payload: dict[str, Any],
    client_id: Optional[str] = None,
    client: Optional[Client] = None,
) -> dict[str, Any]:
    """Log any post that the generic receiver accepts.

    Args:
        source: A short label for where the post came from, such as the
            request path or a caller-supplied identifier.
        payload: The posted body, already parsed to a JSON-safe dict by
            the generic webhook router.
        client_id: Set when the router can attribute the post to a
            client, otherwise None.
        client: Optional Supabase client override for tests.
    """
    return log_event(
        event_type=EVENT_GENERIC_WEBHOOK,
        payload={"source": source, "body": payload},
        client_id=client_id,
        client=client,
    )


def log_stripe_event(
    stripe_event_id: str,
    stripe_event_type: str,
    duplicate: bool = False,
    client_id: Optional[str] = None,
    client: Optional[Client] = None,
) -> dict[str, Any]:
    """Log a verified Stripe webhook delivery.

    The idempotency check itself lives in stripe_idempotency.py. When that
    check flags a replay, pass duplicate=True and this call records the
    skip instead of the normal receipt, so replays stay visible in the
    events log without applying twice.
    """
    payload = {
        "stripe_event_id": stripe_event_id,
        "stripe_event_type": stripe_event_type,
    }
    event_type = EVENT_STRIPE_DUPLICATE if duplicate else EVENT_STRIPE_WEBHOOK
    return log_event(
        event_type=event_type,
        payload=payload,
        client_id=client_id,
        client=client,
    )