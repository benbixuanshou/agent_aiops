"""Tool registries for RAG Agent and SRE Agent."""

from app.tools.datetime_tool import get_current_datetime
from app.tools.prometheus_tool import query_prometheus_alerts
from app.tools.cls_logs_tool import query_logs, get_available_log_topics
from app.rag.rag_tool import search_knowledge_base
from app.config import settings


def gather_rag_tools() -> list:
    """Tools for RAG Agent: knowledge search + datetime."""
    return [search_knowledge_base, get_current_datetime]


def gather_sre_tools(include_cls: bool = None) -> list:
    """Tools for SRE Agent: full incident response toolkit."""
    tools = [get_current_datetime, search_knowledge_base, query_prometheus_alerts]
    if include_cls is None:
        include_cls = settings.cls_mock_enabled
    if include_cls:
        tools.extend([query_logs, get_available_log_topics])
    return tools
