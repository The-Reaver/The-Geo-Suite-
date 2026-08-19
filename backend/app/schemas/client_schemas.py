from pydantic import BaseModel
from typing import Optional, Dict, Any
from uuid import UUID
from ..core.enums import ClientType

class ClientBase(BaseModel):
    business_name: str
    tier: str
    client_type: ClientType  # canonical enum (single source: core/enums.py)
    status: str
    nap: Dict[str, Any]
    monthly_fee_cents: int
    margin_alert_pct: float

class ClientCreate(ClientBase):
    pass

class ClientResponse(ClientBase):
    id: UUID
    owner_user_id: Optional[UUID]

class SiteCreate(BaseModel):
    domain: str

class SiteResponse(BaseModel):
    id: UUID
    client_id: UUID
    domain: str
    status: str
