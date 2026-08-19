# SPEC: SPEC_CCC_M5_ECONOMETRIC
"""Dark-traffic heuristics (ATT-5.1) — never labelled measured AI traffic."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .registry import WEIGHTS_STATUS


def visible_ai_traffic(ga4_sessions: list[dict]) -> dict:
    """ATT-5.1.1 — isolate AI Assistant channel; empty → EMPTY not zeros-as-traffic."""
    if not ga4_sessions:
        return {
            "status": "EMPTY",
            "series": [],
            "reason": "no GA4 sessions — empty series, not zeros-as-traffic",
        }
    by_day: dict[str, int] = defaultdict(int)
    for row in ga4_sessions:
        channel = (row.get("channel") or row.get("sessionDefaultChannelGroup") or "").lower()
        medium = (row.get("medium") or "").lower()
        source = (row.get("source") or "").lower()
        is_ai = (
            "ai" in channel
            or "assistant" in channel
            or "chatgpt" in source
            or "perplexity" in source
            or "gemini" in source
            or medium == "ai"
        )
        if not is_ai:
            continue
        day = row.get("date") or row.get("day")
        if not day:
            continue
        by_day[str(day)] += int(row.get("sessions") or row.get("count") or 1)
    series = [{"date": d, "visible_ai_sessions": by_day[d]} for d in sorted(by_day)]
    if not series:
        return {
            "status": "EMPTY",
            "series": [],
            "reason": "no AI Assistant channel sessions found",
        }
    return {
        "status": "OK",
        "series": series,
        "reason": "visible AI Assistant channel isolation",
    }


def estimate_dark_ai_traffic(
    sessions: list[dict],
    *,
    sov_series: list[dict] | None = None,
) -> dict:
    """ATT-5.1.2 — probabilistic Direct/(not set) heuristic with CI; UNVALIDATED."""
    if not sessions:
        return {
            "status": "INSUFFICIENT_DATA",
            "series": [],
            "ci_lower": None,
            "ci_upper": None,
            "n": 0,
            "method": "heuristic_v1",
            "weights_status": WEIGHTS_STATUS,
            "label": "estimated_dark_ai_not_measured",
            "reason": "no sessions for dark-traffic estimate",
        }

    candidates = []
    for row in sessions:
        channel = (row.get("channel") or "").lower()
        medium = (row.get("medium") or "").lower()
        if channel in ("direct", "(none)") or medium in ("(none)", "(not set)", "none", ""):
            candidates.append(row)

    n = len(candidates)
    if n < 5:
        return {
            "status": "INSUFFICIENT_DATA",
            "series": [],
            "ci_lower": None,
            "ci_upper": None,
            "n": n,
            "method": "heuristic_v1",
            "weights_status": WEIGHTS_STATUS,
            "label": "estimated_dark_ai_not_measured",
            "reason": "too few Direct/(not set) sessions for interval",
        }

    # Features (a)–(e) simplified: landing has brand/SOV-related path, hour, new user, etc.
    scores = []
    by_day: dict[str, list[float]] = defaultdict(list)
    sov_by_day = {
        str(r.get("date")): float(r.get("value") or r.get("sov") or 0)
        for r in (sov_series or [])
    }
    for row in candidates:
        score = 0.15  # base prior — UNVALIDATED
        landing = (row.get("landing_page") or "").lower()
        if any(x in landing for x in ("hbot", "hyperbaric", "brand")):
            score += 0.25
        if row.get("new_user"):
            score += 0.1
        day = str(row.get("date") or "")
        if day and sov_by_day.get(day, 0) >= 0.2:
            score += 0.2
        if (row.get("device") or "").lower() == "desktop":
            score += 0.05
        score = min(0.95, score)
        scores.append(score)
        if day:
            by_day[day].append(score)

    mean = sum(scores) / len(scores)
    # Analytic Wald-ish interval on mean probability (document method).
    var = sum((s - mean) ** 2 for s in scores) / max(1, len(scores) - 1)
    se = (var / len(scores)) ** 0.5
    z = 1.96
    ci_lo = max(0.0, mean - z * se)
    ci_hi = min(1.0, mean + z * se)
    series = [
        {
            "date": d,
            "estimated_dark_ai_rate": sum(by_day[d]) / len(by_day[d]),
            "n": len(by_day[d]),
        }
        for d in sorted(by_day)
    ]
    return {
        "status": "OK",
        "series": series,
        "value": mean,
        "ci_lower": ci_lo,
        "ci_upper": ci_hi,
        "n": n,
        "method": "heuristic_v1_wald_mean",
        "weights_status": WEIGHTS_STATUS,
        "label": "estimated_dark_ai_not_measured",
        "reason": "probabilistic heuristic — must not be labelled measured AI traffic",
    }


def branded_search_inflation(gsc_branded: list[dict], sov_series: list[dict]) -> dict:
    """ATT-5.1.3 — flag excess branded search lagged after SOV rise; co-occurrence only."""
    if not gsc_branded or not sov_series:
        return {
            "status": "INSUFFICIENT_DATA",
            "flags": [],
            "reason": "need both GSC branded and SOV series",
        }
    sov_sorted = sorted(sov_series, key=lambda r: str(r.get("date")))
    gsc_by = {str(r.get("date")): float(r.get("clicks") or r.get("value") or 0) for r in gsc_branded}
    flags = []
    for i in range(1, len(sov_sorted)):
        prev = float(sov_sorted[i - 1].get("value") or sov_sorted[i - 1].get("sov") or 0)
        cur = float(sov_sorted[i].get("value") or sov_sorted[i].get("sov") or 0)
        if cur - prev < 0.05:
            continue
        rise_day = str(sov_sorted[i].get("date"))
        # Look 7–14 days ahead for branded excess vs prior week mean
        # (date strings ISO — lexical lag only when dates are daily ISO)
        for gdate, clicks in gsc_by.items():
            if gdate <= rise_day:
                continue
            # crude: any later branded spike co-occurrence
            prior_vals = [v for d, v in gsc_by.items() if d < gdate]
            if not prior_vals:
                continue
            baseline = sum(prior_vals) / len(prior_vals)
            if clicks > baseline * 1.25:
                flags.append(
                    {
                        "sov_rise_date": rise_day,
                        "branded_date": gdate,
                        "label": "probable AI-influenced branded search",
                        "language": "co-occurrence only until Granger passes",
                    }
                )
                break
    return {
        "status": "OK" if flags else "NONE_FLAGGED",
        "flags": flags,
        "reason": "co-occurrence language only — not causal until Granger MEASURED",
    }
