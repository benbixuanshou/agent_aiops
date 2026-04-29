"""Rate limiting — pure ASGI middleware."""

import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings

SKIP_LIMIT_PATHS = {"/", "/docs", "/redoc", "/openapi.json", "/milvus/health", "/metrics"}

STATIC_EXTENSIONS = {".js", ".css", ".html", ".ico", ".svg", ".png", ".jpg", ".woff2", ".map"}

def _should_skip(path: str) -> bool:
    if path in SKIP_LIMIT_PATHS:
        return True
    import os
    _, ext = os.path.splitext(path)
    return ext.lower() in STATIC_EXTENSIONS
WINDOW_SECONDS = 60


class RateLimitMiddleware:
    def __init__(self, app):
        self.app = app
        self._memory_store: dict[str, list[float]] = defaultdict(list)
        self._redis = None
        self._init_redis()

    def _init_redis(self):
        try:
            import redis
            self._redis = redis.from_url(settings.redis_url, decode_responses=True)
            self._redis.ping()
        except Exception:
            self._redis = None

    def _resolve_key(self, request: Request) -> str | None:
        api_key = request.headers.get("X-API-Key", "")
        if not api_key:
            return None
        return f"rl:{api_key}"

    def _get_limit(self, path: str) -> int:
        if path.startswith("/api/chat") or path.startswith("/api/ai_ops"):
            return settings.rate_limit_chat_per_minute
        return settings.rate_limit_default_per_minute

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        if _should_skip(request.url.path):
            await self.app(scope, receive, send)
            return

        key = self._resolve_key(request)
        if key is None:
            await self.app(scope, receive, send)
            return

        limit = self._get_limit(request.url.path)
        if self._redis:
            ok = self._check_redis(key, limit)
        else:
            ok = self._check_memory(key, limit)

        if not ok:
            resp = JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded"},
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )
            await resp(scope, receive, send)
            return

        await self.app(scope, receive, send)

    def _check_redis(self, key: str, limit: int) -> bool:
        now = time.time()
        window_start = now - WINDOW_SECONDS
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, WINDOW_SECONDS + 1)
        _, count, _, _ = pipe.execute()
        return count < limit

    def _check_memory(self, key: str, limit: int) -> bool:
        now = time.time()
        window_start = now - WINDOW_SECONDS
        timestamps = self._memory_store[key]
        self._memory_store[key] = [t for t in timestamps if t > window_start]
        if len(self._memory_store[key]) >= limit:
            return False
        self._memory_store[key].append(now)
        return True
