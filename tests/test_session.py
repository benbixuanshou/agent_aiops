"""Session persistence tests."""

import pytest
from app.session.manager import Session, SessionStore


@pytest.mark.asyncio
async def test_session_create():
    session = Session("test-1")
    assert session.session_id == "test-1"
    assert session.message_pair_count() == 0


@pytest.mark.asyncio
async def test_session_add_and_retrieve():
    session = Session("test-2")
    await session.add_message("你好", "你好！有什么可以帮助你的？")
    history = await session.get_history()
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_session_prune():
    from app.config import settings
    session = Session("test-3")
    max_pairs = settings.session_max_pairs
    for i in range(max_pairs + 2):
        await session.add_message(f"q{i}", f"a{i}")
    history = await session.get_history()
    assert len(history) <= max_pairs * 2


@pytest.mark.asyncio
async def test_session_store_get_or_create():
    store = SessionStore(backend="memory")
    s1 = await store.get_or_create(None)
    s2 = await store.get_or_create(s1.session_id)
    assert s1.session_id == s2.session_id


@pytest.mark.asyncio
async def test_session_store_info():
    store = SessionStore(backend="memory")
    s = await store.get_or_create("test-info")
    info = await store.get_info("test-info")
    assert info["session_id"] == "test-info"
    assert "message_pair_count" in info
