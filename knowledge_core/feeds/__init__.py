"""
feeds/ -- SPEC_KC_FEEDS package root, Phase 2 Living Knowledge Core.

The fleet-wide Learning Feeds service: four domain subscribers, one per
owner, generalizing the Krebs threat-intel pattern (ingest, extract,
store, search) that Sentinel hardened on 2026-08-01
(test_sentinel_krebs_feed.py), gated on fetch by Jayden's hardened
crawler-policy check (test_crawler_intel.py), per
ORLOK_FLEET_USE_PROTOCOL.md's SPEC_KC_FEEDS row.

Owners: Sentinel (security), Oluwole (regulatory, plus reachability
verification across all four feeds), Amaya (design), Bink (search and
GEO), coordinated by Celestina on the shared seam.

Every subscriber implements the shared contract in
knowledge_core.feeds.common.subscriber.BaseSubscriber:
  - a schedule, recorded as data, not inferred from a running process
  - a fetch step per source, gated by the crawler-policy check and the
    reachability precondition (section 3.6)
  - a dedup step on a stable key, before note generation
  - a secret-scan gate before store, refusing loudly on a hit
  - a note-generation step, writing a draft note through Foundation's
    write_note()/link() seams, status draft, never active
  - an alert step, per feed threshold, that never changes the note's
    status

This module is the registry: FEEDS maps each feed's name to its
subscriber class, and ingest_all()/search() are the fleet-wide entry
points a caller (or the future dashboard surface) uses without importing
each domain subpackage directly.
"""

from knowledge_core.feeds.security import SecuritySubscriber
from knowledge_core.feeds.regulatory import RegulatorySubscriber
from knowledge_core.feeds.design import DesignSubscriber
from knowledge_core.feeds.search import SearchGeoSubscriber

FEEDS = {
    "Security": SecuritySubscriber,
    "Regulatory": RegulatorySubscriber,
    "Design": DesignSubscriber,
    "Search and GEO": SearchGeoSubscriber,
}


def build_subscribers(store, targets=None):
    """Construct one subscriber instance per feed, sharing one GraphStore."""
    targets = targets or {}
    return {name: cls(store, targets=targets.get(name, {})) for name, cls in FEEDS.items()}


def search_notes(store, feed=None, keyword=None):
    """
    Fleet-wide search over draft feed-item notes, generalizing Sentinel's
    FeedStore.search(keyword=..., source=...) contract across all four
    feeds. Filters by feed name (refs.feed) and/or a case-insensitive
    keyword match against the note body.

    Named search_notes, not search, so this module-level function never
    shadows the knowledge_core.feeds.search subpackage (the Search and
    GEO feed) on the feeds package's own namespace.
    """
    results = []
    for note in store.notes.values():
        if note.get("type") != "feed-item":
            continue
        refs = note.get("refs") or {}
        if feed and refs.get("feed") != feed:
            continue
        if keyword and keyword.lower() not in (note.get("body") or "").lower():
            continue
        results.append(note)
    return results
