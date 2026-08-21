"""
Facts persistence — load confirmed BusinessFacts for a site_id.

This is the layer `run_ai_readiness_audit(site_id)` needed. It turns the stored
records for a site into the `BusinessFacts` model the site engine consumes.

Data model (from `supabase/migrations/…_init_schema.sql`):
  - `sites`          : id, client_id, domain, ...
  - `clients`        : id, business_name, nap (JSONB), ...
  - `business_facts` : client_id, field_name, field_value, source, confirmed, ...
    An EAV table. One confirmed row per fact key.

THE INVARIANT (fleet doctrine "read a+c, never b"): **only confirmed facts feed
generation.** This layer filters `confirmed = true`. An unconfirmed fact does not
exist for the purposes of building or auditing a site. If required facts are
missing after the confirmed-only filter, loading fails loudly and names what is
missing — it never substitutes a default and publishes on a guess.

The EAV convention (field_name -> BusinessFacts field):
  scalars (field_value is the plain string):
    subtype, street, locality, region, postal_code, country, telephone, email,
    last_updated, tagline
  JSON-encoded (field_value is a JSON string):
    services       -> [{"name": ..., "description": ..., "faqs": [{"question": ..., "answer": ...}, ...]}, ...]
    faqs           -> [{"question": ..., "answer": ...}, ...]
    service_areas  -> ["Portland", ...]
    credentials    -> ["ADA membership", ...]
    same_as        -> ["https://g.page/...", ...]
    hours          -> ["Mon-Fri 8:00-17:00", ...]
    rating         -> {"value": 4.9, "count": 218}
  from clients:  business_name (column), nap (JSONB) as NAP fallback
  from sites:    domain

The pure mapper (`map_to_business_facts`) takes plain dict rows and is fully
unit-testable without a database. `SupabaseFactsRepository` fetches the rows and
calls it. `InMemoryFactsRepository` backs tests and local development.
"""
from __future__ import annotations

import json
from typing import Any, Protocol

from ..schemas.site_schemas import BusinessFacts, Service, FAQ, Rating

# Fact keys whose stored value is JSON rather than a plain string.
_JSON_KEYS = {"services", "faqs", "service_areas", "credentials", "same_as", "hours", "rating"}

# NAP JSONB key aliases -> BusinessFacts field. Different intake sources spell
# these differently; accept the common variants.
_NAP_ALIASES = {
    "street": ("street", "streetAddress", "street_address", "address1", "line1"),
    "locality": ("locality", "addressLocality", "city", "town"),
    "region": ("region", "addressRegion", "state", "province"),
    "postal_code": ("postal_code", "postalCode", "zip", "zip_code", "postcode"),
    "country": ("country", "addressCountry", "country_code"),
    "telephone": ("telephone", "phone", "phone_number", "tel"),
}

_REQUIRED = ("business_name", "subtype", "street", "locality", "region",
             "postal_code", "telephone", "domain")


class FactsNotConfirmed(Exception):
    """Required facts are missing or unconfirmed; a site cannot be built."""


def _confirmed(fact_rows: list[dict]) -> dict[str, Any]:
    """Collapse confirmed EAV rows into a {field_name: value} dict, decoding JSON
    keys. Unconfirmed rows are dropped — they do not exist for generation."""
    out: dict[str, Any] = {}
    for row in fact_rows or []:
        if not row.get("confirmed", False):
            continue
        name = row.get("field_name")
        value = row.get("field_value")
        if name is None:
            continue
        if name in _JSON_KEYS and isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                # A malformed structured fact is treated as absent, not guessed.
                continue
        out[name] = value
    return out


def _nap_value(nap: dict, field: str) -> str:
    for alias in _NAP_ALIASES.get(field, ()):
        v = nap.get(alias)
        if v:
            return str(v)
    return ""

