# SPEC: SPEC_CCC_M1_INGESTION
"""Ecosystem crawl outcomes — BLOCKED → NOT_CHECKED for M4, never ABSENT."""
from __future__ import annotations

from ..platform_registry import DEFAULT_HBOT_PLATFORM_IDS
from .gateways.crawl_gateway import fetch_page


def crawl_platforms(
    platforms: list[str] | None = None,
    *,
    fakes: dict | None = None,
) -> dict:
    tracked = list(platforms or DEFAULT_HBOT_PLATFORM_IDS)
    fakes = fakes or {}
    rows = []
    checked = 0
    for platform in tracked:
        fake = fakes.get(platform)
        env = fetch_page(f"https://example.invalid/{platform}", fake=fake)
        status = env.get("status")
        if status == "OK":
            checked += 1
            rows.append({
                "platform": platform,
                "status": "PRESENT" if (env.get("data") or {}).get("exists", True) else "ABSENT",
                "exists": (env.get("data") or {}).get("exists", True),
            })
        elif status in ("BLOCKED", "RATE_LIMITED", "TIMEOUT", "VENDOR_ERROR", "AUTH_FAILED"):
            rows.append({
                "platform": platform,
                "status": "NOT_CHECKED",
                "check_failed": True,
                "reason": f"crawl {status}",
            })
        elif status == "EMPTY":
            checked += 1
            rows.append({
                "platform": platform,
                "status": "ABSENT",
                "exists": False,
                "reason": "empty successful check",
            })
        else:
            rows.append({
                "platform": platform,
                "status": "NOT_CHECKED",
                "check_failed": True,
                "reason": f"crawl {status}",
            })
    return {
        "platforms_attempted": len(tracked),
        "platforms_checked": checked,
        "coverage": f"checked {checked} of {len(tracked)} tracked platforms",
        "listings": rows,
    }
