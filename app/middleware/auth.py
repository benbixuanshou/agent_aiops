"""API Key authentication — pure ASGI middleware (avoids BaseHTTPMiddleware ExceptionGroup issues)."""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.tenant_store import tenant_registry, TenantContext, DEFAULT_TENANT_ID

SKIP_AUTH_PATHS = {"/", "/docs", "/redoc", "/openapi.json", "/milvus/health", "/metrics"}

STATIC_EXTENSIONS = {".js", ".css", ".html", ".ico", ".svg", ".png", ".jpg", ".woff2", ".map"}

def _should_skip(path: str) -> bool:
    if path in SKIP_AUTH_PATHS:
        return True
    import os
    _, ext = os.path.splitext(path)
    return ext.lower() in STATIC_EXTENSIONS


def _parse_keys(raw: str) -> set[str]:
    return {k.strip() for k in raw.split(",") if k.strip()}


ANON = TenantContext(tenant_id=DEFAULT_TENANT_ID, tenant_name="Default Tenant", role="viewer")


def get_tenant_context(request: Request) -> TenantContext:
    return getattr(request.state, "tenant", ANON)


class ApiKeyMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        request.state.tenant = ANON

        if _should_skip(request.url.path):
            await self.app(scope, receive, send)
            return

        env_keys = _parse_keys(settings.api_keys)
        has_any_keys = bool(env_keys or tenant_registry.key_count > 0)
        if not has_any_keys:
            await self.app(scope, receive, send)
            return

        api_key = request.headers.get("X-API-Key")
        if not api_key:
            resp = JSONResponse(status_code=401, content={"detail": "missing X-API-Key header"})
            await resp(scope, receive, send)
            return

        ctx = tenant_registry.lookup(api_key)
        if not ctx and api_key in env_keys:
            ctx = TenantContext(
                tenant_id=DEFAULT_TENANT_ID,
                tenant_name="Default Tenant",
                role="admin",
            )

        if not ctx:
            resp = JSONResponse(status_code=401, content={"detail": "invalid API key"})
            await resp(scope, receive, send)
            return

        request.state.tenant = ctx
        await self.app(scope, receive, send)
