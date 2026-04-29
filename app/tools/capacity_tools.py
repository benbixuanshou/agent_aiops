"""Capacity prediction — forecast resource exhaustion based on trends."""

from langchain_core.tools import tool

MOCK_TRENDS = {
    "payment-service": {"cpu_trend": 2.1, "memory_trend": 1.8, "disk_trend": 0.5, "current_cpu": 72, "current_mem": 68, "current_disk": 45},
    "order-service": {"cpu_trend": 3.5, "memory_trend": 4.2, "disk_trend": 0.8, "current_cpu": 65, "current_mem": 78, "current_disk": 52},
    "user-service": {"cpu_trend": 0.8, "memory_trend": 0.5, "disk_trend": 0.3, "current_cpu": 35, "current_mem": 42, "current_disk": 38},
    "mysql": {"cpu_trend": 1.2, "memory_trend": 1.0, "disk_trend": 3.2, "current_cpu": 55, "current_mem": 60, "current_disk": 68},
}


def _days_until(threshold: float, current: float, trend_pct_per_day: float) -> str:
    if trend_pct_per_day <= 0:
        return "稳定（无增长趋势）"
    remaining = threshold - current
    if remaining <= 0:
        return f"已超过 {threshold}% 阈值"
    days = remaining / trend_pct_per_day
    if days > 365:
        return f"{int(days)} 天后"
    if days > 30:
        return f"{int(days / 30)} 个月后"
    if days > 7:
        return f"{int(days / 7)} 周后"
    return f"{int(days)} 天后"


@tool
def predict_capacity(service: str = "") -> str:
    """基于 30 天趋势预测容量瓶颈，估算扩容时机。

    Args:
        service: 服务名，留空显示全部
    """
    if service and service in MOCK_TRENDS:
        t = MOCK_TRENDS[service]
        lines = [f"容量预测 — {service}:\n"]
        lines.append(f"  CPU:     {t['current_cpu']}% → 80% 阈值 {_days_until(80, t['current_cpu'], t['cpu_trend'])}")
        lines.append(f"  Memory:  {t['current_mem']}% → 85% 阈值 {_days_until(85, t['current_mem'], t['memory_trend'])}")
        lines.append(f"  Disk:    {t['current_disk']}% → 80% 阈值 {_days_until(80, t['current_disk'], t['disk_trend'])}")
        return "\n".join(lines)

    lines = ["容量预测报告（基于 30 天趋势）:\n"]
    lines.append(f"{'服务':<20} {'CPU趋势':>8} {'Mem趋势':>8} {'Disk趋势':>8} {'预警'}")
    lines.append("-" * 56)
    for svc, t in MOCK_TRENDS.items():
        urgency = "🔴" if any(v > 3 for v in [t["cpu_trend"], t["memory_trend"]]) else "🟡" if any(v > 1.5 for v in [t["cpu_trend"], t["memory_trend"]]) else "🟢"
        lines.append(f"{svc:<20} {t['cpu_trend']:>6.1f}%/d {t['memory_trend']:>6.1f}%/d {t['disk_trend']:>6.1f}%/d {urgency:>4}")

    lines.append("\n建议: 🔴 需本周扩容 | 🟡 纳入下月计划 | 🟢 当前安全")
    return "\n".join(lines)
