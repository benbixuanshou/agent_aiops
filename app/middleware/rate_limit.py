import time
from collections import defaultdict

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

SKIP_LIMIT_PATHS = {"/docs", "/redoc", "/openapi.json", "/milvus/health"}

WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, dispatch=None):
        super().__init__(app, dispatch)
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

    def _resolve_key(self, request: Request) -> str:
        api_key = request.headers.get("X-API-Key", "anonymous")
        return f"rl:{api_key}"

    def _get_limit(self, path: str) -> int:
        """Chat/AIOps endpoints have tighter limits since they cost LLM calls."""
        if path.startswith("/api/chat") or path.startswith("/api/ai_ops"):
            return settings.rate_limit_chat_per_minute
        return settings.rate_limit_default_per_minute

    async def dispatch(self, request: Request, call_next):
        if request.url.path in SKIP_LIMIT_PATHS:
            return await call_next(request)

        key = self._resolve_key(request)
        limit = self._get_limit(request.url.path)

        if self._redis:
            ok = self._check_redis(key, limit)
        else:
            ok = self._check_memory(key, limit)

        if not ok:
            raise HTTPException(
                status_code=429,
                detail="rate limit exceeded",
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )

        return await call_next(request)

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
