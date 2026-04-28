import logging

from langchain_core.tools import tool

from app.config import settings

logger = logging.getLogger("superbizagent")

MOCK_EVENTS = [
    {
        "namespace": "production",
        "resource": "payment-service-7d4f8b9c-abc12",
        "kind": "Pod",
        "reason": "OOMKilled",
        "message": "Container exceeded memory limit of 512Mi",
        "count": 3,
        "last_timestamp": "2026-04-28T10:15:00+08:00",
    },
    {
        "namespace": "production",
        "resource": "payment-service-7d4f8b9c-abc12",
        "kind": "Pod",
        "reason": "CrashLoopBackOff",
        "message": "Back-off restarting failed container",
        "count": 1,
        "last_timestamp": "2026-04-28T10:16:30+08:00",
    },
    {
        "namespace": "staging",
        "resource": "order-service-6c9d5f7b-def34",
        "kind": "Deployment",
        "reason": "FailedScheduling",
        "message": "0/3 nodes are available: 3 Insufficient memory",
        "count": 5,
        "last_timestamp": "2026-04-28T10:10:00+08:00",
    },
    {
        "namespace": "production",
        "resource": "redis-cache-5f8b7c9d-ghi56",
        "kind": "Pod",
        "reason": "ImagePullBackOff",
        "message": "Back-off pulling image 'redis:latest'",
        "count": 2,
        "last_timestamp": "2026-04-28T09:50:00+08:00",
    },
    {
        "namespace": "production",
        "resource": "nginx-ingress-3d2e1a4b-jkl78",
        "kind": "Pod",
        "reason": "Unhealthy",
        "message": "Readiness probe failed: Get http://10.0.1.5:8080/health: dial tcp 10.0.1.5:8080: connect: connection refused",
        "count": 8,
        "last_timestamp": "2026-04-28T10:18:00+08:00",
    },
]


@tool
def query_k8s_events(namespace: str = "production", resource: str = "") -> str:
    """查询 Kubernetes Events，排查 Pod/Deployment 异常。

    Args:
        namespace: 命名空间，默认 "production"，可用 "staging", "testing"
        resource: 可选，按资源名过滤（如 Pod 名、Deployment 名），留空查所有

    Returns:
        格式化的 K8s Events 信息
    """
    if settings.k8s_mock_enabled:
        events = [
            e for e in MOCK_EVENTS
            if e["namespace"] == namespace
        ]
        if resource:
            events = [e for e in events if resource in e["resource"]]

        if not events:
            return f"namespace={namespace}: no recent warning events found"

        lines = [f"K8s Events ({namespace}):\n"]
        for e in events:
            lines.append(
                f"  [{e['kind']}] {e['resource']}\n"
                f"    Reason: {e['reason']}\n"
                f"    Message: {e['message']}\n"
                f"    Count: {e['count']}, Last: {e['last_timestamp']}\n"
            )
        return "\n".join(lines)

    # Real K8s API path — plugin point for kubectl / k8s-python-client
    return "Real K8s API not configured. Set K8S_MOCK_ENABLED=true for mock data."


@tool
def get_k8s_namespaces() -> str:
    """获取可用的 Kubernetes 命名空间列表。"""
    if settings.k8s_mock_enabled:
        return "Available namespaces: production, staging, testing"
    return "Real K8s API not configured."
