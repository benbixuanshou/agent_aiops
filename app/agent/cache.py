"""Tool invocation cache — avoids redundant LLM→tool round-trips."""

import asyncio
import hashlib
import json
import time
from functools import wraps


class ToolCache:
    """In-process cache for tool invocation results. 5-min default TTL."""

    def __init__(self):
        self._cache: dict[str, tuple[float, str]] = {}
        self._lock = asyncio.Lock()

    def _key(self, tool_name: str, args: dict) -> str:
        raw = f"{tool_name}:{json.dumps(args, sort_keys=True, default=str)}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    async def get(self, tool_name: str, args: dict, ttl: int = 300) -> str | None:
        key = self._key(tool_name, args)
        async with self._lock:
            entry = self._cache.get(key)
            if entry and (time.time() - entry[0]) < ttl:
                return entry[1]
        return None

    async def set(self, tool_name: str, args: dict, result: str):
        key = self._key(tool_name, args)
        async with self._lock:
            self._cache[key] = (time.time(), result)

    async def clear(self):
        async with self._lock:
            self._cache.clear()


# Global singleton
tool_cache = ToolCache()
