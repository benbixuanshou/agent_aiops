import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from langchain.tools import tool

import httpx
from app.config import settings

SHANGHAI_TZ = timezone(timedelta(hours=8))


def _format_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _build_system_metrics_logs(now: datetime, query: str) -> list[dict]:
    """Build mock system metrics logs"""
    logs = []
    q = query.lower()

    if "cpu" in q or ">80" in q:
        for i in range(5):
            logs.append({
                "timestamp": _format_ts(now - timedelta(minutes=i * 2)),
                "level": "WARN",
                "service": "payment-service",
                "instance": "pod-payment-service-7d8f9c6b5-x2k4m",
                "message": f"CPU使用率过高: {92.0 - i * 1.5:.1f}%, 进程: java (PID: 1), 线程数: 245",
                "metrics": {
                    "cpu_usage": f"{92.0 - i * 1.5:.1f}",
                    "cpu_cores": "4",
                    "load_average_1m": "3.82",
                    "load_average_5m": "3.65",
                },
            })

    if "memory" in q or ">85" in q:
        for i in range(5):
            logs.append({
                "timestamp": _format_ts(now - timedelta(minutes=i * 3)),
                "level": "WARN",
                "service": "order-service",
                "instance": "pod-order-service-5c7d8e9f1-m3n2p",
                "message": f"内存使用率过高: {91.0 - i * 1.2:.1f}%, JVM堆内存: {3.8 - i * 0.1:.1f}GB/4GB, GC次数: {128 - i * 5}",
                "metrics": {
                    "memory_usage": f"{91.0 - i * 1.2:.1f}",
                    "jvm_heap_used": f"{3.8 - i * 0.1:.1f}GB",
                    "gc_count": str(128 - i * 5),
                },
            })

        logs.append({
            "timestamp": _format_ts(now - timedelta(minutes=8)),
            "level": "WARN",
            "service": "order-service",
            "instance": "pod-order-service-5c7d8e9f1-m3n2p",
            "message": "频繁 Full GC 警告: 过去10分钟内发生 15 次 Full GC, 平均耗时 850ms, 建议检查内存泄漏",
            "metrics": {"full_gc_count": "15", "avg_gc_time_ms": "850", "old_gen": "89%"},
        })

    return logs


def _build_application_logs(now: datetime, query: str) -> list[dict]:
    """Build mock application logs"""
    logs = []
    q = query.lower()

    if "error" in q or "fatal" in q or "500" in q:
        logs.append({
            "timestamp": _format_ts(now - timedelta(minutes=5)),
            "level": "ERROR",
            "service": "order-service",
            "instance": "pod-order-service-5c7d8e9f1-m3n2p",
            "message": "数据库连接池耗尽: Cannot acquire connection from pool, active: 50/50, waiting: 23, timeout: 30000ms",
            "metrics": {"error_type": "ConnectionPoolExhaustedException", "pool_active": "50"},
        })
        logs.append({
            "timestamp": _format_ts(now - timedelta(minutes=12)),
            "level": "FATAL",
            "service": "order-service",
            "instance": "pod-order-service-5c7d8e9f1-m3n2p",
            "message": "java.lang.OutOfMemoryError: Java heap space at com.example.order.service.OrderService.processLargeOrder(OrderService.java:156)",
            "metrics": {"error_type": "OutOfMemoryError", "heap_used": "3.9GB"},
        })
        for i in range(3):
            logs.append({
                "timestamp": _format_ts(now - timedelta(minutes=3 + i)),
                "level": "ERROR",
                "service": "user-service",
                "instance": "pod-user-service-8e9f0a1b2-k5j6h",
                "message": f"HTTP 500 Internal Server Error: /api/v1/users/profile, 耗时: {5200 + i * 300}ms, 错误: Database query timeout",
                "metrics": {"http_status": "500", "duration_ms": str(5200 + i * 300)},
            })

    if "slow" in q or "response_time" in q or ">3000" in q:
        for i in range(5):
            logs.append({
                "timestamp": _format_ts(now - timedelta(minutes=i * 2)),
                "level": "WARN",
                "service": "user-service",
                "instance": "pod-user-service-8e9f0a1b2-k5j6h",
                "message": f"慢请求警告: {'/api/v1/users/profile' if i % 2 == 0 else '/api/v1/users/orders'}, 响应时间: {4200 - i * 150}ms, 阈值: 3000ms",
                "metrics": {"response_time_ms": str(4200 - i * 150), "threshold_ms": "3000"},
            })

    return logs


