"""Admin API — global stats, tenant overview."""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.middleware.auth import get_tenant_context
from app.self_monitor import agent_metrics
from app.tenant_store import tenant_registry

logger = logging.getLogger("superbizagent")
router = APIRouter(tags=["admin"])


@router.get("/admin/stats")
async def admin_stats(request: Request):
    """Global dashboard stats — admin role only."""
    ctx = get_tenant_context(request)
    if ctx is None or ctx.role != "admin":
        raise HTTPException(status_code=403, detail="admin role required")

    return {
        "tenants": {
            "count": tenant_registry.tenant_count,
            "keys": tenant_registry.key_count,
        },
        "agent": agent_metrics.health_report(),
        "server": "ok",
    }


@router.get("/admin/tenants")
async def admin_tenants(request: Request):
    ctx = get_tenant_context(request)
    if ctx is None or ctx.role != "admin":
        raise HTTPException(status_code=403, detail="admin role required")

    return {
        "current_tenant": {
            "id": ctx.tenant_id,
            "name": ctx.tenant_name,
            "role": ctx.role,
        },
    }
