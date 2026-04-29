from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

SKIP_AUTH_PATHS = {"/docs", "/redoc", "/openapi.json", "/milvus/health", "/metrics"}


def _parse_keys(raw: str) -> set[str]:
    return {k.strip() for k in raw.split(",") if k.strip()}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in SKIP_AUTH_PATHS:
            return await call_next(request)

        valid_keys = _parse_keys(settings.api_keys)
        if not valid_keys:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not api_key:
            raise HTTPException(status_code=401, detail="missing X-API-Key header")

        if api_key not in valid_keys:
            raise HTTPException(status_code=401, detail="invalid API key")

        return await call_next(request)
