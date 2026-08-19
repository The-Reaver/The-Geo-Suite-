# SPEC: SPEC_CCC_SALES_DISCOVERY (prospect source)
"""Prospect discovery source — turns a location+type query into candidate
provider records for the lead scorer.

The gap this closes (GEO Brain Trust 2026-08-08, open item 6, "Prospecting does
not exist"): the pipeline could already *rank* a hand-entered provider list
(`lead_scorer.rank_leads`, exposed at POST /sales/rank-leads) but nothing
*produced* that list. There was no directory search, no map pull, no scrape.
This module is that missing source.

Honesty invariant (the fleet's "read a+c, never b"): a directory / map pull
yields only the *discoverable* facts — name, street, locality, region, domain,
telephone, category, rating, review count. It CANNOT know a clinic's ownership,
payment model, decision-maker, or medical indications; those are established on
a confirmed call, not scraped. So a candidate carries a `discovered` block of
real facts and leaves the lead scorer's undiscoverable required keys ABSENT.
The lead therefore scores INCOMPLETE until a human enriches it, rather than
inventing a fit/opportunity number from thin air. Discovery finds prospects; it
does not qualify them.

Offline-safe and injectable: pass `rows=[...]` to `discover()` to run the whole
pipeline on a fixture with no network — the shape the test battery uses. A real
live adapter (`http_places_source`) is gated behind GEO_PLACES_API_KEY and
returns an honest DISABLED status when unconfigured, mirroring the
GEO_USE_SUPABASE_* gate pattern used elsewhere in this codebase.
"""
from __future__ import annotations

import os
import re
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

from .lead_scorer import rank_leads, score_lead

# --- normalized place schema --------------------------------------------------
# A source adapter's one job is to map its provider's response onto these keys.
# Everything downstream reads only these, so swapping Google Places for OSM or a
# CSV import never touches the pipeline.
_DISCOVERABLE_KEYS = (
    "name", "street", "locality", "region", "postal_code", "country",
    "domain", "website", "telephone", "categories", "rating",
    "review_count", "place_id",
)

# Required by lead_scorer but NOT discoverable from a directory/map pull. Named
# here so the candidate can tell a salesperson exactly what to confirm on the
# call, and so we never silently invent them.
NEEDS_CONFIRMATION = ("ownership", "decision_maker", "payment_model", "indications")

