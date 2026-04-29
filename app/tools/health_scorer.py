"""Service health scoring — multi-dimensional score (latency, error rate, saturation)."""

import random
from langchain_core.tools import tool

MOCK_SERVICES = {
    "payment-service": {"latency_p99": 220, "error_rate": 0.012, "saturation": 0.72, "qps": 450},
    "order-service": {"latency_p99": 350, "error_rate": 0.005, "saturation": 0.65, "qps": 320},
    "user-service": {"latency_p99": 180, "error_rate": 0.003, "saturation": 0.55, "qps": 280},
    "notification-service": {"latency_p99": 120, "error_rate": 0.001, "saturation": 0.35, "qps": 150},
}


def _score_service(name: str, metrics: dict) -> dict:
    latency_score = max(0, 100 - metrics["latency_p99"] / 10)
    error_score = max(0, 100 - metrics["error_rate"] * 10000)
    sat_score = max(0, 100 - metrics["saturation"] * 100)
    overall = round((latency_score * 0.4 + error_score * 0.35 + sat_score * 0.25), 1)
    return {
        "name": name,
        "overall": overall,
        "latency_score": round(latency_score, 1),
        "error_score": round(error_score, 1),
        "sat_score": round(sat_score, 1),
        "grade": "A" if overall >= 90 else "B" if overall >= 75 else "C" if overall >= 60 else "D",
    }


@tool
def score_service_health(service: str = "") -> str:
    """查询服务健康评分（0-100，多维度加权）。

    Args:
        service: 服务名，留空查全部
    """
    if service and service in MOCK_SERVICES:
        s = _score_service(service, MOCK_SERVICES[service])
        return (
            f"服务健康评分: {s['name']}\n"
            f"  总分: {s['overall']} ({s['grade']})\n"
            f"  延迟 P99: {MOCK_SERVICES[service]['latency_p99']}ms → {s['latency_score']}/40\n"
            f"  错误率: {MOCK_SERVICES[service]['error_rate']:.2%} → {s['error_score']}/35\n"
            f"  饱和度: {MOCK_SERVICES[service]['saturation']:.0%} → {s['sat_score']}/25"
        )

    scores = [_score_service(k, v) for k, v in MOCK_SERVICES.items()]
    scores.sort(key=lambda x: x["overall"], reverse=True)

    lines = [f"{'服务':<22} {'总分':>5} {'等级':>4}"]
    lines.append("-" * 35)
    for s in scores:
        emoji = "🟢" if s["grade"] == "A" else "🟡" if s["grade"] == "B" else "🔴"
        lines.append(f"{s['name']:<22} {s['overall']:>5.1f} {s['grade']:>4} {emoji}")
    return "\n".join(lines)
