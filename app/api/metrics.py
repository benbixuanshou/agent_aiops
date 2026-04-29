"""Prometheus /metrics endpoint — export Agent health counters."""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.self_monitor import agent_metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics():
    m = agent_metrics
    lines = [
        "# HELP superbizagent_http_requests_total Total HTTP requests (placeholder — set by middleware)",
        "# TYPE superbizagent_http_requests_total counter",
        f"superbizagent_http_requests_total 0",
        "",
        "# HELP superbizagent_llm_calls_total Total LLM calls",
        "# TYPE superbizagent_llm_calls_total counter",
        f"superbizagent_llm_calls_total {m.llm_calls}",
        "",
        "# HELP superbizagent_llm_failures_total Total LLM call failures",
        "# TYPE superbizagent_llm_failures_total counter",
        f"superbizagent_llm_failures_total {m.llm_failures}",
        "",
        "# HELP superbizagent_tool_calls_total Total tool calls",
        "# TYPE superbizagent_tool_calls_total counter",
        f"superbizagent_tool_calls_total {m.tool_calls}",
        "",
        "# HELP superbizagent_tool_failures_total Total tool call failures",
        "# TYPE superbizagent_tool_failures_total counter",
        f"superbizagent_tool_failures_total {m.tool_failures}",
        "",
        "# HELP superbizagent_llm_success_rate LLM call success rate (0-1)",
        "# TYPE superbizagent_llm_success_rate gauge",
        f"superbizagent_llm_success_rate {m.llm_success_rate}",
        "",
        "# HELP superbizagent_alert_storm 1 if alert storm detected",
        "# TYPE superbizagent_alert_storm gauge",
        f"superbizagent_alert_storm {1 if m.is_alert_storm else 0}",
        "",
    ]
    return PlainTextResponse("\n".join(lines), media_type="text/plain")
