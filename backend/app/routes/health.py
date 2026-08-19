"""Health route for the platform.

GET /health reports two things: that the FastAPI service is alive, and
whether the Supabase database answers. The route never raises on a
database failure. Placeholder environment values produce a clean
"not_configured" or "unreachable" status instead of a crash, so the
repo runs locally before you paste live keys.

Deploy notes for Railway. This route is the healthcheckPath named in
backend/railway.json, and scripts/verify_health.py reads its JSON body
during the acceptance pass. The handler always answers 200, because a
response proves the process is alive and Railway restarts the service
on non-200 healthchecks. Degradation shows in the body, not the status
code: the top-level "status" field reads "ok" when the database ping
succeeds and "degraded" otherwise, and the acceptance pass requires
"ok" at the live URL. A HEAD handler answers platform probes that skip
the body.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Response

from app.config import get_settings
from app.services.supabase_client import check_database

router = APIRouter(tags=["health"])

_STARTED_AT = time.monotonic()


@router.get("/health")
async def health() -> dict[str, Any]:
    """Return service and database status.

    The service field is always "ok" when this handler runs, because a
    response proves the process is alive. The database field carries one
    of three values:

    - "ok": Supabase answered the ping.
    - "not_configured": the environment holds placeholder or missing
      Supabase values, so no ping was attempted.
    - "unreachable": real-looking values are present but the ping failed.

    The top-level status field aggregates the two: "ok" only when the
    database also answers, "degraded" for anything else. The live
    acceptance pass (criterion 8) requires "ok", so a deploy with
    placeholder keys shows up as degraded instead of passing silently.
    """
    settings = get_settings()

    database = await check_database()

    # check_database() returns {"status": ..., "detail": ...}, not a bare
    # string -- comparing the dict itself to "ok" is always False, which
    # made this endpoint report "degraded" unconditionally even against a
    # healthy, fully-configured Supabase project.
    status = "ok" if database.get("status") == "ok" else "degraded"

    return {
        "status": status,
        "service": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
        "uptime_seconds": round(time.monotonic() - _STARTED_AT, 1),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "database": database,
    }


@router.head("/health")
async def health_head() -> Response:
    """Answer bodyless probes.

    Railway and some uptime monitors send HEAD instead of GET. A plain
    200 here proves liveness without running the database ping.
    """
    return Response(status_code=200)