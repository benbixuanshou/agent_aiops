"""Audit logger — append-only operation records to JSONL file + in-memory buffer."""

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path

logger = logging.getLogger("superbizagent")

AUDIT_PATH = Path("data/audit.jsonl")


class AuditLogger:
    """Append-only audit log. File-based for simplicity, DB-backed in production."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._buffer: list[dict] = []
        self._max_buffer = 50

    async def log(self, actor: str, action: str, target: str = "", detail: str = "", tenant_id: str = ""):
        entry = {
            "id": str(uuid.uuid4())[:8],
            "ts": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "actor": actor[:64],
            "action": action,
            "target": target[:128],
            "detail": detail[:500],
            "tenant": tenant_id,
        }
        async with self._lock:
            self._buffer.append(entry)
            if len(self._buffer) >= self._max_buffer:
                await self._flush()

    async def log_request(self, api_key: str, method: str, path: str, status: int, tenant_id: str = ""):
        await self.log(
            actor=api_key[:16],
            action=f"{method} {path}",
            target=path,
            detail=f"status={status}",
            tenant_id=tenant_id,
        )

    async def log_write_op(self, api_key: str, op: str, target: str, tenant_id: str = ""):
        await self.log(
            actor=api_key[:16],
            action=op,
            target=target,
            detail="write_operation",
            tenant_id=tenant_id,
        )

    async def _flush(self):
        if not self._buffer:
            return
        try:
            AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(AUDIT_PATH, "a", encoding="utf-8") as f:
                for entry in self._buffer:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._buffer.clear()
        except Exception:
            logger.error("audit_flush_failed", exc_info=True)

    async def shutdown(self):
        await self._flush()


audit_logger = AuditLogger()
