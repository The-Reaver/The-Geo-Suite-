# SPEC: SPEC_CCC_M1_INGESTION
from .analytics_gateway import fetch_analytics
from .crawl_gateway import fetch_page
from .llm_gateway import complete_prompt, multi_model_identical
from .serp_gateway import fetch_serp

__all__ = [
    "fetch_serp",
    "complete_prompt",
    "multi_model_identical",
    "fetch_page",
    "fetch_analytics",
]
