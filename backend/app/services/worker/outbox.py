"""Transactional outbox, idempotent consumers, and resumable batches.

Implements `references/patterns/event-driven-outbox-idempotency.md` per
`specs/SPEC_EVENT_DRIVEN_OUTBOX.md`. Batched site regeneration and every
external mutation need to be safe, resumable, and duplicate-proof.

Three primitives, each solving one failure mode:

    relay()             the dual-write problem. The event is written to the
                        outbox in the same transaction as the business row;
                        this relay publishes it afterwards. Nothing is lost
                        if the publish fails, and nothing publishes twice.
    handle_idempotent() at-least-once delivery. The same message arriving
                        twice applies once, because the second call returns
                        the cached result without re-running the handler.
    run_batch()         the crashed batch job. A checkpoint after each item
                        means a restart resumes where it stopped instead of
                        redoing the whole run.

Storage sits behind small protocols so tests run against the in-memory
implementations below and production swaps in Supabase-backed ones. Nothing
here touches a broker, a database, or the network.

Ordering note: `relay` publishes *before* marking the event published, which
makes delivery at-least-once rather than at-most-once. That is deliberate.
If the process dies between the two, the event republishes on the next run
and the consumer's idempotency key absorbs it - a duplicate a consumer can
absorb is recoverable, a lost event is not. Exactly-once *delivery* is a
myth; exactly-once *processing* is what `handle_idempotent` buys.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Callable, Optional, Protocol, Sequence

logger = logging.getLogger(__name__)


class OutboxStore(Protocol):
    """Durable event log written in the same transaction as the business row."""

    def add(self, event: dict) -> str:
        """Append an event and return its id."""

    def unpublished(self) -> list:
        """Every event not yet marked published, in insertion order."""

    def mark_published(self, event_id: str) -> None:
        """Mark one event published. Must raise on an unknown id."""


class DedupStore(Protocol):
    """Record of idempotency keys already handled, with their results."""

    def seen(self, idempotency_key: str) -> bool:
        """Whether this key has already been handled."""

    def cached(self, idempotency_key: str) -> Any:
        """The result recorded for a seen key.

        Not in the spec's protocol sketch, which lists only `seen` and
        `record`. It is required to satisfy the spec's own behaviour - "if
        key seen, return the cached result" is impossible to implement with
        a boolean alone. Flagged in `reports/OUTBOX_BUILD_REPORT.md`.
        """

    def record(self, idempotency_key: str, result: Any) -> None:
        """Record a key and the result of handling it."""


class Checkpoint(Protocol):
    """Cursor marking how far a batch got, so a restart can resume."""

    def load(self) -> Optional[int]:
        """Index of the last completed item, or None if nothing ran yet."""

    def save(self, last_processed_index: int) -> None:
        """Persist the index of the item that just completed."""


class InMemoryOutboxStore:
    """Reference `OutboxStore` for tests and local runs.

    Events are copied in and out, so a caller mutating its own dict after
    `add` cannot retroactively change what will be published.
    """

    def __init__(self) -> None:
        self._events: list = []
        self._published: set = set()
        self._dead: dict = {}  # event_id -> reason

    def add(self, event: dict) -> str:
        if not isinstance(event, dict):
            raise TypeError(f"an outbox event must be a dict, got {type(event).__name__}")
        stored = dict(event)
        event_id = str(stored.get("id") or uuid.uuid4())
        stored["id"] = event_id
        self._events.append(stored)
        return event_id

    def unpublished(self) -> list:
        return [
            dict(e)
            for e in self._events
            if e["id"] not in self._published and e["id"] not in self._dead
        ]

    def mark_published(self, event_id: str) -> None:
        if not any(e["id"] == event_id for e in self._events):
            raise KeyError(
                f"cannot mark unknown event id {event_id!r} published; it is not "
                f"in this outbox, so marking it would hide a lost event"
            )
        self._published.add(event_id)

    def mark_dead(self, event_id: str, reason: str) -> None:
        """Park a poison event so it no longer blocks the relay queue."""
        if not any(e["id"] == event_id for e in self._events):
            raise KeyError(
                f"cannot dead-letter unknown event id {event_id!r}"
            )
        if not reason or not str(reason).strip():
            raise ValueError("dead-letter reason is required")
        self._dead[event_id] = str(reason).strip()

    def dead_letters(self) -> list:
        """Dead-lettered events with named reasons (insertion order)."""
        out = []
        for e in self._events:
            eid = e["id"]
            if eid in self._dead:
                out.append({"event_id": eid, "reason": self._dead[eid], "event": dict(e)})
        return out

    def published_ids(self) -> list:
        """Ids marked published, in insertion order. Read-only, for assertions."""
        return [e["id"] for e in self._events if e["id"] in self._published]

class InMemoryDedupStore:
    """Reference `DedupStore` for tests and local runs."""

    def __init__(self) -> None:
        self._results: dict = {}

    def seen(self, idempotency_key: str) -> bool:
        return idempotency_key in self._results

    def cached(self, idempotency_key: str) -> Any:
        return self._results.get(idempotency_key)

    def record(self, idempotency_key: str, result: Any) -> None:
        self._results[idempotency_key] = result


class InMemoryCheckpoint:
    """Reference `Checkpoint` for tests and local runs."""

    def __init__(self, last_processed_index: Optional[int] = None) -> None:
        self._index = last_processed_index
        self.saves: list = []

    def load(self) -> Optional[int]:
        return self._index

    def save(self, last_processed_index: int) -> None:
        self._index = last_processed_index
        self.saves.append(last_processed_index)


def relay(
    store: OutboxStore,
    publish: Callable[[dict], Any],
    *,
    continue_on_error: bool = False,
) -> int:
    """Publish every unpublished event exactly once. Returns the count published.

    Safe to run repeatedly: a second run over the same store publishes zero,
    because each event is marked as it goes.

    If `publish` raises and `continue_on_error` is False (default), the
    exception propagates and that event stays unpublished (legacy behaviour —
    a poison event blocks those behind it).

    If `continue_on_error` is True and the store supports `mark_dead`, a failed
    publish is dead-lettered with a named reason and the relay continues so
    one poison event cannot stall the queue forever.
    """
    published = 0
    for event in store.unpublished():
        event_id = event.get("id")
        if not event_id:
            raise ValueError(
                f"outbox event has no id, so it cannot be marked published "
                f"and would republish forever: {event!r}"
            )
        try:
            publish(event)
        except Exception as exc:
            if not continue_on_error:
                raise
            mark_dead = getattr(store, "mark_dead", None)
            if mark_dead is None:
                raise
            reason = f"publish_failed:{type(exc).__name__}:{exc}"
            mark_dead(event_id, reason)
            logger.error(
                "outbox.dead_lettered event_id=%s reason=%s", event_id, reason
            )
            continue
        store.mark_published(event_id)
        published += 1
        logger.info("outbox.published event_id=%s", event_id)
    return published


def handle_idempotent(dedup: DedupStore, key: str, handler: Callable[[], Any]) -> Any:
    """Run `handler` at most once per key; a repeat returns the cached result.

    This is what makes at-least-once delivery safe. The second delivery of a
    message does not re-run the handler at all - no second charge, no second
    send - it returns exactly what the first run produced.

    A handler that raises is NOT recorded, so the key stays unseen and a
    retry gets a real attempt. Recording a failure would permanently swallow
    the work.
    """
    if not isinstance(key, str) or not key.strip():
        raise ValueError(
            f"an idempotency key is required to handle a message, got {key!r}; "
            f"without one, a re-delivery cannot be recognised and will double-apply"
        )
    key = key.strip()

    if dedup.seen(key):
        logger.info("outbox.duplicate_suppressed key=%s", key)
        return dedup.cached(key)

    result = handler()
    dedup.record(key, result)
    return result


def run_batch(items: Sequence, process: Callable[[Any], Any],
              checkpoint: Checkpoint) -> dict:
    """Process `items` in order, checkpointing after each, resuming on restart.

    Returns `{"processed": int, "resumed_from": int}` - how many items this
    run handled, and the index it started at.

    The checkpoint is saved only *after* `process` returns, so an item whose
    processing raises is not marked done and is retried on the next run. If
    `process` raises, the exception propagates (that is the crash), and the
    checkpoint holds the last item that genuinely completed.
    """
    if items is None:
        raise ValueError("run_batch needs a sequence of items, got None")

    last_done = checkpoint.load()
    if last_done is not None and not isinstance(last_done, int):
        raise ValueError(
            f"checkpoint.load() must return an int index or None, got {last_done!r}"
        )

    start = 0 if last_done is None else last_done + 1
    processed = 0

    for index in range(start, len(items)):
        process(items[index])
        checkpoint.save(index)
        processed += 1

    logger.info("outbox.batch_complete resumed_from=%d processed=%d", start, processed)
    return {"processed": processed, "resumed_from": start}
