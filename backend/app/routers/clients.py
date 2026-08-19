"""Client provisioning routes â€” backed by ClientStore seam (RV-PLATFORM-01)."""
from __future__ import annotations

from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path

from ..core.permissions import require_admin, require_owner
from ..schemas.client_schemas import ClientCreate, ClientResponse, SiteCreate
from ..services.client_store import get_client_store

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("/", response_model=ClientResponse)
def create_client(client: ClientCreate, payload: dict = Depends(require_admin)):
    owner = None
    sub = payload.get("sub")
    if sub:
        try:
            owner = UUID(str(sub))
        except ValueError:
            owner = None
    rec = get_client_store().create_client(client.model_dump(mode="json"), owner_user_id=owner)
    return rec.to_response_dict()


@router.get("/", response_model=List[ClientResponse])
def list_clients(payload: dict = Depends(require_admin)):
    return [c.to_response_dict() for c in get_client_store().list_clients()]


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: str = Path(..., description="Client ID coerced to str to avoid UUID serialization bugs"),
    payload: dict = Depends(require_owner),
):
    try:
        cid = UUID(str(client_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid client_id") from e
    rec = get_client_store().get_client(cid)
    if rec is None:
        # Preserve prior stub tolerance for fixture UUID used in owner-scope test
        # only when store is empty of that id: return honest 404.
        raise HTTPException(status_code=404, detail="client not found")
    return rec.to_response_dict()


@router.patch("/{client_id}", response_model=ClientResponse)
def update_client(
    client: ClientCreate,
    client_id: str = Path(...),
    payload: dict = Depends(require_owner),
):
    try:
        cid = UUID(str(client_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid client_id") from e
    rec = get_client_store().update_client(cid, client.model_dump(mode="json"))
    if rec is None:
        raise HTTPException(status_code=404, detail="client not found")
    return rec.to_response_dict()


@router.post("/{client_id}/sites", response_model=Dict[str, str])
def create_site_and_queue_build(
    site: SiteCreate,
    client_id: str = Path(...),
    payload: dict = Depends(require_owner),
):
    try:
        cid = UUID(str(client_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid client_id") from e
    rec = get_client_store().create_site(cid, site.domain)
    if rec is None:
        raise HTTPException(status_code=404, detail="client not found")
    return rec.to_queue_dict()
