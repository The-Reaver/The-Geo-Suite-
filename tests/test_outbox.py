"""Standalone test for the outbox worker primitives (SPEC_EVENT_DRIVEN_OUTBOX).

The two proofs that matter:

  * a re-delivered message applies ONCE - the handler call count proves it,
    not a boolean;
  * a crashed batch resumes from its checkpoint and every item is processed
    exactly once across the two runs.

Everything runs against the in-memory stores, so there is no broker and no
database anywhere in this file.

No pytest - standalone-runnable with a __main__ runner printing a real N/N.
"""
import logging
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)
BACKEND = os.path.join(PROJ, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.services.worker.outbox import (  # noqa: E402
    InMemoryCheckpoint,
    InMemoryDedupStore,
    InMemoryOutboxStore,
    handle_idempotent,
    relay,
    run_batch,
)

# Per-event info logging would bury the battery output; the assertions below
# read call counts and store state, not the log stream.
logging.getLogger("app.services.worker.outbox").setLevel(logging.CRITICAL)


class Publisher:
    """A stand-in broker that records every event it was handed."""

    def __init__(self, fail_on=None):
        self.delivered = []
        self.fail_on = fail_on

    def __call__(self, event):
        if self.fail_on is not None and event.get("site_id") == self.fail_on:
            raise RuntimeError(f"broker refused site_id={self.fail_on}")
        self.delivered.append(event)


class Handler:
    """A consumer whose invocations are counted, so double-apply is visible."""

    def __init__(self, result=None, error=None):
        self.calls = 0
        self.result = result if result is not None else {"status": "charged"}
        self.error = error

    def __call__(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


def _store_with(*site_ids):
    store = InMemoryOutboxStore()
    ids = [store.add({"type": "site.regenerate", "site_id": s}) for s in site_ids]
    return store, ids


# --- outbox relay -----------------------------------------------------------

def test_added_event_stays_unpublished_until_relayed():
    store, ids = _store_with("s1")
    assert len(ids) == 1 and ids[0], ids

    pending = store.unpublished()
    assert len(pending) == 1, f"the event must be pending before any relay, got {pending}"
    assert pending[0]["site_id"] == "s1", pending[0]
    assert pending[0]["id"] == ids[0], pending[0]

    relay(store, Publisher())
    assert store.unpublished() == [], (
        f"after a relay nothing may remain pending, got {store.unpublished()}"
    )


def test_relay_publishes_every_event_once_in_order():
    store, ids = _store_with("s1", "s2", "s3")
    publisher = Publisher()

    count = relay(store, publisher)

    assert count == 3, f"relay must return the real published count, got {count}"
    assert [e["site_id"] for e in publisher.delivered] == ["s1", "s2", "s3"], (
        f"events must publish in insertion order, got {publisher.delivered}"
    )
    assert store.published_ids() == ids, store.published_ids()


def test_second_relay_publishes_zero():
    store, _ids = _store_with("s1", "s2")
    publisher = Publisher()

    first = relay(store, publisher)
    second = relay(store, publisher)

    assert first == 2, first
    assert second == 0, (
        f"a repeat relay must publish nothing, got {second} - that is a duplicate delivery"
    )
    assert len(publisher.delivered) == 2, (
        f"the broker must have seen each event exactly once, got "
        f"{[e['site_id'] for e in publisher.delivered]}"
    )


def test_failed_publish_leaves_the_event_pending_for_the_next_run():
    store, _ids = _store_with("s1", "s2", "s3")
    broken = Publisher(fail_on="s2")

    try:
        relay(store, broken)
    except RuntimeError as exc:
        assert "broker refused site_id=s2" in str(exc), exc
    else:
        raise AssertionError("a publish failure must propagate, not be swallowed")

    pending = [e["site_id"] for e in store.unpublished()]
    assert pending == ["s2", "s3"], (
        f"s1 published so it must be marked done; s2 failed and s3 never ran, so "
        f"both must still be pending. Got {pending}"
    )

    working = Publisher()
    assert relay(store, working) == 2, "the retry must pick up exactly the two stragglers"
    assert [e["site_id"] for e in working.delivered] == ["s2", "s3"], working.delivered
    assert [e["site_id"] for e in broken.delivered] == ["s1"], (
        f"s1 must not be republished on the retry, got {broken.delivered}"
    )


def test_relay_over_an_empty_outbox_is_a_no_op():
    store = InMemoryOutboxStore()
    publisher = Publisher()
    assert relay(store, publisher) == 0
    assert publisher.delivered == []


def test_marking_an_unknown_event_published_is_refused():
    store, _ids = _store_with("s1")
    try:
        store.mark_published("not-a-real-id")
    except KeyError as exc:
        assert "cannot mark unknown event id" in str(exc), exc
    else:
        raise AssertionError(
            "marking an id that is not in the outbox must raise - silently "
            "accepting it would hide a lost event"
        )


def test_stored_event_does_not_alias_the_callers_dict():
    store = InMemoryOutboxStore()
    payload = {"type": "site.regenerate", "site_id": "s1"}
    store.add(payload)
    payload["site_id"] = "MUTATED"

    pending = store.unpublished()
    assert pending[0]["site_id"] == "s1", (
        f"the outbox must snapshot the event at add() time, got {pending[0]}"
    )


# --- idempotent consumer ----------------------------------------------------

def test_handler_runs_once_for_a_key():
    dedup = InMemoryDedupStore()
    handler = Handler(result={"charge_id": "ch_1"})

    result = handle_idempotent(dedup, "evt_100", handler)

    assert result == {"charge_id": "ch_1"}, result
    assert handler.calls == 1, f"first delivery must run the handler once, got {handler.calls}"
    assert dedup.seen("evt_100") is True


def test_redelivery_returns_the_cached_result_without_rerunning():
    dedup = InMemoryDedupStore()
    handler = Handler(result={"charge_id": "ch_1"})

    first = handle_idempotent(dedup, "evt_100", handler)
    second = handle_idempotent(dedup, "evt_100", handler)
    third = handle_idempotent(dedup, "evt_100", handler)

    assert handler.calls == 1, (
        f"three deliveries of the same key must apply ONCE; the handler ran "
        f"{handler.calls} times, which is {handler.calls - 1} duplicate side effect(s)"
    )
    assert first == second == third == {"charge_id": "ch_1"}, (first, second, third)


def test_different_keys_each_get_their_own_run():
    dedup = InMemoryDedupStore()
    handler = Handler()

    handle_idempotent(dedup, "evt_1", handler)
    handle_idempotent(dedup, "evt_2", handler)

    assert handler.calls == 2, (
        f"distinct keys are distinct work and must both run, got {handler.calls}"
    )


def test_a_failed_handler_is_not_recorded_so_a_retry_reruns():
    dedup = InMemoryDedupStore()
    failing = Handler(error=RuntimeError("stripe timeout"))

    try:
        handle_idempotent(dedup, "evt_7", failing)
    except RuntimeError as exc:
        assert "stripe timeout" in str(exc), exc
    else:
        raise AssertionError("a handler failure must propagate")

    assert dedup.seen("evt_7") is False, (
        "a failed handler must not be recorded, or the work is swallowed forever"
    )

    recovered = Handler(result={"charge_id": "ch_9"})
    assert handle_idempotent(dedup, "evt_7", recovered) == {"charge_id": "ch_9"}
    assert recovered.calls == 1, recovered.calls


def test_idempotent_handling_refuses_an_empty_key():
    dedup = InMemoryDedupStore()
    handler = Handler()
    for bad in ("", "   ", None, 7):
        try:
            handle_idempotent(dedup, bad, handler)
        except ValueError as exc:
            assert "an idempotency key is required" in str(exc), exc
        else:
            raise AssertionError(f"key={bad!r} must be refused, not handled blind")
    assert handler.calls == 0, (
        f"no handler may run without a usable key, got {handler.calls} calls"
    )


# --- resumable batch --------------------------------------------------------

def test_batch_processes_every_item_once_from_scratch():
    items = ["s1", "s2", "s3"]
    done = []
    checkpoint = InMemoryCheckpoint()

    outcome = run_batch(items, done.append, checkpoint)

    assert outcome == {"processed": 3, "resumed_from": 0}, outcome
    assert done == items, done
    assert checkpoint.saves == [0, 1, 2], (
        f"the cursor must advance after each item, got {checkpoint.saves}"
    )


def test_crashed_batch_resumes_from_its_checkpoint():
    items = ["s1", "s2", "s3", "s4", "s5"]
    done = []
    checkpoint = InMemoryCheckpoint()

    crashed = {"already": False}

    def crash_on_s3(item):
        # The crash happens BEFORE the item is recorded, so s3 genuinely did
        # not get processed on the first run. It fires once: the restarted
        # worker is healthy again.
        if item == "s3" and not crashed["already"]:
            crashed["already"] = True
            raise RuntimeError("worker killed mid-batch")
        done.append(item)

    try:
        run_batch(items, crash_on_s3, checkpoint)
    except RuntimeError as exc:
        assert "worker killed mid-batch" in str(exc), exc
    else:
        raise AssertionError("the simulated crash must propagate out of run_batch")

    assert done == ["s1", "s2"], f"only the pre-crash items may be done, got {done}"
    assert checkpoint.load() == 1, (
        f"the cursor must point at the last item that genuinely completed, got "
        f"{checkpoint.load()}"
    )

    outcome = run_batch(items, crash_on_s3, checkpoint)

    assert outcome["resumed_from"] == 2, (
        f"the second run must restart at the failed item, got {outcome}"
    )
    assert outcome["processed"] == 3, outcome
    assert done == ["s1", "s2", "s3", "s4", "s5"], done
    for item in items:
        assert done.count(item) == 1, (
            f"{item} was processed {done.count(item)} times across the two runs; "
            f"exactly once is the invariant. Full record: {done}"
        )


def test_completed_batch_is_not_reprocessed():
    items = ["s1", "s2", "s3"]
    done = []
    checkpoint = InMemoryCheckpoint()

    run_batch(items, done.append, checkpoint)
    outcome = run_batch(items, done.append, checkpoint)

    assert outcome == {"processed": 0, "resumed_from": 3}, outcome
    assert done == ["s1", "s2", "s3"], (
        f"re-running a finished batch must do nothing, got {done}"
    )


def test_batch_resumes_from_a_preexisting_cursor():
    items = ["s1", "s2", "s3", "s4"]
    done = []

    outcome = run_batch(items, done.append, InMemoryCheckpoint(last_processed_index=1))

    assert outcome == {"processed": 2, "resumed_from": 2}, outcome
    assert done == ["s3", "s4"], (
        f"items at or before the cursor must be skipped, got {done}"
    )


def test_empty_batch_is_an_honest_no_op():
    checkpoint = InMemoryCheckpoint()
    outcome = run_batch([], lambda item: None, checkpoint)
    assert outcome == {"processed": 0, "resumed_from": 0}, outcome
    assert checkpoint.saves == [], checkpoint.saves


def test_batch_rejects_a_corrupt_checkpoint():
    class BadCheckpoint:
        def load(self):
            return "not-an-index"

        def save(self, index):
            raise AssertionError("save must never be reached with a corrupt cursor")

    try:
        run_batch(["s1"], lambda item: None, BadCheckpoint())
    except ValueError as exc:
        assert "must return an int index or None" in str(exc), exc
    else:
        raise AssertionError(
            "a non-integer cursor must be refused; guessing would silently "
            "reprocess or skip real work"
        )


def test_poison_event_dead_lettered_does_not_block_queue():
    store, ids = _store_with("poison", "ok-site")
    pub = Publisher(fail_on="poison")
    try:
        relay(store, pub)
    except RuntimeError:
        pass
    else:
        raise AssertionError("default relay must still raise on poison")

    # Resume with continue_on_error: poison parks, later event publishes.
    published = relay(store, pub, continue_on_error=True)
    assert published == 1, published
    dead = store.dead_letters()
    assert len(dead) == 1, dead
    assert dead[0]["event_id"] == ids[0]
    assert "publish_failed" in dead[0]["reason"], dead[0]["reason"]
    assert "poison" in dead[0]["reason"]
    assert len(store.unpublished()) == 0, store.unpublished()
    assert any(e.get("site_id") == "ok-site" for e in pub.delivered)


def _run_all():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print("PASS  " + t.__name__)
            passed += 1
        except AssertionError as e:
            print("FAIL  " + t.__name__ + ": " + str(e))
        except Exception as e:
            print("FAIL  " + t.__name__ + ": " + type(e).__name__ + " " + str(e))
    print(f"\n{passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