def business_facts_to_rows(client_id: Any, facts: BusinessFacts, *, source: str = "intake", confirmed: bool = False) -> list[dict]:
    """Map a BusinessFacts object back to a list of EAV dict rows for storage.
    business_name and NAP live on the clients row, NOT business_facts — do not emit rows for them here."""
    rows: list[dict] = []
    skip_keys = {"business_name", "domain", "street", "locality", "region", "postal_code", "country", "telephone"}
    
    fact_dict = facts.model_dump() if hasattr(facts, "model_dump") else (facts.dict() if hasattr(facts, "dict") else vars(facts))
    
    for k, v in fact_dict.items():
        if k in skip_keys:
            continue
            
        if v is None or v == "" or v == []:
            continue
            
        if k in _JSON_KEYS:
            field_value = json.dumps(v)
        else:
            field_value = str(v)
            
        rows.append({
            "client_id": str(client_id),
            "field_name": k,
            "field_value": field_value,
            "source": source,
            "confirmed": confirmed
        })
    return rows

def map_to_business_facts(site: dict, client: dict, fact_rows: list[dict]) -> BusinessFacts:
    """Pure mapper: stored rows -> BusinessFacts. Confirmed facts only.

    Raises FactsNotConfirmed if any required field is missing after filtering, so
    a site is never generated from an incomplete or unconfirmed record.
    """
    facts = _confirmed(fact_rows)
    nap = client.get("nap") or {}
    if not isinstance(nap, dict):
        nap = {}

    def pick(field: str, *, nap_fallback: bool = False) -> str:
        v = facts.get(field)
        if v:
            return str(v)
        if nap_fallback:
            return _nap_value(nap, field)
        return ""

    # 2026-08-21, Opus 5 review of §6 sub-slice 2b: this rebuild dropped
    # per-service faqs entirely -- the write side (BusinessFacts.model_dump())
    # already persists them, so a real business's confirmed FAQ content was
    # silently discarded on every reload through this repository, making
    # the whole feature unreachable from this real persisted-facts path.
    # Reproduced directly: stored with a real faqs list, reloaded with
    # faqs == []. Same shape as this repo's own documented "faqs" EAV
    # field just above, applied per-service instead of business-wide.
    services = [
        Service(
            name=s.get("name", ""), description=s.get("description", ""),
            faqs=[FAQ(question=q.get("question", ""), answer=q.get("answer", ""))
                  for q in (s.get("faqs") or []) if isinstance(q, dict) and q.get("question")],
        )
        for s in facts.get("services", []) if isinstance(s, dict) and s.get("name")
    ]
    faqs = [FAQ(question=q.get("question", ""), answer=q.get("answer", ""))
            for q in facts.get("faqs", []) if isinstance(q, dict) and q.get("question")]
    rating = None
    r = facts.get("rating")
    if isinstance(r, dict) and r.get("value") is not None and r.get("count") is not None:
        rating = Rating(value=float(r["value"]), count=int(r["count"]))

    candidate = dict(
        business_name=str(client.get("business_name") or "").strip(),
        subtype=pick("subtype"),
        street=pick("street", nap_fallback=True),
        locality=pick("locality", nap_fallback=True),
        region=pick("region", nap_fallback=True),
        postal_code=pick("postal_code", nap_fallback=True),
        country=pick("country", nap_fallback=True) or "US",
        telephone=pick("telephone", nap_fallback=True),
        email=facts.get("email") or None,
        domain=str(site.get("domain") or "").strip(),
        hours=list(facts.get("hours", [])),
        service_areas=list(facts.get("service_areas", [])),
        services=services,
        credentials=list(facts.get("credentials", [])),
        faqs=faqs,
        same_as=list(facts.get("same_as", [])),
        rating=rating,
        last_updated=str(facts.get("last_updated") or ""),
        tagline=facts.get("tagline") or None,
    )

    missing = [k for k in _REQUIRED if not candidate.get(k)]
    if missing:
        raise FactsNotConfirmed(
            "cannot build site for site_id=" + str(site.get("id")) + ": missing or "
            "unconfirmed required fact(s): " + ", ".join(missing) + ". Confirm these "
            "facts before generating; the engine does not guess."
        )
    return BusinessFacts(**candidate)


# =============================================================================
# Repository interface + implementations
# =============================================================================


