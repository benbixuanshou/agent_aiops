"""Self-monitoring — Agent health metrics, LLM call success rate, self-throttle."""

import logging
import time
from collections import defaultdict

from app.config import settings

logger = logging.getLogger("superbizagent")


class AgentMetrics:
    """Tracks Agent health: LLM call success rate, avg latency, tool failures."""

    def __init__(self):
        self.llm_calls: int = 0
        self.llm_failures: int = 0
        self.total_latency_ms: float = 0.0
        self.tool_calls: int = 0
        self.tool_failures: int = 0
        self._alert_storm_count: int = 0
        self._last_alert_time: float = 0

    def record_llm_success(self, latency_ms: float):
        self.llm_calls += 1
        self.total_latency_ms += latency_ms

    def record_llm_failure(self):
        self.llm_failures += 1

    def record_tool_success(self):
        self.tool_calls += 1

    def record_tool_failure(self):
        self.tool_calls += 1
        self.tool_failures += 1

    def record_alert(self):
        now = time.time()
        if now - self._last_alert_time < 10:
            self._alert_storm_count += 1
        else:
            self._alert_storm_count = 1
        self._last_alert_time = now

    @property
    def is_alert_storm(self) -> bool:
        return self._alert_storm_count > 10

    @property
    def llm_success_rate(self) -> float:
        total = self.llm_calls + self.llm_failures
        if total == 0:
            return 1.0
        return self.llm_calls / total

    @property
    def avg_latency_ms(self) -> float:
        if self.llm_calls == 0:
            return 0
        return self.total_latency_ms / self.llm_calls

    def health_report(self) -> dict:
        return {
            "llm_success_rate": round(self.llm_success_rate, 4),
            "llm_avg_latency_ms": round(self.avg_latency_ms, 1),
            "llm_calls": self.llm_calls,
            "llm_failures": self.llm_failures,
            "tool_calls": self.tool_calls,
            "tool_failures": self.tool_failures,
            "alert_storm": self.is_alert_storm,
        }

    def throttle(self) -> bool:
        """Return True if we should throttle (alert storm + low LLM health)."""
        return self.is_alert_storm or self.llm_success_rate < 0.5


agent_metrics = AgentMetrics()
