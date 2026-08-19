# SPEC: SPEC_CCC_M1_INGESTION
from .content_parse import parse_html_document, resolve_freshness_date
from .ecosystem_crawl import crawl_platforms
from .envelope import GatewayEnvelope, IngestionError
from .llm_ingest import assert_budget, run_stability_sample

__all__ = [
    "GatewayEnvelope",
    "IngestionError",
    "parse_html_document",
    "resolve_freshness_date",
    "crawl_platforms",
    "run_stability_sample",
    "assert_budget",
]
