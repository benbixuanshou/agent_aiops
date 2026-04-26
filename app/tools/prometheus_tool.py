import json
import random
from datetime import datetime, timezone, timedelta
from typing import Optional
from langchain.tools import tool
import httpx

from app.config import settings


def _calculate_duration(active_at_str: str) -> str:
    """Calculate duration from active_at to now"""
    try:
        active_at = datetime.fromisoformat(active_at_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - active_at
        total_seconds = int(delta.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours}h{minutes}m{seconds}s"
        elif minutes > 0:
            return f"{minutes}m{seconds}s"
        else:
            return f"{seconds}s"
    except Exception:
        return "unknown"


def _build_mock_alerts() -> list[dict]:
    """Build mock alert data matching Java QueryMetricsTools.buildMockAlerts()"""
    now = datetime.now(timezone.utc)

    alerts = [
        {
            "alert_name": "HighCPUUsage",
            "description": "服务 payment-service 的 CPU 使用率持续超过 80%，当前值为 92%。实例: pod-payment-service-7d8f9c6b5-x2k4m，命名空间: production",
            "state": "firing",
            "active_at": (now - timedelta(minutes=25)).isoformat(),
        },
        {
            "alert_name": "HighMemoryUsage",
            "description": "服务 order-service 的内存使用率持续超过 85%，当前值为 91%。JVM堆内存使用: 3.8GB/4GB，可能存在内存泄漏风险。实例: pod-order-service-5c7d8e9f1-m3n2p，命名空间: production",
            "state": "firing",
            "active_at": (now - timedelta(minutes=15)).isoformat(),
        },
        {
            "alert_name": "SlowResponse",
            "description": "服务 user-service 的 P99 响应时间持续超过 3 秒，当前值为 4.2 秒。受影响接口: /api/v1/users/profile, /api/v1/users/orders。可能原因：数据库慢查询或下游服务延迟",
            "state": "firing",
            "active_at": (now - timedelta(minutes=10)).isoformat(),
        },
    ]

    for alert in alerts:
        alert["duration"] = _calculate_duration(alert["active_at"])

    return alerts


@tool
def query_prometheus_alerts() -> str:
    """
    Query active alerts from Prometheus alerting system.
    This tool retrieves all currently active/firing alerts including their labels, annotations, state, and values.
    Use this tool when you need to check what alerts are currently firing, investigate alert conditions, or monitor alert status.
    """
    try:
        if settings.prometheus_mock_enabled:
            mock_alerts = _build_mock_alerts()
            output = {
                "success": True,
                "alerts": mock_alerts,
                "message": f"成功检索到 {len(mock_alerts)} 个活动告警",
            }
            return json.dumps(output, ensure_ascii=False, indent=2)

        # Real mode: call Prometheus API
        api_url = f"{settings.prometheus_base_url}/api/v1/alerts"
        response = httpx.get(api_url, timeout=settings.prometheus_timeout)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "success":
            return json.dumps({"success": False, "message": "Prometheus API returned non-success status"}, ensure_ascii=False)

        # Deduplicate by alertname (keep first)
        seen_names = set()
        simplified = []
        for alert in data.get("data", {}).get("alerts", []):
            labels = alert.get("labels", {})
            alert_name = labels.get("alertname", "")
            if alert_name in seen_names:
                continue
            seen_names.add(alert_name)

            simplified.append({
                "alert_name": alert_name,
                "description": alert.get("annotations", {}).get("description", ""),
                "state": alert.get("state", ""),
                "active_at": alert.get("activeAt", ""),
                "duration": _calculate_duration(alert.get("activeAt", "")),
            })

        output = {
            "success": True,
            "alerts": simplified,
            "message": f"成功检索到 {len(simplified)} 个活动告警",
        }
        return json.dumps(output, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"success": False, "message": f"查询失败: {str(e)}"}, ensure_ascii=False, indent=2)
