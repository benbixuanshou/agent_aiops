"""Knowledge deposition endpoint — confirm & ingest AIOps findings into the vector DB."""

import logging
import time

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.session.manager import session_store

logger = logging.getLogger("superbizagent")
router = APIRouter()


class ConfirmRequest(BaseModel):
    cache_key: str = Field(..., description="Tool cache key from aiops report")
    title: str = Field(default="", description="Document title for the knowledge entry")


@router.post("/knowledge/confirm")
async def confirm_knowledge(request: Request, req: ConfirmRequest):
    """Confirm an AIOps finding and store it as a knowledge base entry.

    Called when a user in IM replies "confirm" to an Agent report.
    The finding is retrieved from the tool cache, formatted, and indexed into Milvus.
    """
    result = await session_store.get_tool_result(req.cache_key)
    if not result:
        return {"status": "not_found", "detail": "cache key expired or invalid"}

    vector_store = request.app.state.vector_store
    embedder = request.app.state.embedder

    title = req.title or f"AIops finding {time.strftime('%Y-%m-%d %H:%M')}"
    document = f"# {title}\n\n## 排查结果\n\n{result[:8000]}"

    try:
        from app.ingestion.indexer import IndexingService
        indexer = IndexingService(vector_store, embedder)
        await indexer.index_text(document, source=req.cache_key)
        logger.info("knowledge_confirmed: %s", req.cache_key)
        return {"status": "ok", "detail": f"knowledge entry '{title}' indexed"}
    except Exception:
        logger.error("knowledge_confirm_failed: %s", req.cache_key, exc_info=True)
        return {"status": "error", "detail": "indexing failed"}
