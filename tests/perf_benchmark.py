"""Performance benchmark — measure agent response times under load."""

import asyncio
import time
import statistics


async def benchmark_intent(iterations: int = 1000) -> dict:
    """Benchmark IntentGateway throughput."""
    from app.rag.intent import IntentRecognizer, IntentGateway

    recognizer = IntentRecognizer()
    gateway = IntentGateway(recognizer)

    queries = [
        "CPU 使用率过高怎么排查",
        "数据库连接池耗尽了怎么办",
        "Redis 怎么配置持久化",
        "K8s Pod 一直 CrashLoopBackOff",
        "微服务和单体架构有什么区别",
    ]

    start = time.perf_counter()
    for _ in range(iterations):
        q = queries[_ % len(queries)]
        gateway.route(q)
    elapsed = time.perf_counter() - start

    return {
        "iterations": iterations,
        "total_seconds": round(elapsed, 3),
        "avg_ms": round(elapsed / iterations * 1000, 3),
        "qps": round(iterations / elapsed, 1),
    }


async def benchmark_session_ops(iterations: int = 500) -> dict:
    """Benchmark session manager operations."""
    from app.session.manager import Session, SessionStore

    store = SessionStore(backend="memory")

    start = time.perf_counter()
    for i in range(iterations):
        sid = f"perf-test-{i}"
        session = await store.get_or_create(sid)
        await session.add_message(f"question {i}", f"answer {i}")
        await session.get_history()
    elapsed = time.perf_counter() - start

    return {
        "iterations": iterations,
        "total_seconds": round(elapsed, 3),
        "avg_ms": round(elapsed / iterations * 1000, 3),
    }


async def run_all_benchmarks():
    print("=" * 50)
    print("SuperBizAgent Performance Benchmarks")
    print("=" * 50)

    intent_result = await benchmark_intent(1000)
    print(f"\nIntentGateway:")
    print(f"  {intent_result['iterations']} iterations")
    print(f"  {intent_result['total_seconds']}s total")
    print(f"  {intent_result['avg_ms']}ms avg")
    print(f"  {intent_result['qps']} QPS")

    session_result = await benchmark_session_ops(500)
    print(f"\nSessionStore (memory):")
    print(f"  {session_result['iterations']} iterations")
    print(f"  {session_result['total_seconds']}s total")
    print(f"  {session_result['avg_ms']}ms avg")


if __name__ == "__main__":
    asyncio.run(run_all_benchmarks())