# Category keyword -> a practice_type the lead scorer weights. This is an
# *inference from a discovered fact* (the listing's own category text), so it is
# returned as `inferred_practice_type` for the UI to prefill-and-confirm. It is
# deliberately NOT fed into the scored provider record: an unconfirmed guess must
# not move a fit score. See discover_and_rank.
_CATEGORY_TO_TYPE = (
    ("chiropract", "chiropractic"),
    ("integrative", "integrative med"),
    ("functional med", "integrative med"),
    ("naturopath", "integrative med"),
    ("sports medicine", "sports/pain"),
    ("pain", "sports/pain"),
    ("physical therap", "sports/pain"),
    ("wellness", "wellness"),
    ("spa", "wellness"),
    ("med spa", "wellness"),
    ("veterin", "veterinary"),
    ("animal", "veterinary"),
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _domain_from(raw: dict) -> str:
    """Prefer an explicit domain, else derive it from a website URL. Never a
    fabricated guess: returns '' when neither is present."""
    domain = _clean(raw.get("domain"))
    if domain:
        return domain.lower().lstrip("www.")
    website = _clean(raw.get("website"))
    if not website:
        return ""
    if "://" not in website:
        website = "https://" + website
    host = urlparse(website).hostname or ""
    return host.lower().lstrip("www.") if host.startswith("www.") else host.lower()


def _infer_practice_type(categories: Iterable[str]) -> str:
    text = " ".join(_clean(c).lower() for c in (categories or []))
    for needle, ptype in _CATEGORY_TO_TYPE:
        if needle in text:
            return ptype
    return ""


def _dedupe_key(candidate: dict) -> str:
    d = candidate["discovered"]
    place_id = _clean(d.get("place_id"))
    if place_id:
        return "pid:" + place_id.lower()
    domain = _clean(d.get("domain"))
    if domain:
        return "dom:" + domain
    name = re.sub(r"\s+", " ", _clean(d.get("name")).lower())
    loc = _clean(d.get("locality")).lower()
    return f"nl:{name}|{loc}"


def normalize_place(raw: dict) -> dict:
    """Map one raw place row onto a candidate: the discovered facts, the honest
    list of what still needs confirming, and an inferred (unconfirmed) practice
    type for the UI. Never raises on a malformed row."""
    raw = raw if isinstance(raw, dict) else {}
    categories = raw.get("categories")
    if isinstance(categories, str):
        categories = [c.strip() for c in categories.split(",") if c.strip()]
    elif not isinstance(categories, list):
        categories = []

    discovered: dict[str, Any] = {
        "name": _clean(raw.get("name")),
        "street": _clean(raw.get("street")),
        "locality": _clean(raw.get("locality") or raw.get("city")),
        "region": _clean(raw.get("region") or raw.get("state")),
        "postal_code": _clean(raw.get("postal_code")),
        "country": _clean(raw.get("country")),
        "domain": _domain_from(raw),
        "website": _clean(raw.get("website")),
        "telephone": _clean(raw.get("telephone") or raw.get("phone")),
        "categories": categories,
        "rating": raw.get("rating"),
        "review_count": raw.get("review_count"),
        "place_id": _clean(raw.get("place_id")),
        "source": _clean(raw.get("source")) or "unknown",
    }

    return {
        "discovered": discovered,
        "inferred_practice_type": _infer_practice_type(categories),
        "needs_confirmation": list(NEEDS_CONFIRMATION),
        "auditable": bool(discovered["domain"] or discovered["website"]),
    }


def _to_provider_record(candidate: dict) -> dict:
    """The partial provider dict handed to the lead scorer. Carries ONLY
    confirmed-discoverable keys plus name; the four NEEDS_CONFIRMATION keys are
    intentionally absent so the scorer returns INCOMPLETE rather than a number
    built on guesses."""
    d = candidate["discovered"]
    return {
        "name": d.get("name"),
        # discovered context the scorer ignores today but downstream panels use
        "domain": d.get("domain"),
        "locality": d.get("locality"),
        "region": d.get("region"),
        "telephone": d.get("telephone"),
    }


# --- sources ------------------------------------------------------------------

def _places_enabled() -> bool:
    return bool(os.getenv("GEO_PLACES_API_KEY") and os.getenv("GEO_PLACES_API_URL"))


def http_places_source(query: dict) -> dict:
    """Live directory/map adapter, gated behind GEO_PLACES_API_KEY +
    GEO_PLACES_API_URL. Provider-agnostic on purpose: the operator points
    GEO_PLACES_API_URL at whichever places API they license (Google Places,
    Foursquare, an internal directory) and this maps a standard response shape.
    Returns an honest {"status": "DISABLED", ...} when unconfigured, so the
    battery and any un-provisioned environment never touch the network.

    Kept import-light: httpx is imported inside the enabled branch so the module
    imports with no network stack present.
    """
    if not _places_enabled():
        return {
            "status": "DISABLED",
            "rows": [],
            "reason": (
                "live prospecting source not configured; set GEO_PLACES_API_KEY "
                "and GEO_PLACES_API_URL to enable directory/map pulls"
            ),
        }

    api_url = os.environ["GEO_PLACES_API_URL"]
    if urlparse(api_url).scheme not in ("http", "https"):
        return {"status": "ERROR", "rows": [], "reason": "GEO_PLACES_API_URL must be http(s)"}

    import httpx  # local import: keeps the module offline-importable

    params = {
        "key": os.environ["GEO_PLACES_API_KEY"],
        "type": _clean(query.get("business_type")),
        "location": ", ".join(
            p for p in (_clean(query.get("locality")), _clean(query.get("region"))) if p
        ),
        "limit": int(query.get("limit") or 20),
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(api_url, params=params)
            resp.raise_for_status()
            body = resp.json()
    except Exception as exc:  # noqa: BLE001 - surfaced honestly, never fabricated
        return {"status": "ERROR", "rows": [], "reason": f"places lookup failed: {exc}"}

    rows = body.get("results") if isinstance(body, dict) else body
    rows = rows if isinstance(rows, list) else []
    for r in rows:
        if isinstance(r, dict):
            r.setdefault("source", "http_places")
    return {"status": "OK", "rows": rows, "reason": "live_pull"}


def discover(
    query: dict,
    *,
    rows: list[dict] | None = None,
    source: Callable[[dict], dict] | None = None,
) -> dict:
    """Run a prospect discovery. Resolution order for the raw rows:
      1. `rows` if given (the injectable, offline path the battery uses),
      2. else `source(query)` if given,
      3. else the configured live http_places_source.
    Normalizes, dedupes, and returns candidates plus an honest source status.
    Never fabricates prospects: an unconfigured, empty, or failed source yields
    zero candidates and says why.
    """
    query = query if isinstance(query, dict) else {}
    limit = int(query.get("limit") or 20)

    if rows is not None:
        raw_rows, status, reason = list(rows), "OK", "injected_rows"
    else:
        src = source or http_places_source
        result = src(query)
        raw_rows = list(result.get("rows") or [])
        status = result.get("status", "OK")
        reason = result.get("reason", "")

    seen: set[str] = set()
    candidates: list[dict] = []
    for raw in raw_rows:
        cand = normalize_place(raw)
        if not cand["discovered"]["name"]:
            continue  # a nameless listing is not a usable prospect
        key = _dedupe_key(cand)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(cand)
        if len(candidates) >= limit:
            break

    return {
        "status": status if candidates or status != "OK" else "EMPTY",
        "reason": reason or ("no listings matched the query" if not candidates else "discovered"),
        "query": {
            "business_type": _clean(query.get("business_type")),
            "locality": _clean(query.get("locality")),
            "region": _clean(query.get("region")),
            "limit": limit,
        },
        "count": len(candidates),
        "candidates": candidates,
    }


def discover_and_rank(
    query: dict,
    *,
    rows: list[dict] | None = None,
    source: Callable[[dict], dict] | None = None,
    audits: dict | None = None,
) -> dict:
    """Discover prospects and attach the lead scorer's verdict to each.

    Freshly-discovered candidates score INCOMPLETE by design (ownership,
    payment model, decision-maker and indications are not discoverable) — that
    is the honest state, not a bug. `audits` may map a candidate name to a
    measured {accessibility_gap, visibility_gap} from the existing audit engine;
    those raise the opportunity score even while fit stays provisional.
    """
    found = discover(query, rows=rows, source=source)
    audits = audits if isinstance(audits, dict) else {}

    ranked: list[dict] = []
    for cand in found["candidates"]:
        record = _to_provider_record(cand)
        name = record.get("name")
        verdict = score_lead(record, audit=audits.get(name))
        ranked.append({
            "discovered": cand["discovered"],
            "inferred_practice_type": cand["inferred_practice_type"],
            "needs_confirmation": cand["needs_confirmation"],
            "auditable": cand["auditable"],
            "score": verdict,
        })

    # INCOMPLETE first is correct here: those are the ones a human must action
    # next. rank_leads sorts qualified leads; discovery output is a work queue.
    ranked.sort(key=lambda r: (r["score"]["tier"] != "INCOMPLETE", -r["score"]["priority"]))

    incomplete = sum(1 for r in ranked if r["score"]["tier"] == "INCOMPLETE")
    return {
        "status": found["status"],
        "reason": found["reason"],
        "query": found["query"],
        "count": found["count"],
        "needs_confirmation_count": incomplete,
        "candidates": ranked,
        "note": (
            "Discovered prospects list INCOMPLETE until ownership, payment model, "
            "decision-maker and indications are confirmed on the call. Discovery "
            "supplies the list and the discoverable facts, never the qualification."
        ),
    }
