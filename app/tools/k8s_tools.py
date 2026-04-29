import json
import logging
import os

import httpx
from langchain_core.tools import tool

from app.config import settings

logger = logging.getLogger("superbizagent")


def _get_k8s_headers() -> dict | None:
    """Try to load K8s auth from kubeconfig or in-cluster service account."""
    token = settings.k8s_api_token
    if token:
        return {"Authorization": f"Bearer {token}"}
    # Try in-cluster service account
    sa_token = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    if os.path.exists(sa_token):
        with open(sa_token) as f:
            return {"Authorization": f"Bearer {f.read().strip()}"}
    # Try kubeconfig
    kubeconfig = os.path.expanduser("~/.kube/config")
    if os.path.exists(kubeconfig):
        return {"X-Kubeconfig": kubeconfig}
    return None


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
    # Try real K8s API first
    if not settings.k8s_mock_enabled:
        headers = _get_k8s_headers()
        base = settings.k8s_api_url
        if headers and base:
            try:
                url = f"{base}/api/v1/namespaces/{namespace}/events"
                params = {"fieldSelector": "type=Warning"}
                if resource:
                    params["fieldSelector"] += f",involvedObject.name={resource}"
                resp = httpx.get(url, headers=headers, params=params,
                                 verify=settings.k8s_verify_ssl, timeout=10)
                resp.raise_for_status()
                items = resp.json().get("items", [])
                if not items:
                    return f"namespace={namespace}: no recent warning events found (real K8s API)"
                lines = [f"K8s Events ({namespace}, real API):\n"]
                for ev in items[:10]:
                    obj = ev.get("involvedObject", {})
                    lines.append(
                        f"  [{obj.get('kind', '')}] {obj.get('name', '')}\n"
                        f"    Reason: {ev.get('reason', '')}\n"
                        f"    Message: {ev.get('message', '')[:200]}\n"
                        f"    Count: {ev.get('count', 1)}, Last: {ev.get('lastTimestamp', '')}\n"
                    )
                return "\n".join(lines)
            except Exception as e:
                logger.warning("k8s_real_api_failed: %s, falling back to mock", e)

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