class FactsRepository(Protocol):
    def load_business_facts(self, site_id: Any) -> BusinessFacts: ...
    def save_business_facts(self, client_id: Any, facts: BusinessFacts, *, source: str = "intake", confirmed: bool = False) -> None: ...
    def confirm_facts(self, client_id: Any, field_names: list[str] | None = None) -> None: ...


class InMemoryFactsRepository:
    """Test/local repository. Seed with dict rows shaped like the DB tables."""

    def __init__(self, sites: dict, clients: dict, business_facts: dict):
        # sites: {site_id: site_row}; clients: {client_id: client_row};
        # business_facts: {client_id: [fact_row, ...]}
        self._sites = sites
        self._clients = clients
        self._facts = business_facts

    def save_business_facts(self, client_id: Any, facts: BusinessFacts, *, source: str = "intake", confirmed: bool = False) -> None:
        rows = business_facts_to_rows(client_id, facts, source=source, confirmed=confirmed)
        cid = str(client_id)
        if cid not in self._facts:
            self._facts[cid] = []
        self._facts[cid].extend(rows)

    def confirm_facts(self, client_id: Any, field_names: list[str] | None = None) -> None:
        cid = str(client_id)
        if cid not in self._facts:
            return
        for row in self._facts[cid]:
            if field_names is None or row.get("field_name") in field_names:
                row["confirmed"] = True

    def load_business_facts(self, site_id: Any) -> BusinessFacts:
        site = self._sites.get(str(site_id)) or self._sites.get(site_id)
        if not site:
            raise FactsNotConfirmed(f"no site record for site_id={site_id}")
        client_id = site.get("client_id")
        client = self._clients.get(str(client_id)) or self._clients.get(client_id) or {}
        rows = self._facts.get(str(client_id)) or self._facts.get(client_id) or []
        return map_to_business_facts(site, client, rows)


class SupabaseFactsRepository:
    """Production repository. Reads sites, clients, and confirmed business_facts
    from Supabase, then maps to BusinessFacts. Imports the client lazily so this
    module loads without the dependency; misconfiguration fails loudly at call
    time rather than returning a fabricated record."""

    def __init__(self, client: Any = None):
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from supabase import create_client
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "supabase client not installed; install supabase-py or inject a "
                "client. This layer refuses to fabricate facts."
            ) from exc
        from ..core.config import settings
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise RuntimeError(
                "SUPABASE_URL / SUPABASE_KEY are not configured; cannot load facts."
            )
        self._client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        return self._client

    def save_business_facts(self, client_id: Any, facts: BusinessFacts, *, source: str = "intake", confirmed: bool = False) -> None:
        rows = business_facts_to_rows(client_id, facts, source=source, confirmed=confirmed)
        if not rows:
            return
        db = self._get_client()
        db.table("business_facts").insert(rows).execute()

    def confirm_facts(self, client_id: Any, field_names: list[str] | None = None) -> None:
        db = self._get_client()
        query = db.table("business_facts").update({"confirmed": True}).eq("client_id", str(client_id))
        if field_names is not None:
            query = query.in_("field_name", field_names)
        query.execute()

    def load_business_facts(self, site_id: Any) -> BusinessFacts:
        db = self._get_client()
        site_res = db.table("sites").select("*").eq("id", str(site_id)).limit(1).execute()
        sites = getattr(site_res, "data", None) or []
        if not sites:
            raise FactsNotConfirmed(f"no site record for site_id={site_id}")
        site = sites[0]
        client_id = site["client_id"]

        client_res = db.table("clients").select("*").eq("id", str(client_id)).limit(1).execute()
        clients = getattr(client_res, "data", None) or []
        client = clients[0] if clients else {}

        # Only confirmed facts. The filter is the invariant, enforced at the query.
        facts_res = (db.table("business_facts").select("*")
                     .eq("client_id", str(client_id)).eq("confirmed", True).execute())
        fact_rows = getattr(facts_res, "data", None) or []
        return map_to_business_facts(site, client, fact_rows)
