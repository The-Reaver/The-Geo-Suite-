"""Dependency-free resilience toolkit for calls that cross the network.

Implements `references/patterns/resilience-circuit-breakers.md` (R-A4) per
`specs/SPEC_RESILIENCE_CIRCUIT_BREAKER.md`. Stripe, Twilio and Resend will
fail; this module is what every such call gets wrapped in so a downstream
outage degrades one feature instead of taking the request path with it.

Three pieces:

    CircuitBreaker        fail fast while a dependency is down, recover on a
                          single probe, and make every fallback observable.
    retry_with_backoff    retry only with exponential backoff + jitter.
    with_idempotency_key  carry one stable key across the retries of a
                          mutating call so it cannot double-apply.

Time is injected everywhere (`clock`, `sleep`), so the whole toolkit is
offline and deterministic under test - no real waiting, no network.

The breaker deliberately never hides a degraded state: every fallback
activation is logged and reported to `on_fallback(reason)` with a specific
reason string. A silent failover is the anti-pattern this exists to prevent.
"""
from __future__ import annotations

import logging
import random
import threading
import time
import uuid
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

CLOSED = "CLOSED"
OPEN = "OPEN"
HALF_OPEN = "HALF_OPEN"

IDEMPOTENCY_HEADER = "Idempotency-Key"


class CircuitOpenError(RuntimeError):
    """The breaker refused a call and the caller supplied no fallback.

    Carries the same reason string handed to `on_fallback`, so the failure
    names which circuit refused, why, and when it will probe again.
    """


def _label(fn: Any) -> str:
    return getattr(fn, "__name__", None) or repr(fn)


