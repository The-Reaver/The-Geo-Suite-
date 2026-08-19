"""
Fixture data for the Regulatory feed, owner Oluwole. Self-contained, no
network access. Federal Register, Congress.gov and tracked state
legislatures, FDA, FTC, OCR, W3C, and the EU's official publication
channels, per SPEC_KC_FEEDS section 3.3.
"""

ROBOTS_ALLOW_ALL = """\
User-agent: *
Disallow:
Sitemap: https://example-regulatory-source.test/sitemap.xml
"""

SOURCES = [
    {
        "name": "FederalRegister",
        "base_url": "https://www.federalregister.gov/api/v1/documents.json",
        "robots_txt": ROBOTS_ALLOW_ALL,
        "bot_name": "STAGRegulatoryBot",
        "path": "/api/v1/documents.json",
        "verified": True,
        "robots_allowance": "published API, no robots.txt restriction",
        "rate_limit": "1 request / 10 minutes",
        "access_method": "api",
        "checked_date": "2026-07-30",
        "checked_by": "Oluwole",
    },
    {
        "name": "CongressGov",
        "base_url": "https://www.congress.gov/rss/most-viewed-bills.xml",
        "robots_txt": ROBOTS_ALLOW_ALL,
        "bot_name": "STAGRegulatoryBot",
        "path": "/rss/most-viewed-bills.xml",
        "verified": True,
        "robots_allowance": "public RSS feed, no robots.txt restriction",
        "rate_limit": "1 request / 15 minutes",
        "access_method": "rss",
        "checked_date": "2026-07-30",
        "checked_by": "Oluwole",
    },
]

SEED_TARGETS = {
    "prospect:california-retailer": {
        "type": "prospect",
        "body": "A California-headquartered retail prospect in the CCPA/CPRA jurisdiction.",
        "source": "https://internal.example/crm/california-retailer",
    },
    "prospect:federal-healthcare-client": {
        "type": "prospect",
        "body": "A HIPAA-covered federal-jurisdiction healthcare client.",
        "source": "https://internal.example/crm/federal-healthcare-client",
    },
}

CORE_ITEMS = {
    "FederalRegister": [
        {
            "source": "FederalRegister",
            "id": "FR-2026-14501",
            "docket_id": "FR-2026-14501",
            "url": "https://www.federalregister.gov/documents/2026/07/30/2026-14501",
            "title": "FTC Final Rule on Automated Decision Disclosures",
            "status": "final_rule",
            "jurisdiction": "US-Federal",
            "effective_date": "2026-10-01",
            "published": "2026-07-30",
            "prospect_key": "prospect:federal-healthcare-client",
        },
        {
            "source": "FederalRegister",
            "id": "FR-2026-14700",
            "docket_id": "FR-2026-14700",
            "url": "https://www.federalregister.gov/documents/2026/07/28/2026-14700",
            "title": "OCR Proposed Rule on Health Data Portability",
            "status": "proposed_rule",
            "jurisdiction": "US-Federal",
            "effective_date": "",
            "published": "2026-07-28",
            "prospect_key": "prospect:federal-healthcare-client",
        },
    ],
    "CongressGov": [
        {
            # exact re-poll of FR-2026-14501 by docket id: must dedupe
            "source": "CongressGov",
            "id": "FR-2026-14501",
            "docket_id": "FR-2026-14501",
            "url": "https://www.congress.gov/mirror/2026-14501",
            "title": "FTC Final Rule on Automated Decision Disclosures (mirrored)",
            "status": "final_rule",
            "jurisdiction": "US-Federal",
            "effective_date": "2026-10-01",
            "published": "2026-07-30",
            "prospect_key": "prospect:federal-healthcare-client",
        },
        {
            "source": "CongressGov",
            "id": "CA-SB-2044",
            "docket_id": "CA-SB-2044",
            "url": "https://www.congress.gov/bill/ca-sb-2044",
            "title": "California SB-2044 passes the Senate",
            "status": "passed_chamber",
            "jurisdiction": "California",
            "effective_date": "",
            "published": "2026-07-27",
            "prospect_key": "prospect:california-retailer",
        },
        {
            "source": "CongressGov",
            "id": "CA-AB-3399",
            "docket_id": "CA-AB-3399",
            "url": "https://www.congress.gov/bill/ca-ab-3399",
            "title": "California AB-3399 introduced",
            "status": "introduced_bill",
            "jurisdiction": "California",
            "effective_date": "",
            "published": "2026-07-20",
            "prospect_key": "prospect:california-retailer",
        },
    ],
}

# Planted, obviously-fake secret in the body/title, to prove the shared
# secret-scan gate applies to this feed too, not just Security's.
SECRET_ITEM = {
    "source": "FederalRegister",
    "id": "FR-2026-15200",
    "docket_id": "FR-2026-15200",
    "url": "https://www.federalregister.gov/documents/2026/07/31/2026-15200",
    "title": 'Enforcement action notice, internal note leaked: api_key="FAKEGENERICKEY1234567890"',
    "status": "enforcement_action",
    "jurisdiction": "US-Federal",
    "effective_date": "2026-08-15",
    "published": "2026-07-31",
    "prospect_key": "prospect:federal-healthcare-client",
}

MALFORMED_ITEM = {"source": "FederalRegister", "id": "FR-2026-00000"}

PRESEED_ITEM = {
    "source": "FederalRegister",
    "id": "FR-2026-16000",
    "docket_id": "FR-2026-16000",
    "url": "https://www.federalregister.gov/documents/2026/06/01/2026-16000",
    "title": "Already-known enforcement action, re-polled",
    "status": "enforcement_action",
    "jurisdiction": "US-Federal",
    "effective_date": "2026-07-01",
    "published": "2026-06-01",
    "prospect_key": "prospect:federal-healthcare-client",
}

PRESEED_NEW_ITEM = {
    "source": "FederalRegister",
    "id": "FR-2026-16001",
    "docket_id": "FR-2026-16001",
    "url": "https://www.federalregister.gov/documents/2026/06/02/2026-16001",
    "title": "New enforcement action",
    "status": "enforcement_action",
    "jurisdiction": "California",
    "effective_date": "2026-07-02",
    "published": "2026-06-02",
    "prospect_key": "prospect:california-retailer",
}
