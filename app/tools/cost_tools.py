"""Cost anomaly detection — cloud resource / API cost monitoring."""

from langchain_core.tools import tool

MOCK_COSTS = {
    "payment-service": {"daily": 128.50, "weekly_avg": 115.20, "anomaly": False},
    "order-service": {"daily": 312.80, "weekly_avg": 210.00, "anomaly": True, "spike_pct": 49},
    "user-service": {"daily": 89.30, "weekly_avg": 92.50, "anomaly": False},
    "mysql": {"daily": 45.00, "weekly_avg": 45.00, "anomaly": False},
    "redis": {"daily": 22.00, "weekly_avg": 20.00, "anomaly": False},
    "cdn": {"daily": 67.20, "weekly_avg": 55.00, "anomaly": True, "spike_pct": 22},
}


@tool
def check_cost_anomaly(threshold_pct: float = 20) -> str:
    """检查云资源/API 费用异常波动。

    Args:
        threshold_pct: 异常检测阈值（超过周平均的百分比），默认 20%
    """
    lines = ["成本异常检测报告:\n"]
    anomalies = []
    total = 0
    for svc, c in MOCK_COSTS.items():
        total += c["daily"]
        if c.get("anomaly"):
            anomalies.append(f"  ⚠️ {svc}: {c['daily']:.1f}/day (周平均 {c['weekly_avg']:.1f}) +{c['spike_pct']}%")
        else:
            lines.append(f"  ✅ {svc}: {c['daily']:.1f}/day (正常)")

    lines.append(f"\n今日总成本: {total:.1f}")

    if anomalies:
        lines.append(f"\n⚠️ {len(anomalies)} 个服务费用异常:")
        lines.extend(anomalies)
        lines.append("\n建议: 检查异常服务是否有新版本发布、流量激增或 N+1 查询问题")
    else:
        lines.append("\n未发现费用异常")

    return "\n".join(lines)
