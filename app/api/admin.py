"""Admin API — login, global stats, tenant overview."""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.middleware.auth import get_tenant_context
from app.self_monitor import agent_metrics
from app.tenant_store import tenant_registry, TenantContext, DEFAULT_TENANT_ID
from app.config import settings

logger = logging.getLogger("superbizagent")
router = APIRouter(tags=["admin"])


class LoginRequest(BaseModel):
    api_key: str = Field(..., alias="api_key")


@router.post("/login")
async def login(req: LoginRequest):
    """Validate API Key and return tenant info + role. No auth required."""
    key = req.api_key.strip()
    if not key:
        raise HTTPException(status_code=401, detail="api_key is required")

    ctx = tenant_registry.lookup(key)

    # Also check env API_KEYS fallback
    if not ctx:
        env_keys = {k.strip() for k in settings.api_keys.split(",") if k.strip()}
        if key in env_keys:
            ctx = TenantContext(
                tenant_id=DEFAULT_TENANT_ID,
                tenant_name="Default Tenant",
                role="admin",
            )

    if not ctx:
        raise HTTPException(status_code=401, detail="invalid api_key")

    return {
        "status": "ok",
        "tenant": {
            "id": ctx.tenant_id,
            "name": ctx.tenant_name,
            "role": ctx.role,
        },
    }


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
    """Current tenant info — any authenticated role."""
    ctx = get_tenant_context(request)
    return {
        "tenant": {
            "id": ctx.tenant_id,
            "name": ctx.tenant_name,
            "role": ctx.role,
        },
    }
