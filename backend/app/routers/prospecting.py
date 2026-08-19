"""Prospecting router — the live directory/map discovery surface.

Closes GEO Brain Trust open item 6: the frontend Prospecting screen had wiring
but no service producing prospects. This exposes the discovery source. Auth is
required (require_owner) — prospecting runs an outbound directory pull and feeds
the sales pipeline, so it is not an anonymous endpoint.

When the live source is unconfigured this returns HTTP 200 with status
"DISABLED" and a plain instruction, not a 500: an un-provisioned environment is
an expected operator state, not a server fault.
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.permissions import require_owner
from app.services.sales.prospect_source import discover_and_rank

router = APIRouter(prefix="/prospecting", tags=["prospecting"])


class DiscoverRequest(BaseModel):
    business_type: str
    locality: str = ""
    region: str = ""
    limit: int = 20


@router.post("/discover")
async def discover_prospects(
    request: DiscoverRequest,
    payload: dict = Depends(require_owner),
):
    """Discover prospects for a business type + location and attach each lead's
    honest verdict. Fresh candidates return INCOMPLETE until confirmed — see the
    `note` and `needs_confirmation` fields."""
    return discover_and_rank({
        "business_type": request.business_type,
        "locality": request.locality,
        "region": request.region,
        "limit": request.limit,
    })
