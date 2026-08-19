"""Standalone test for the resilience toolkit (SPEC_RESILIENCE_CIRCUIT_BREAKER).

Proves the circuit breaker trips on its threshold, fails fast while OPEN
*without invoking the wrapped callable*, recovers through HALF_OPEN, and
reports every fallback activation with a specific reason. Also proves retry
never happens without backoff, and that an idempotency key survives retries.

Fully offline and deterministic: the clock and the sleep are injected, so
nothing here waits on real time and no network is touched.

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

from app.core.resilience import (  # noqa: E402
    CLOSED,
    HALF_OPEN,
    IDEMPOTENCY_HEADER,
    OPEN,
    CircuitBreaker,
    CircuitOpenError,
    new_idempotency_key,
    retry_with_backoff,
    with_idempotency_key,
)

# The toolkit logs every degraded state at WARNING, which would bury the
# battery output. Reason strings are asserted from the on_fallback callback,
# not scraped from the log stream; test_fallback_is_logged_even_without_a
# _callback re-enables the logger to prove the log itself still happens.
RESILIENCE_LOGGER = logging.getLogger("app.core.resilience")
RESILIENCE_LOGGER.setLevel(logging.CRITICAL)


class FakeClock:
    """Injected monotonic clock. Time only moves when a test moves it."""

    def __init__(self, now=0.0):
        self.now = float(now)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += float(seconds)


class Dependency:
    """A stand-in for Stripe/Twilio that counts how often it was really called."""

    def __init__(self, *, fail=True, error=None, result="ok"):
        self.fail = fail
        self.error = error or RuntimeError("dependency down")
        self.result = result
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        if self.fail:
            raise self.error
        return self.result


class Recorder:
    """Captures every on_fallback(reason) so activations can be counted."""

    def __init__(self):
        self.reasons = []

    def __call__(self, reason):
        self.reasons.append(reason)


def _breaker(clock, *, threshold=3, timeout=30.0, name="stripe"):
    return CircuitBreaker(
        failure_threshold=threshold, reset_timeout_s=timeout,
        clock=clock, name=name,
    )


def _trip(breaker, dep, times):
    """Drive `times` failing calls through the breaker, absorbing the fallback."""
    for _ in range(times):
        breaker.call(dep, fallback="degraded")


# --- tripping ---------------------------------------------------------------

def test_breaker_opens_only_on_the_threshold_failure():
    clock = FakeClock()
    breaker = _breaker(clock, threshold=3)
    dep = Dependency()

    _trip(breaker, dep, 2)
    assert breaker.state == CLOSED, (
        f"2 of 3 failures must leave the breaker CLOSED, got {breaker.state}"
    )
    assert breaker.consecutive_failures == 2, breaker.consecutive_failures

    breaker.call(dep, fallback="degraded")
    assert breaker.state == OPEN, (
        f"the 3rd consecutive failure must open the breaker, got {breaker.state}"
    )
    assert dep.calls == 3, f"all 3 failures must have reached the dependency, got {dep.calls}"


def test_open_breaker_fails_fast_without_invoking_fn():
    clock = FakeClock()
    breaker = _breaker(clock, threshold=2)
    dep = Dependency()

    _trip(breaker, dep, 2)
    assert breaker.state == OPEN, breaker.state
    calls_when_opened = dep.calls
    assert calls_when_opened == 2, calls_when_opened

    for _ in range(5):
        assert breaker.call(dep, fallback="degraded") == "degraded"

    assert dep.calls == calls_when_opened, (
        "an OPEN breaker must not invoke the wrapped callable at all; call count "
        f"moved {calls_when_opened} -> {dep.calls}"
    )


def test_success_resets_the_consecutive_failure_count():
    clock = FakeClock()
    breaker = _breaker(clock, threshold=3)
    failing = Dependency()
    healthy = Dependency(fail=False, result="live")

    _trip(breaker, failing, 2)
    assert breaker.call(healthy) == "live"
    assert breaker.consecutive_failures == 0, (
        f"a success must reset the run of failures, got {breaker.consecutive_failures}"
    )

    _trip(breaker, failing, 2)
    assert breaker.state == CLOSED, (
        "failures either side of a success are not consecutive, so the breaker "
        f"must still be CLOSED, got {breaker.state}"
    )


# --- fallback visibility ----------------------------------------------------

def test_blocked_call_reports_reason_exactly_once():
    clock = FakeClock()
    breaker = _breaker(clock, threshold=2, timeout=30.0)
    dep = Dependency()
    seen = Recorder()

    _trip(breaker, dep, 2)
    seen.reasons.clear()

    assert breaker.call(dep, fallback="cached", on_fallback=seen) == "cached"
    assert len(seen.reasons) == 1, (
        f"exactly one report per blocked call, got {len(seen.reasons)}: {seen.reasons}"
    )
    reason = seen.reasons[0]
    assert "circuit 'stripe' is OPEN" in reason, reason
    assert "failing fast" in reason, reason
    assert "next probe in 30.0s" in reason, reason


def test_failure_fallback_reason_names_the_real_error():
    clock = FakeClock()
    breaker = _breaker(clock, threshold=5)
    dep = Dependency(error=ValueError("stripe 503"))
    seen = Recorder()

    breaker.call(dep, fallback="cached", on_fallback=seen)

    assert len(seen.reasons) == 1, seen.reasons
    reason = seen.reasons[0]
    assert "ValueError: stripe 503" in reason, (
        f"the reason must carry the real error, not a generic message: {reason}"
    )
    assert "1 of 5 consecutive failures" in reason, reason


def test_callable_and_static_fallbacks_both_supply_a_value():
    clock = FakeClock()
    breaker = _breaker(clock, threshold=1)
    dep = Dependency()

    assert breaker.call(dep, fallback=lambda: {"source": "cache"}) == {"source": "cache"}
    assert breaker.call(dep, fallback={"source": "static"}) == {"source": "static"}


def test_no_fallback_reraises_the_original_error():
    clock = FakeClock()
    breaker = _breaker(clock, threshold=5)
    dep = Dependency(error=KeyError("missing customer"))

    try:
        breaker.call(dep)
    except KeyError as exc:
        assert "missing customer" in str(exc), exc
    else:
        raise AssertionError(
            "with no fallback the breaker must stay transparent and re-raise, "
            "not swallow the error and return None"
        )


def test_no_fallback_while_open_raises_circuit_open_error():
    clock = FakeClock()
    breaker = _breaker(clock, threshold=2)
    dep = Dependency()

    _trip(breaker, dep, 2)
    calls_when_opened = dep.calls

    try:
        breaker.call(dep)
    except CircuitOpenError as exc:
        assert "is OPEN" in str(exc), exc
    else:
        raise AssertionError("a refused call with no fallback must raise CircuitOpenError")

    assert dep.calls == calls_when_opened, "the refused call still must not reach the dependency"


def test_fallback_is_logged_even_without_a_callback():
    clock = FakeClock()
    breaker = _breaker(clock, threshold=1)
    dep = Dependency()

    class Capture(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []

        def emit(self, record):
            self.records.append(record)

    capture = Capture()
    previous_level = RESILIENCE_LOGGER.level
    RESILIENCE_LOGGER.setLevel(logging.WARNING)
    RESILIENCE_LOGGER.addHandler(capture)
    try:
        assert breaker.call(dep, fallback="degraded") == "degraded"
    finally:
        RESILIENCE_LOGGER.removeHandler(capture)
        RESILIENCE_LOGGER.setLevel(previous_level)

    degraded = [r for r in capture.records if "resilience.degraded" in r.getMessage()]
    assert len(degraded) == 1, (
        "a fallback with no on_fallback callback must still be logged - a silent "
        f"failover is the anti-pattern; got {[r.getMessage() for r in capture.records]}"
    )
    assert degraded[0].levelno == logging.WARNING, (
        f"a degraded state is at least a WARNING, got {degraded[0].levelname}"
    )


def test_on_fallback_failure_does_not_break_the_call_path():
    clock = FakeClock()
    breaker = _breaker(clock, threshold=1)
    dep = Dependency()

    def exploding_reporter(reason):
        raise RuntimeError("telemetry sink is down")

    assert breaker.call(dep, fallback="degraded", on_fallback=exploding_reporter) == "degraded", (
        "a broken telemetry sink must not take out the request path it is observing"
    )


# --- recovery ---------------------------------------------------------------

def test_breaker_half_opens_only_after_the_reset_timeout():
    clock = FakeClock()
    breaker = _breaker(clock, threshold=2, timeout=30.0)
    dep = Dependency()

    _trip(breaker, dep, 2)
    assert breaker.state == OPEN, breaker.state

    clock.advance(29.9)
    assert breaker.state == OPEN, (
        f"still inside the timeout, so the breaker must stay OPEN, got {breaker.state}"
    )
    assert round(breaker.seconds_until_probe, 4) == 0.1, breaker.seconds_until_probe

    clock.advance(0.1)
    assert breaker.state == HALF_OPEN, (
        f"the timeout has elapsed, so the breaker must admit a probe, got {breaker.state}"
    )


def test_half_open_success_closes_the_circuit():
    clock = FakeClock()
    breaker = _breaker(clock, threshold=2, timeout=10.0)
    failing = Dependency()
    recovered = Dependency(fail=False, result="live")

    _trip(breaker, failing, 2)
    clock.advance(10.0)
    assert breaker.state == HALF_OPEN, breaker.state

    assert breaker.call(recovered) == "live"
    assert recovered.calls == 1, (
        f"the probe must actually reach the dependency, got {recovered.calls} calls"
    )
    assert breaker.state == CLOSED, (
        f"one success must close the circuit, got {breaker.state}"
    )
    assert breaker.consecutive_failures == 0, breaker.consecutive_failures


def test_half_open_failure_reopens_and_restarts_the_timer():
    clock = FakeClock()
    breaker = _breaker(clock, threshold=2, timeout=10.0)
    dep = Dependency()
    seen = Recorder()

    _trip(breaker, dep, 2)
    clock.advance(10.0)
    assert breaker.state == HALF_OPEN, breaker.state
    seen.reasons.clear()
    calls_before_probe = dep.calls

    breaker.call(dep, fallback="degraded", on_fallback=seen)
    assert dep.calls == calls_before_probe + 1, "the probe itself must reach the dependency"
    assert breaker.state == OPEN, (
        f"a failed probe must reopen the circuit, got {breaker.state}"
    )
    assert "recovery probe" in seen.reasons[0], seen.reasons[0]
    assert "reopened for another 10.0s" in seen.reasons[0], seen.reasons[0]

    clock.advance(9.9)
    assert breaker.state == OPEN, (
        "the reset timer must restart from the failed probe, not from the original "
        f"trip, got {breaker.state}"
    )
    clock.advance(0.1)
    assert breaker.state == HALF_OPEN, breaker.state


def test_half_open_admits_only_one_probe_at_a_time():
    clock = FakeClock()
    breaker = _breaker(clock, threshold=2, timeout=10.0)
    dep = Dependency()
    seen = Recorder()
    nested = {}

    _trip(breaker, dep, 2)
    clock.advance(10.0)
    assert breaker.state == HALF_OPEN, breaker.state

    def probe():
        # Re-enter while this probe is still in flight: the second caller must be
        # refused so a recovering dependency is not hit by the full load at once.
        nested["result"] = breaker.call(dep, fallback="still-degraded", on_fallback=seen)
        return "probe-ok"

    assert breaker.call(probe) == "probe-ok"
    assert nested["result"] == "still-degraded", nested
    assert len(seen.reasons) == 1, seen.reasons
    assert "single recovery probe is already in flight" in seen.reasons[0], seen.reasons[0]
    assert dep.calls == 2, (
        f"the re-entrant call must not reach the dependency, got {dep.calls} calls"
    )


def test_breaker_rejects_nonsense_configuration():
    for bad in (0, -1):
        try:
            CircuitBreaker(failure_threshold=bad, reset_timeout_s=1.0)
        except ValueError as exc:
            assert "failure_threshold must be an int >= 1" in str(exc), exc
        else:
            raise AssertionError(f"failure_threshold={bad} must be rejected")

    try:
        CircuitBreaker(failure_threshold=1, reset_timeout_s=0)
    except ValueError as exc:
        assert "reset_timeout_s must be > 0" in str(exc), exc
    else:
        raise AssertionError("reset_timeout_s=0 must be rejected")


# --- retry with backoff -----------------------------------------------------

def test_retry_backs_off_exponentially_until_success():
    delays = []
    attempts_made = {"n": 0}

    def flaky():
        attempts_made["n"] += 1
        if attempts_made["n"] < 3:
            raise RuntimeError("timeout")
        return "ok"

    result = retry_with_backoff(
        flaky, attempts=5, base_delay_s=0.5, jitter=False, sleep=delays.append
    )

    assert result == "ok", result
    assert attempts_made["n"] == 3, attempts_made
    assert delays == [0.5, 1.0], (
        f"delays must double from base_delay_s and stop once fn succeeds, got {delays}"
    )


def test_retry_never_sleeps_zero_when_jittered():
    delays = []

    def always_fails():
        raise RuntimeError("down")

    try:
        retry_with_backoff(
            always_fails, attempts=6, base_delay_s=0.4, jitter=True, sleep=delays.append
        )
    except RuntimeError:
        pass

    assert len(delays) == 5, f"5 waits between 6 attempts, got {len(delays)}: {delays}"
    for i, delay in enumerate(delays):
        cap = 0.4 * (2 ** i)
        assert cap / 2 <= delay <= cap, (
            f"jittered delay {i} must land in [{cap / 2}, {cap}], got {delay} - a "
            f"delay of 0 would be a bare retry"
        )
    assert delays[-1] > delays[0], (
        f"jitter must not flatten the exponential growth: {delays}"
    )


def test_retry_exhausts_attempts_then_reraises_the_last_error():
    delays = []
    calls = {"n": 0}

    def always_fails():
        calls["n"] += 1
        raise ValueError(f"attempt {calls['n']} failed")

    try:
        retry_with_backoff(
            always_fails, attempts=3, base_delay_s=1.0, jitter=False, sleep=delays.append
        )
    except ValueError as exc:
        assert str(exc) == "attempt 3 failed", (
            f"the LAST error must surface, not an earlier one: {exc}"
        )
    else:
        raise AssertionError("exhausting every attempt must re-raise, not return None")

    assert calls["n"] == 3, f"fn must be called exactly `attempts` times, got {calls['n']}"
    assert delays == [1.0, 2.0], f"no sleep after the final attempt, got {delays}"


def test_retry_rejects_a_bare_retry_configuration():
    try:
        retry_with_backoff(lambda: None, attempts=0, base_delay_s=1.0)
    except ValueError as exc:
        assert "attempts must be an int >= 1" in str(exc), exc
    else:
        raise AssertionError("attempts=0 must be rejected")

    try:
        retry_with_backoff(lambda: None, attempts=3, base_delay_s=0)
    except ValueError as exc:
        assert "which is a bare retry" in str(exc), exc
    else:
        raise AssertionError("base_delay_s=0 is a bare retry and must be rejected")


# --- idempotency ------------------------------------------------------------

def test_idempotency_key_is_stable_across_retries():
    base = {"Authorization": "Bearer tok"}
    key = new_idempotency_key()

    first = with_idempotency_key(base, key)
    second = with_idempotency_key(base, key)

    assert first[IDEMPOTENCY_HEADER] == second[IDEMPOTENCY_HEADER] == key, (
        "a retry must carry the same key or the provider will repeat the side effect"
    )
    assert first["Authorization"] == "Bearer tok", first
    assert IDEMPOTENCY_HEADER not in base, (
        f"the caller's shared headers dict must not be mutated, got {base}"
    )


def test_new_idempotency_key_is_a_unique_uuid():
    keys = {new_idempotency_key() for _ in range(100)}
    assert len(keys) == 100, f"keys must be unique, got {len(keys)} distinct of 100"
    sample = keys.pop()
    assert len(sample) == 36 and sample.count("-") == 4, f"not a UUID4 string: {sample}"


def test_idempotency_key_rejects_an_empty_key():
    for bad in ("", "   ", None, 42):
        try:
            with_idempotency_key({}, bad)
        except ValueError as exc:
            assert "an idempotency key is required" in str(exc), exc
        else:
            raise AssertionError(f"key={bad!r} must be rejected, not silently accepted")


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
