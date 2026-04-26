"""Core smoke tests — 10 cases covering the critical path."""

import pytest


# ═══ Intent Recognition (6 cases) ═══

def test_intent_troubleshoot_cpu():
    from app.rag.intent import IntentRecognizer, IntentType
    r = IntentRecognizer()
    result = r.recognize("CPU 使用率过高怎么排查")
    assert result.intent in (IntentType.TROUBLESHOOTING, IntentType.GENERAL_QUESTION)

def test_intent_troubleshoot_error():
    from app.rag.intent import IntentRecognizer, IntentType
    r = IntentRecognizer()
    result = r.recognize("服务报错了 CPU 过高 内存泄漏")
    assert result.intent != IntentType.TECHNICAL_QUESTION

def test_intent_technical_question():
    from app.rag.intent import IntentRecognizer, IntentType
    r = IntentRecognizer()
    result = r.recognize("Redis 怎么配置持久化")
    assert result.intent in (IntentType.CONFIGURATION, IntentType.TECHNICAL_QUESTION, IntentType.GENERAL_QUESTION)

def test_intent_empty_query():
    from app.rag.intent import IntentRecognizer, IntentType
    r = IntentRecognizer()
    result = r.recognize("")
    assert result.confidence == 0.0

def test_intent_irrelevant():
    from app.rag.intent import IntentRecognizer, IntentType
    r = IntentRecognizer()
    result = r.recognize("今天天气怎么样")
    assert result.confidence == 0.0  # no keyword matches

def test_intent_gateway_blocks_irrelevant():
    from app.rag.intent import IntentGateway
    g = IntentGateway()
    config = g.route("今天天气怎么样")
    assert config.block is True


# ═══ Session (3 cases) ═══

@pytest.mark.asyncio
async def test_session_create_and_add():
    from app.session.manager import Session
    s = Session("test-a")
    await s.add_message("你好", "你好！")
    h = await s.get_history()
    assert len(h) == 2
    assert h[0]["role"] == "user"

@pytest.mark.asyncio
async def test_session_store():
    from app.session.manager import SessionStore
    store = SessionStore(backend="memory")
    s1 = await store.get_or_create(None)
    s2 = await store.get_or_create(s1.session_id)
    assert s1.session_id == s2.session_id

@pytest.mark.asyncio
async def test_session_clear():
    from app.session.manager import Session
    s = Session("test-c")
    await s.add_message("q", "a")
    await s.clear()
    h = await s.get_history()
    assert len(h) == 0


# ═══ Health check (1 case) ═══

def test_health_check_response_key():
    """Verify the health check module can be imported and has the right route."""
    from app.api.health import router
    routes = [r.path for r in router.routes]
    assert "/milvus/health" in routes
