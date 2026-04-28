"""Session store — MySQL/Redis/sqlite/memory backends.

Architecture:
  Session objects → in-memory (asyncio.Lock, fast access)
  Messages       → MySQL or SQLite (durable persistence)
  Tool cache     → Redis (TTL) or SQLite
  Long-term      → MySQL or SQLite
"""

import asyncio
import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger("superbizagent")


class Session:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.history: list[dict] = []
        self.created_at = time.time()
        self.updated_at = time.time()
        self._lock = asyncio.Lock()

    async def add_message(self, user_msg: str, assistant_msg: str):
        async with self._lock:
            self.history.append({"role": "user", "content": user_msg})
            self.history.append({"role": "assistant", "content": assistant_msg})
            self.updated_at = time.time()

    async def compress_history(self, summarize_fn):
        async with self._lock:
            max_messages = settings.session_max_pairs * 2
            if len(self.history) <= max_messages:
                return
            to_compress = []
            while len(self.history) > max_messages and self.history:
                user_msg = self.history.pop(0)
                if self.history and self.history[0].get("role") == "assistant":
                    assistant_msg = self.history.pop(0)
                    to_compress.append((user_msg["content"], assistant_msg["content"]))
                else:
                    break
            if not to_compress:
                return
            try:
                dialog = "\n".join(f"Q: {u}\nA: {a[:200]}" for u, a in to_compress[-3:])
                summary = await summarize_fn(
                    f"将以下对话压缩为200字以内的摘要，只保留关键事实:\n{dialog}"
                )
                self.history.insert(0, {"role": "system", "content": f"[前情摘要] {summary}"})
            except Exception:
                logger.warning("compress_history: summarization failed, keeping raw history")

    async def get_history(self) -> list[dict]:
        async with self._lock:
            return list(self.history)

    async def clear(self):
        async with self._lock:
            self.history.clear()

    def message_pair_count(self) -> int:
        return len(self.history) // 2


# ═══════════════════════════════════════════════════════════════
# SessionStore with pluggable backends
# ═══════════════════════════════════════════════════════════════