class CircuitBreaker:
    """Fail fast while a dependency is failing, then recover on one probe.

    States and transitions::

        CLOSED  --failure_threshold consecutive failures-->  OPEN
        OPEN    --reset_timeout_s elapsed on the clock-->    HALF_OPEN
        HALF_OPEN --one success-->  CLOSED
        HALF_OPEN --one failure-->  OPEN   (timer restarts)

    While OPEN the wrapped callable is never invoked - that is the whole
    point, and `test_open_breaker_fails_fast_without_invoking_fn` proves it
    by asserting the call count does not move.

    HALF_OPEN admits exactly one recovery probe at a time. Letting the full
    load through the moment the timer expires is how a recovering dependency
    gets knocked over again, so any further caller keeps failing fast until
    the probe resolves. This single-probe rule is the canonical breaker
    behaviour from the cited Azure pattern rather than something the spec
    spells out; it is flagged in `reports/RESILIENCE_BUILD_REPORT.md`.

    A `clock` is injected (default `time.monotonic`) so `reset_timeout_s`
    can be advanced in tests without sleeping. `time.monotonic` is used
    rather than `time.time` because a wall-clock adjustment must not be able
    to hold the breaker open or release it early.
    """

    def __init__(self, *, failure_threshold: int, reset_timeout_s: float,
                 clock: Callable[[], float] = time.monotonic,
                 name: str = "circuit") -> None:
        if not isinstance(failure_threshold, int) or failure_threshold < 1:
            raise ValueError(
                "failure_threshold must be an int >= 1; a breaker that opens "
                f"on zero failures would never call anything (got {failure_threshold!r})"
            )
        if reset_timeout_s <= 0:
            raise ValueError(
                "reset_timeout_s must be > 0; a zero timeout would half-open "
                f"immediately and defeat the breaker (got {reset_timeout_s!r})"
            )
        self._failure_threshold = failure_threshold
        self._reset_timeout_s = float(reset_timeout_s)
        self._clock = clock
        self._name = name
        self._lock = threading.RLock()
        self._state = CLOSED
        self._consecutive_failures = 0
        self._opened_at: Optional[float] = None
        self._probe_in_flight = False

    # -- observability -----------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> str:
        """Current state, applying the OPEN -> HALF_OPEN transition lazily.

        Reading the state is enough to move an expired OPEN breaker to
        HALF_OPEN, so a test can advance the injected clock and observe the
        transition without having to make a call first.
        """
        with self._lock:
            self._maybe_half_open()
            return self._state

    @property
    def consecutive_failures(self) -> int:
        with self._lock:
            return self._consecutive_failures

    @property
    def seconds_until_probe(self) -> float:
        """Seconds until the OPEN breaker will admit a probe. 0.0 otherwise."""
        with self._lock:
            if self._state != OPEN or self._opened_at is None:
                return 0.0
            remaining = self._reset_timeout_s - (self._clock() - self._opened_at)
            return max(0.0, remaining)

    # -- the call path -----------------------------------------------------

    def call(self, fn: Callable[..., Any], *args: Any,
             fallback: Any = None,
             on_fallback: Optional[Callable[[str], None]] = None,
             **kwargs: Any) -> Any:
        """Run `fn(*args, **kwargs)` under the breaker.

        On success the result is returned and the failure count resets.

        When the call is refused (OPEN) or raises, the breaker degrades:
        `on_fallback(reason)` fires exactly once with a specific reason
        string, and `fallback` supplies the answer. `fallback` may be a
        callable (invoked with no arguments) or a plain value returned
        as-is - a cached dict is as valid a fallback as a function.

        With no `fallback` there is nothing to degrade to, so the breaker
        stays transparent: a refused call raises `CircuitOpenError` and a
        failed call re-raises the original exception untouched. It never
        returns None to paper over a failure.
        """
        refusal = self._reserve_slot(_label(fn))
        if refusal is not None:
            return self._degrade(refusal, fallback, on_fallback)
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - classified, then re-raised or degraded
            reason = self._record_failure(_label(fn), exc)
            return self._degrade(reason, fallback, on_fallback, error=exc)
        self._record_success()
        return result

    # -- state machine -----------------------------------------------------

    def _maybe_half_open(self) -> None:
        """OPEN -> HALF_OPEN once reset_timeout_s has elapsed. Caller holds the lock."""
        if self._state != OPEN or self._opened_at is None:
            return
        if (self._clock() - self._opened_at) < self._reset_timeout_s:
            return
        self._state = HALF_OPEN
        self._probe_in_flight = False
        logger.info(
            "resilience.half_open circuit=%s after reset_timeout_s=%.3f; admitting one probe",
            self._name, self._reset_timeout_s,
        )

    def _reserve_slot(self, label: str) -> Optional[str]:
        """Return None if the call may proceed, else the refusal reason."""
        with self._lock:
            self._maybe_half_open()
            if self._state == OPEN:
                return (
                    f"circuit '{self._name}' is OPEN after {self._consecutive_failures} "
                    f"consecutive failures; failing fast without calling {label}; "
                    f"next probe in {self.seconds_until_probe:.1f}s"
                )
            if self._state == HALF_OPEN:
                if self._probe_in_flight:
                    return (
                        f"circuit '{self._name}' is HALF_OPEN and its single recovery "
                        f"probe is already in flight; failing fast without calling {label}"
                    )
                self._probe_in_flight = True
            return None

    def _record_failure(self, label: str, exc: BaseException) -> str:
        with self._lock:
            was_probe = self._state == HALF_OPEN
            self._probe_in_flight = False
            detail = f"{type(exc).__name__}: {exc}"

            if was_probe:
                self._state = OPEN
                self._opened_at = self._clock()
                # The probe failing means the dependency is still down: hold the
                # count at the threshold so the breaker reads as fully tripped.
                self._consecutive_failures = max(
                    self._consecutive_failures, self._failure_threshold
                )
                logger.warning(
                    "resilience.reopened circuit=%s probe_error=%s", self._name, detail
                )
                return (
                    f"circuit '{self._name}' recovery probe to {label} failed ({detail}); "
                    f"reopened for another {self._reset_timeout_s:.1f}s"
                )

            self._consecutive_failures += 1
            if self._consecutive_failures >= self._failure_threshold:
                self._state = OPEN
                self._opened_at = self._clock()
                logger.warning(
                    "resilience.opened circuit=%s failures=%d error=%s",
                    self._name, self._consecutive_failures, detail,
                )
                return (
                    f"circuit '{self._name}' opened after {self._consecutive_failures} "
                    f"consecutive failures calling {label} ({detail}); "
                    f"failing fast for {self._reset_timeout_s:.1f}s"
                )

            return (
                f"call to {label} failed ({detail}); {self._consecutive_failures} of "
                f"{self._failure_threshold} consecutive failures before circuit "
                f"'{self._name}' opens"
            )

    def _record_success(self) -> None:
        with self._lock:
            self._probe_in_flight = False
            if self._state == HALF_OPEN:
                logger.info(
                    "resilience.closed circuit=%s recovery probe succeeded", self._name
                )
            self._state = CLOSED
            self._consecutive_failures = 0
            self._opened_at = None

    def _degrade(self, reason: str, fallback: Any,
                 on_fallback: Optional[Callable[[str], None]],
                 error: Optional[BaseException] = None) -> Any:
        """Log the degraded state, notify, and return the fallback (or raise)."""
        logger.warning("resilience.degraded circuit=%s reason=%s", self._name, reason)

        if fallback is None:
            if error is not None:
                raise error
            raise CircuitOpenError(reason)

        if on_fallback is not None:
            try:
                on_fallback(reason)
            except Exception:  # noqa: BLE001 - telemetry must never break the call path
                logger.exception(
                    "resilience.on_fallback_failed circuit=%s; the fallback still applies",
                    self._name,
                )

        return fallback() if callable(fallback) else fallback


