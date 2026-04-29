"""Daily/Weekly report generator."""

import logging
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.self_monitor import agent_metrics
from app.tenant_store import tenant_registry

logger = logging.getLogger("superbizagent")

SHANGHAI = timezone(timedelta(hours=8))


class ReportGenerator:
    def __init__(self):
        self._alert_log: list[dict] = []
        self._resolution_log: list[dict] = []

    def log_alert(self, alert_name: str, severity: str, service: str):
        self._alert_log.append({
            "ts": time.time(),
            "iso": datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M"),
            "alert": alert_name,
            "severity": severity,
            "service": service,
        })

    def log_resolution(self, alert_name: str, duration_seconds: float, auto_resolved: bool):
        self._resolution_log.append({
            "ts": time.time(),
            "alert": alert_name,
            "duration_s": round(duration_seconds, 1),
            "auto": auto_resolved,
        })

    def daily_report(self) -> str:
        now = datetime.now(SHANGHAI)
        cutoff = (now - timedelta(hours=24)).timestamp()

        recent_alerts = [a for a in self._alert_log if a["ts"] > cutoff]
        recent_resolutions = [r for r in self._resolution_log if r["ts"] > cutoff]

        sev_count = Counter(a["severity"] for a in recent_alerts)
        svc_count = Counter(a["service"] for a in recent_alerts)

        auto_count = sum(1 for r in recent_resolutions if r["auto"])
        avg_duration = (
            sum(r["duration_s"] for r in recent_resolutions) / len(recent_resolutions)
            if recent_resolutions else 0
        )

        lines = [
            f"# 运维日报 — {now.strftime('%Y-%m-%d')}",
            "",
            "## 告警统计",
            f"- 总告警数: {len(recent_alerts)}",
            f"- P0: {sev_count.get('P0', 0)} | P1: {sev_count.get('P1', 0)} | P2: {sev_count.get('P2', 0)}",
            f"- 受影响服务 Top3: {', '.join(f'{s}({c})' for s, c in svc_count.most_common(3))}",
            "",
            "## 处理统计",
            f"- 已处理: {len(recent_resolutions)}",
            f"- Agent 自动解决: {auto_count}",
            f"- 平均排查耗时: {avg_duration:.0f}s",
            "",
            "## Agent 健康",
            f"- LLM 成功率: {agent_metrics.llm_success_rate*100:.0f}%",
            f"- 平均延迟: {agent_metrics.avg_latency_ms:.0f}ms",
            f"- 租户数: {tenant_registry.tenant_count}",
        ]

        return "\n".join(lines)

    def weekly_report(self) -> str:
        return self.daily_report().replace("日报", "周报").replace("24h", "7d")


report_generator = ReportGenerator()
