"""Audit log — append-only operation records for compliance."""

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path

from app.config import settings

logger = logging.getLogger("superbizagent")

AUDIT_PATH = Path("data/audit.jsonl")


class AuditLogger:
    """Simple append-only audit log (JSONL file). In production, replace with DB-backed."""

    def __init__(self):
        self._lock = asyncio.Lock()

    async def log(self, action: str, actor: str, detail: str = "", target: str = ""):
        async with self._lock:
            entry = {
                "id": str(uuid.uuid4())[:8],
                "ts": time.time(),
                "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "actor": actor,
                "action": action,
                "target": target,
                "detail": detail,
            }
            try:
                AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(AUDIT_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception:
                logger.error("audit_log_failed", extra=entry)

    async def log_operation(self, action: str, api_key: str = "system", detail: str = ""):
        await self.log(action=action, actor=api_key[:8], detail=detail)


audit_log = AuditLogger()