class SessionStore:
    def __init__(self, backend: str = "memory"):
        self.backend = backend
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()
        self._mysql_pool = None
        self._redis = None

        if backend == "sqlite":
            self._db_path = settings.sqlite_path or "data/sessions.db"
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            self._init_sqlite()
        elif backend == "mysql":
            self._mysql_dsn = {
                "host": settings.mysql_host,
                "port": settings.mysql_port,
                "user": settings.mysql_user,
                "password": settings.mysql_password,
                "db": settings.mysql_database,
                "autocommit": True,
            }

    # ═══ SQLite (legacy) ═══

    def _init_sqlite(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY, created_at REAL, updated_at REAL)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT,
                role TEXT, content TEXT, created_at REAL)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS tool_cache (
                cache_key TEXT PRIMARY KEY, result TEXT,
                created_at REAL, ttl INTEGER DEFAULT 300)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS long_term_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT, query TEXT,
                finding TEXT, created_at REAL)""")
            conn.commit()

    # ═══ MySQL ═══

    async def _get_mysql(self):
        if self._mysql_pool is None:
            import aiomysql
            self._mysql_pool = await aiomysql.create_pool(**self._mysql_dsn, minsize=1, maxsize=5)
            async with self._mysql_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""CREATE TABLE IF NOT EXISTS sessions (
                        session_id VARCHAR(64) PRIMARY KEY,
                        created_at DOUBLE NOT NULL,
                        updated_at DOUBLE NOT NULL) ENGINE=InnoDB""")
                    await cur.execute("""CREATE TABLE IF NOT EXISTS messages (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        session_id VARCHAR(64) NOT NULL,
                        role VARCHAR(16) NOT NULL,
                        content TEXT NOT NULL,
                        created_at DOUBLE NOT NULL,
                        INDEX idx_session (session_id)) ENGINE=InnoDB""")
                    await cur.execute("""CREATE TABLE IF NOT EXISTS tool_cache (
                        cache_key VARCHAR(128) PRIMARY KEY,
                        result TEXT NOT NULL,
                        created_at DOUBLE NOT NULL,
                        ttl INT DEFAULT 300) ENGINE=InnoDB""")
                    await cur.execute("""CREATE TABLE IF NOT EXISTS long_term_memory (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        query TEXT NOT NULL,
                        finding TEXT NOT NULL,
                        created_at DOUBLE NOT NULL) ENGINE=InnoDB""")
        return self._mysql_pool

    # ═══ Redis ═══

    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as aioredis
            try:
                self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
                await self._redis.ping()
            except Exception:
                self._redis = None
        return self._redis

    # ═══ Public API ═══

    async def get_or_create(self, session_id: Optional[str] = None) -> Session:
        if not session_id:
            session_id = str(uuid.uuid4())
        async with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = Session(session_id)
                if self.backend == "sqlite":
                    self._persist_sqlite_session(session_id)
                elif self.backend == "mysql":
                    await self._persist_mysql_session(session_id)
            return self._sessions[session_id]

    def _persist_sqlite_session(self, session_id: str):
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?, ?)",
                             (session_id, time.time(), time.time()))
                conn.commit()
        except Exception:
            logger.warning("_persist_sqlite_session failed for %s", session_id)

    async def _persist_mysql_session(self, session_id: str):
        try:
            pool = await self._get_mysql()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO sessions VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE updated_at=%s",
                        (session_id, time.time(), time.time(), time.time()))
        except Exception:
            logger.warning("_persist_mysql_session failed for %s", session_id)

    async def clear(self, session_id: str):
        session = self._sessions.get(session_id)
        if session:
            await session.clear()

    async def get_info(self, session_id: str) -> Optional[dict]:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        return {
            "session_id": session.session_id,
            "message_pair_count": session.message_pair_count(),
            "create_time": session.created_at,
        }

    async def cleanup_expired(self, max_age_seconds: int = 7 * 24 * 3600):
        now = time.time()
        async with self._lock:
            expired = [sid for sid, s in self._sessions.items() if now - s.updated_at > max_age_seconds]
            for sid in expired:
                del self._sessions[sid]

    # ═══ Tool cache ═══

    async def store_tool_result(self, cache_key: str, result: str, ttl: int = 300):
        redis = await self._get_redis()
        if redis:
            try:
                await redis.setex(f"tool:{cache_key}", ttl, result[:50000])
                return
            except Exception:
                logger.warning("store_tool_result: redis failed for %s", cache_key)
        if self.backend == "sqlite":
            try:
                with sqlite3.connect(self._db_path) as conn:
                    conn.execute("INSERT OR REPLACE INTO tool_cache VALUES (?, ?, ?, ?)",
                                 (cache_key, result, time.time(), ttl))
                    conn.commit()
            except Exception:
                logger.warning("store_tool_result: sqlite failed for %s", cache_key)
        elif self.backend == "mysql":
            try:
                pool = await self._get_mysql()
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(
                            "REPLACE INTO tool_cache VALUES (%s, %s, %s, %s)",
                            (cache_key, result, time.time(), ttl))
            except Exception:
                logger.warning("store_tool_result: mysql failed for %s", cache_key)

    async def get_tool_result(self, cache_key: str) -> Optional[str]:
        redis = await self._get_redis()
        if redis:
            try:
                val = await redis.get(f"tool:{cache_key}")
                if val:
                    return val
            except Exception:
                logger.warning("get_tool_result: redis failed for %s", cache_key)
        if self.backend == "sqlite":
            try:
                with sqlite3.connect(self._db_path) as conn:
                    row = conn.execute("SELECT result, created_at, ttl FROM tool_cache WHERE cache_key=?",
                                       (cache_key,)).fetchone()
                    if row and (time.time() - row[1]) < row[2]:
                        return row[0]
            except Exception:
                logger.warning("get_tool_result: sqlite failed for %s", cache_key)
        elif self.backend == "mysql":
            try:
                pool = await self._get_mysql()
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT result, created_at, ttl FROM tool_cache WHERE cache_key=%s",
                                          (cache_key,))
                        row = await cur.fetchone()
                        if row and (time.time() - row[0][1]) < row[0][2]:
                            return row[0][0]
            except Exception:
                logger.warning("get_tool_result: mysql failed for %s", cache_key)
        return None


session_store = SessionStore(backend=settings.session_backend)
