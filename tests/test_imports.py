"""Smoke test: all modules import cleanly."""

def test_import_config():
    from app.config import settings
    assert settings.port == 9900
    assert settings.milvus_collection == "biz"


def test_import_agent():
    from app.agent.react_agent import build_rag_agent, build_sre_agent
    from app.agent.tools import gather_rag_tools, gather_sre_tools
    from app.agent.supervisor import Supervisor

    rag_tools = gather_rag_tools()
    sre_tools = gather_sre_tools()
    assert len(rag_tools) >= 2
    assert len(sre_tools) >= 3


def test_import_rag():
    from app.rag.intent import IntentRecognizer, IntentGateway, IntentType
    from app.rag.retrieval import MilvusStore
    from app.rag.rag_tool import search_knowledge_base

    r = IntentRecognizer()
    result = r.recognize("CPU 使用率过高怎么排查")
    assert result.intent in (IntentType.TROUBLESHOOTING, IntentType.GENERAL_QUESTION)


def test_import_tools():
    from app.tools.datetime_tool import get_current_datetime
    from app.tools.prometheus_tool import query_prometheus_alerts
    from app.tools.cls_logs_tool import query_logs, get_available_log_topics

    dt = get_current_datetime.invoke({})
    assert "T" in dt


def test_import_session():
    from app.session.manager import SessionStore, session_store
    assert session_store is not None


def test_import_skills():
    from app.skills.loader import SkillLoader
    loader = SkillLoader()
    assert len(loader.skills) >= 1


def test_import_api():
    from app.api import chat, aiops, upload, health, session
    from app.models.schemas import ChatRequest, SseMessage

    req = ChatRequest(Question="test")
    assert req.Question == "test"
