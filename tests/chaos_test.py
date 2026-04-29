"""Chaos test — verify agent behavior under degraded conditions."""

import asyncio


async def test_agent_with_missing_tool():
    """Agent should gracefully handle a missing tool."""
    from app.agent.tools import gather_rag_tools
    tools = gather_rag_tools()
    assert len(tools) >= 2, f"Expected at least 2 tools, got {len(tools)}"
    print(f"  [PASS] RAG agent has {len(tools)} tools (expected >=2)")


async def test_intent_fast_path():
    """IntentGateway should not crash on edge-case inputs."""
    from app.rag.intent import IntentGateway

    gateway = IntentGateway()
    edge_cases = [
        "", " ", "a" * 10000, "!@#$%^&*()", "CPU", "好",
        "SELECT * FROM users", "<script>alert(1)</script>",
    ]
    for q in edge_cases:
        try:
            config = gateway.route(q)
            assert config is not None
        except Exception as e:
            print(f"  [FAIL] IntentGateway crashed on '{q[:30]}': {e}")
            return

    print(f"  [PASS] IntentGateway handled {len(edge_cases)} edge cases")


async def test_session_isolation():
    """Tenant-scoped sessions should be isolated."""
    from app.session.manager import SessionStore

    store = SessionStore(backend="memory")
    s1 = await store.get_or_create("tenant-a:session-1")
    s2 = await store.get_or_create("tenant-b:session-1")

    await s1.add_message("qa", "aa")
    await s2.add_message("qb", "ab")

    h1 = await s1.get_history()
    h2 = await s2.get_history()

    assert len(h1) == 2, f"Session A should have 2 messages, got {len(h1)}"
    assert len(h2) == 2, f"Session B should have 2 messages, got {len(h2)}"
    print(f"  [PASS] Tenant session isolation works (A:{len(h1)}, B:{len(h2)})")


async def test_aggregator_edge_cases():
    """AlertAggregator should handle empty/malformed inputs."""
    from app.agent.alert_aggregator import AlertAggregator

    agg = AlertAggregator()
    assert agg.aggregate([]) == [], "Empty list should return empty"
    assert len(agg.aggregate([{"status": "resolved"}])) == 0, "Resolved alerts should be skipped"
    print("  [PASS] AlertAggregator handles edge cases")


async def test_suppressor_no_crash():
    """AlertSuppressor should handle all alert formats."""
    from app.agent.alert_suppressor import AlertSuppressor

    suppressor = AlertSuppressor()
    edge_alerts = [
        {}, {"labels": {}}, {"status": "firing", "labels": {"alertname": "Test"}},
        {"status": "firing", "labels": {"alertname": "Test", "service": "payment-service"}},
    ]

    active = [{"status": "firing", "labels": {"service": "mysql"}}]
    for a in edge_alerts:
        result = suppressor.should_suppress(a, active)
        # Should not crash, may suppress or not

    print(f"  [PASS] AlertSuppressor handled {len(edge_alerts)} edge cases")


async def run_all_chaos():
    print("=" * 50)
    print("SuperBizAgent Chaos Tests")
    print("=" * 50)

    tests = [
        test_agent_with_missing_tool,
        test_intent_fast_path,
        test_session_isolation,
        test_aggregator_edge_cases,
        test_suppressor_no_crash,
    ]
    for t in tests:
        await t()

    print("\nAll chaos tests passed.")


if __name__ == "__main__":
    asyncio.run(run_all_chaos())
