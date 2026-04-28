"""SLO / Error Budget tools — Google SRE methodology."""

from langchain_core.tools import tool

MOCK_SLOS = {
    "payment-service": {"slo": 99.9, "current": 99.87, "budget_burned_pct": 72},
    "order-service": {"slo": 99.9, "current": 99.95, "budget_burned_pct": 15},
    "user-service": {"slo": 99.5, "current": 99.42, "budget_burned_pct": 88},
}


@tool
def query_slo_status(service: str = "") -> str:
    """查询服务的 SLO/SLI 状态和错误预算消耗。

    Args:
        service: 服务名，留空查所有

    Returns:
        各服务的 SLO 满足情况和错误预算剩余
    """
    if service:
        s = MOCK_SLOS.get(service)
        if not s:
            return f"未找到服务 {service} 的 SLO 定义"
        return (
            f"SLO for {service}:\n"
            f"  Target: {s['slo']}%\n"
            f"  Current: {s['current']}%\n"
            f"  Error budget burned: {s['budget_burned_pct']}%\n"
            f"  Status: {'CRITICAL' if s['budget_burned_pct'] > 80 else 'OK'}"
        )

    lines = ["SLO Status:\n"]
    for svc, s in MOCK_SLOS.items():
        flag = "🔴" if s["budget_burned_pct"] > 80 else "🟢"
        lines.append(
            f"  {flag} {svc}: {s['current']}% vs {s['slo']}% target, "
            f"budget burned {s['budget_burned_pct']}%"
        )
    return "\n".join(lines)


@tool
def define_slo(service: str, slo_target: float, window_days: int = 30) -> str:
    """为服务定义 SLO 目标。

    Args:
        service: 服务名
        slo_target: SLO 百分比，如 99.9
        window_days: 评估窗口天数
    """
    return f"SLO for {service}: {slo_target}% over {window_days}d (defined, restart required to persist)"
