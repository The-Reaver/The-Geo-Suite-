"""
Regulatory feed, owner Oluwole. The Federal Register, Congress.gov and
the tracked state legislatures, FDA, FTC, OCR, W3C, and the EU's
official publication channels, per SPEC_KC_FEEDS section 3.3.

Dedup key: the docket or bill identifier, otherwise the canonical
publication URL. Touch links: touches to the prospect and client notes
whose jurisdiction or sector the filing names, carrying jurisdiction,
effective date, and citation fields for SPEC_KC_REGWATCH to read later.
Alert threshold: any final rule, any bill that passes a chamber, or any
enforcement action alerts. A proposed rule or an introduced bill logs as
a draft note without an alert.
"""

from knowledge_core.feeds.common.subscriber import BaseSubscriber
from knowledge_core.feeds.regulatory.fixtures import SOURCES, CORE_ITEMS

SCHEDULE = {
    "feed": "Regulatory",
    "cadence": "cron",
    "value": "0 */6 * * *",
    "note": "poll every 6 hours across Federal Register and Congress.gov",
}

ALERTABLE_STATUSES = frozenset({"final_rule", "passed_chamber", "enforcement_action"})


class RegulatorySubscriber(BaseSubscriber):
    name = "Regulatory"
    SCHEDULE = SCHEDULE
    SOURCES = SOURCES
    DEFAULT_ITEMS = CORE_ITEMS
    TOUCH_FIELDS = [("touches", "prospect_key")]

    def extract(self, raw_item):
        required = ("source", "id", "url", "title", "status", "published", "jurisdiction")
        for field in required:
            if field not in raw_item:
                raise ValueError(
                    "extract: missing required field '%s' in raw item %r" % (field, raw_item)
                )
        return {
            "docket_id": raw_item.get("docket_id"),
            "title": raw_item["title"],
            "body": raw_item["title"],
            "status": raw_item["status"],
            "source": raw_item["source"],
            "url": raw_item["url"],
            "published": raw_item["published"],
            "jurisdiction": raw_item["jurisdiction"],
            "effective_date": raw_item.get("effective_date", ""),
            "prospect_key": raw_item.get("prospect_key"),
        }

    def dedup_key(self, extracted):
        return extracted.get("docket_id") or extracted["url"]

    def is_alertable(self, extracted):
        return extracted["status"] in ALERTABLE_STATUSES

    def alert_reason(self, extracted):
        return "regulatory item %s has status '%s', jurisdiction '%s', meets alert threshold" % (
            extracted.get("docket_id") or extracted["url"], extracted["status"], extracted["jurisdiction"],
        )