def _build_db_slow_query_logs(now: datetime) -> list[dict]:
    """Build mock database slow query logs"""
    return [
        {
            "timestamp": _format_ts(now - timedelta(minutes=3)),
            "level": "WARN", "service": "mysql",
            "instance": "mysql-primary-01",
            "message": "慢查询: SELECT * FROM orders WHERE user_id = ? AND status IN (?, ?, ?) ORDER BY created_at DESC LIMIT 100, 执行时间: 3.2s, 扫描行数: 1,245,678",
            "metrics": {"query_time_sec": "3.2", "rows_examined": "1245678", "table": "orders"},
        },
        {
            "timestamp": _format_ts(now - timedelta(minutes=6)),
            "level": "WARN", "service": "mysql",
            "instance": "mysql-primary-01",
            "message": "慢查询: SELECT u.*, p.* FROM users u LEFT JOIN user_profiles p ON u.id = p.user_id WHERE u.last_login > ?, 执行时间: 2.8s, 全表扫描",
            "metrics": {"query_time_sec": "2.8", "rows_examined": "856234", "index_used": "NONE"},
        },
    ]


def _build_system_events_logs(now: datetime) -> list[dict]:
    """Build mock system event logs"""
    return [
        {
            "timestamp": _format_ts(now - timedelta(minutes=15)),
            "level": "WARN", "service": "kubernetes",
            "instance": "kube-controller-manager",
            "message": "Pod 重启事件: pod-order-service-5c7d8e9f1-m3n2p, 原因: OOMKilled, 容器退出码: 137, 重启次数: 3",
            "metrics": {"event_type": "PodRestart", "reason": "OOMKilled", "restart_count": "3"},
        },
        {
            "timestamp": _format_ts(now - timedelta(minutes=16)),
            "level": "ERROR", "service": "kernel",
            "instance": "node-worker-02",
            "message": "OOM Killer 触发: 进程 java (PID: 12345) 被杀死, 内存使用: 3.9GB, 内存限制: 4GB",
            "metrics": {"event_type": "OOMKill", "process": "java", "memory_used": "3.9GB"},
        },
    ]


@tool
def get_available_log_topics() -> str:
    """Get all available log topics and their descriptions. Call this tool first before querying logs to understand what log topics are available."""
    topics = [
        {
            "topic_name": "system-metrics",
            "description": "系统指标日志，包含 CPU、内存、磁盘使用率等系统资源监控数据",
            "example_queries": ["cpu_usage:>80", "memory_usage:>85", "level:WARN AND service:payment-service"],
            "related_alerts": ["HighCPUUsage", "HighMemoryUsage", "HighDiskUsage"],
        },
        {
            "topic_name": "application-logs",
            "description": "应用日志，包含应用程序的错误日志、警告日志、慢请求日志、下游依赖调用日志等",
            "example_queries": ["level:ERROR", "http_status:500", "response_time:>3000", "slow"],
            "related_alerts": ["ServiceUnavailable", "SlowResponse", "HighMemoryUsage"],
        },
        {
            "topic_name": "database-slow-query",
            "description": "数据库慢查询日志，包含执行时间较长的 SQL 查询，可用于分析数据库性能问题",
            "example_queries": ["query_time:>2", "table:orders"],
            "related_alerts": ["SlowResponse", "ServiceUnavailable"],
        },
        {
            "topic_name": "system-events",
            "description": "系统事件日志，包含 Kubernetes Pod 重启、OOM Kill、容器崩溃等系统级事件",
            "example_queries": ["restart OR crash", "oom_kill", "event_type:PodRestart"],
            "related_alerts": ["ServiceUnavailable", "HighMemoryUsage"],
        },
    ]
    output = {
        "success": True,
        "topics": topics,
        "available_regions": ["ap-guangzhou", "ap-shanghai", "ap-beijing", "ap-chengdu"],
        "default_region": "ap-guangzhou",
        "message": f"共有 {len(topics)} 个可用的日志主题",
    }
    return json.dumps(output, ensure_ascii=False, indent=2)


