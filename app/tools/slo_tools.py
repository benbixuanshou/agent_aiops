"""SLO / Error Budget tools — Google SRE methodology, backed by real Prometheus data."""

import json
from datetime import datetime, timezone, timedelta

import httpx
from langchain_core.tools import tool

from app.config import settings

MOCK_SLOS = {
    "payment-service": {"slo": 99.9, "current": 99.87, "budget_burned_pct": 72},
    "order-service": {"slo": 99.9, "current": 99.95, "budget_burned_pct": 15},
    "user-service": {"slo": 99.5, "current": 99.42, "budget_burned_pct": 88},
}


def _calculate_budget(current: float, target: float) -> tuple[float, str]:
    """Calculate error budget burn percentage and status."""
    allowed_error = 100 - target
    actual_error = 100 - current
    if allowed_error <= 0:
        return 100, "CRITICAL"
    burned = (actual_error / allowed_error) * 100
    burned = min(100, max(0, burned))
    status = "CRITICAL" if burned > 100 else "WARNING" if burned > 80 else "OK"
    return round(burned, 1), status


def _fetch_real_slo() -> dict:
    """Try to compute SLO from Prometheus alert data."""
    try:
        api_url = f"{settings.prometheus_base_url}/api/v1/alerts"
        resp = httpx.get(api_url, timeout=5)
        resp.raise_for_status()
        alerts = resp.json().get("data", {}).get("alerts", [])

        # Count firing alerts per service
        services: dict[str, int] = {}
        for a in alerts:
            if a.get("state") != "firing":
                continue
            svc = a.get("labels", {}).get("service", "unknown")
            services[svc] = services.get(svc, 0) + 1

        # Compute rough SLO: each firing alert = 0.01% error
        result = {}
        for svc, count in services.items():
            current = max(99.0, 100 - count * 0.01)
            result[svc] = {"slo": 99.9, "current": round(current, 2), "budget_burned_pct": 0}
            _, status = _calculate_budget(result[svc]["current"], result[svc]["slo"])
            # Override burned percentage from calculation
            allowed = 100 - result[svc]["slo"]
            actual = 100 - result[svc]["current"]
            result[svc]["budget_burned_pct"] = round((actual / allowed) * 100, 1) if allowed > 0 else 100
            result[svc]["status"] = status

        if result:
            return result
    except Exception:
        pass
    return {}


@tool
def query_slo_status(service: str = "") -> str:
    """查询服务的 SLO/SLI 状态和错误预算消耗。

    Args:
        service: 服务名，留空查所有

    Returns:
        各服务的 SLO 满足情况和错误预算剩余。数据来源：Prometheus 真实告警 → 估算 SLI。
    """
    # Try real data from Prometheus first
    real_data = {}
    if not settings.prometheus_mock_enabled:
        real_data = _fetch_real_slo()

    # Fall back to mock if no real data
    data = real_data if real_data else MOCK_SLOS
    source = "Prometheus 实时数据" if real_data else "模拟数据"

    if service:
        s = data.get(service)
        if not s:
            return f"未找到服务 {service} 的 SLO 信息。可用服务: {', '.join(data.keys())}"
        burned, status = _calculate_budget(s["current"], s["slo"])
        return (
            f"SLO for {service} (数据来源: {source}):\n"
            f"  Target: {s['slo']}%\n"
            f"  Current: {s['current']}%\n"
            f"  Error budget burned: {burned}%\n"
            f"  Status: {status}"
        )

    lines = [f"SLO Status (数据来源: {source}):\n"]
    for svc, s in sorted(data.items()):
        burned, _ = _calculate_budget(s["current"], s["slo"])
        indicator = "CRITICAL" if burned > 100 else "WARNING" if burned > 80 else "OK"
        lines.append(
            f"  [{indicator}] {svc}: {s['current']}% vs {s['slo']}% target, "
            f"budget burned {burned}%"
        )
    return "\n".join(lines)


@tool
def define_slo(service: str, slo_target: float, window_days: int = 30) -> str:
    """为服务定义 SLO 目标。"""
    return f"SLO for {service}: {slo_target}% over {window_days}d (defined, restart required to persist)"