def retry_with_backoff(fn: Callable[[], Any], *, attempts: int, base_delay_s: float,
                       jitter: bool = True,
                       sleep: Callable[[float], None] = time.sleep) -> Any:
    """Call `fn` up to `attempts` times, backing off exponentially between tries.

    Delay before retry *n* (1-indexed) is capped at
    `base_delay_s * 2 ** (n - 1)`.

    With `jitter=True` the delay is drawn with **equal jitter** -
    `cap/2 + uniform(0, cap/2)` - rather than the full-jitter `uniform(0, cap)`
    also described in the cited AWS post. Equal jitter still spreads a
    thundering herd, but it guarantees a strictly positive delay, so there is
    no draw in which this function degenerates into a bare retry. Bare
    retries are the banned anti-pattern here, and this makes the ban a
    property of the code rather than a probability.

    `sleep` is injected so tests record the delays instead of waiting. If
    every attempt fails the last exception is re-raised untouched.
    """
    if not isinstance(attempts, int) or attempts < 1:
        raise ValueError(
            f"attempts must be an int >= 1; got {attempts!r}, which would never call fn"
        )
    if base_delay_s <= 0:
        raise ValueError(
            f"base_delay_s must be > 0; got {base_delay_s!r}, which is a bare retry"
        )

    last_exc: Optional[BaseException] = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - retried, then re-raised
            last_exc = exc
            if attempt == attempts:
                break
            cap = base_delay_s * (2 ** (attempt - 1))
            delay = (cap / 2) + random.uniform(0, cap / 2) if jitter else cap
            logger.warning(
                "resilience.retry fn=%s attempt=%d/%d delay_s=%.3f error=%s: %s",
                _label(fn), attempt, attempts, delay, type(exc).__name__, exc,
            )
            sleep(delay)

    assert last_exc is not None  # unreachable: the loop only breaks after an exception
    raise last_exc


def new_idempotency_key() -> str:
    """Mint a fresh UUID4 idempotency key for one logical mutating operation.

    Call this once per operation, not once per attempt - the retries of a
    single charge or send must all carry the same key.
    """
    return str(uuid.uuid4())


def with_idempotency_key(headers: dict, key: str) -> dict:
    """Return a copy of `headers` carrying `key` as the idempotency header.

    A copy, not a mutation, so the caller's shared default-headers dict
    cannot be contaminated with one request's key. Because the key is an
    argument rather than generated here, every retry of the same operation
    reproduces the same header, which is what makes the provider return the
    cached result instead of repeating the side effect.
    """
    if not isinstance(key, str) or not key.strip():
        raise ValueError(
            "an idempotency key is required for a mutating request; got "
            f"{key!r}. Mint one per operation with new_idempotency_key() and "
            "reuse it across that operation's retries"
        )
    merged = dict(headers or {})
    merged[IDEMPOTENCY_HEADER] = key.strip()
    return merged