@tool
def query_logs(
    region: str = "ap-guangzhou",
    log_topic: str = "system-metrics",
    query: str = "",
    limit: int = 20,
) -> str:
    """
    Query logs from Cloud Log Service (CLS).
    Available log topics:
    1) 'system-metrics' - System metrics logs (CPU, memory, disk usage, etc.)
    2) 'application-logs' - Application logs (error logs, slow request logs, downstream dependency logs)
    3) 'database-slow-query' - Database slow query logs (SQL queries with long execution time)
    4) 'system-events' - System event logs (Pod restart, OOM Kill, container crash)
    """
    if not settings.cls_mock_enabled:
        # Try real Elasticsearch / Loki
        if settings.elasticsearch_url:
            try:
                es_url = f"{settings.elasticsearch_url}/{log_topic}/_search"
                body = {"query": {"match": {"message": query or "*"}}, "size": min(limit, 100)}
                resp = httpx.post(es_url, json=body, timeout=10)
                resp.raise_for_status()
                hits = resp.json().get("hits", {}).get("hits", [])
                logs = [{
                    "timestamp": h["_source"].get("@timestamp", ""),
                    "level": h["_source"].get("level", "INFO"),
                    "service": h["_source"].get("service", ""),
                    "message": h["_source"].get("message", ""),
                } for h in hits]
                return json.dumps({"success": True, "source": "elasticsearch", "logs": logs, "total": len(logs)}, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning("elasticsearch_query_failed: %s", e)

        if settings.loki_url:
            try:
                loki_url = f"{settings.loki_url}/loki/api/v1/query_range"
                params = {"query": f'{{job=~".*{log_topic}.*"}} |= `{query or ""}`', "limit": min(limit, 100)}
                resp = httpx.get(loki_url, params=params, timeout=10)
                resp.raise_for_status()
                streams = resp.json().get("data", {}).get("result", [])
                logs = []
                for s in streams:
                    for ts, line in s.get("values", []):
                        logs.append({"timestamp": ts, "message": line})
                return json.dumps({"success": True, "source": "loki", "logs": logs[:limit], "total": len(logs)}, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning("loki_query_failed: %s", e)

        return json.dumps({"success": False, "message": "真实日志系统未配置 (elasticsearch_url / loki_url)"}, ensure_ascii=False)

    actual_limit = min(max(limit, 1), 100)
    now = datetime.now(SHANGHAI_TZ)
    safe_topic = (log_topic or "system-metrics").lower()

    topic_handlers = {
        "system-metrics": _build_system_metrics_logs,
        "application-logs": _build_application_logs,
        "database-slow-query": lambda n, q: _build_db_slow_query_logs(n),
        "system-events": lambda n, q: _build_system_events_logs(n),
    }

    logs = topic_handlers.get(safe_topic, lambda n, q: [])(now, query)

    if not logs:
        logs = [{
            "timestamp": _format_ts(now),
            "level": "INFO",
            "service": "generic-service",
            "instance": "instance-0",
            "message": f"日志查询结果: topic={safe_topic}, query={query}",
            "metrics": {},
        }]

    logs = logs[:actual_limit]

    output = {
        "success": True,
        "region": region,
        "log_topic": safe_topic,
        "query": query or "DEFAULT_QUERY",
        "logs": logs,
        "total": len(logs),
        "message": f"成功查询到 {len(logs)} 条日志",
    }
    return json.dumps(output, ensure_ascii=False, indent=2)
