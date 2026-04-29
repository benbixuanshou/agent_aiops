from fastapi import APIRouter, Request

from app.self_monitor import agent_metrics

router = APIRouter(tags=["health"])


@router.get("/milvus/health")
async def milvus_health(request: Request):
    status = {"milvus": "unknown", "deepseek": "unknown", "collection": "biz"}

    # Milvus
    try:
        vs = request.app.state.vector_store
        status["vector_count"] = vs.col.num_entities
        status["milvus"] = "ok"
    except Exception as e:
        status["milvus"] = f"disconnected"

    # DeepSeek
    try:
        sv = request.app.state.supervisor
        if sv and sv.llm:
            status["deepseek"] = "ok"
    except Exception:
        status["deepseek"] = "not_initialized"

    # Agent self-monitoring
    status["agent"] = agent_metrics.health_report()

    ok = status["milvus"] == "ok" and status["deepseek"] == "ok"
    return {"message": "ok" if ok else "degraded", **status}
