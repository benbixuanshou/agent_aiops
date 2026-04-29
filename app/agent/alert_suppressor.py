"""Alert Suppressor — noise reduction engine.

Rules:
1. Maintenance windows — silence known alerts during planned work
2. Dependency chain suppression — if upstream is down, suppress downstream cascade
3. Duplicate folding — same alert firing repeatedly within a window → fold into one
4. Low-severity auto-silence — P2 alerts from non-critical services → log only
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger("superbizagent")

DEFAULT_MAINT_WINDOWS_PATH = Path(".claude/maintenance_windows.yml")

SILENCEABLE_DEPENDENCIES = {
    "payment-service": ["order-service", "notification-service"],
    "mysql": ["payment-service", "order-service", "user-service"],
    "redis": ["payment-service", "user-service"],
    "nginx": ["payment-service", "order-service", "user-service"],
}


@dataclass
class SuppressionRule:
    alertname: str
    service: str
    namespace: str
    reason: str


@dataclass
class MaintenanceWindow:
    start: float
    end: float
    services: list[str]
    alerts: list[str]
    reason: str

    def active(self) -> bool:
        now = time.time()
        return self.start <= now <= self.end


class AlertSuppressor:
    """Decides whether an alert should be suppressed."""

    def __init__(self):
        self._alert_counters: dict[str, list[float]] = {}
        self._maintenance_windows: list[MaintenanceWindow] = []
        self._load_maintenance_windows()

    def _load_maintenance_windows(self):
        if not DEFAULT_MAINT_WINDOWS_PATH.exists():
            return
        try:
            data = yaml.safe_load(DEFAULT_MAINT_WINDOWS_PATH.read_text(encoding="utf-8"))
            for w in data.get("windows", []):
                self._maintenance_windows.append(MaintenanceWindow(
                    start=w.get("start", 0),
                    end=w.get("end", 0),
                    services=w.get("services", []),
                    alerts=w.get("alerts", []),
                    reason=w.get("reason", ""),
                ))
        except Exception:
            logger.warning("suppressor: failed to load maintenance windows")

    def should_suppress(self, alert: dict, active_alerts: list[dict]) -> Optional[str]:
        """Returns None if alert should fire, or a reason string if suppressed."""

        # Rule 1: Maintenance window
        reason = self._check_maintenance(alert)
        if reason:
            return reason

        # Rule 2: Dependency chain suppression
        reason = self._check_dependency_chain(alert, active_alerts)
        if reason:
            return reason

        # Rule 3: Duplicate folding
        reason = self._check_duplicate(alert)
        if reason:
            return reason

        # Rule 4: Low-severity auto-silence
        reason = self._check_low_severity(alert)
        if reason:
            return reason

        return None

    def _check_maintenance(self, alert: dict) -> Optional[str]:
        labels = alert.get("labels", {})
        svc = labels.get("service", "")
        name = labels.get("alertname", "")
        for w in self._maintenance_windows:
            if not w.active():
                continue
            if svc in w.services or name in w.alerts:
                return f"maintenance window: {w.reason}"
        return None

    def _check_dependency_chain(self, alert: dict, active_alerts: list[dict]) -> Optional[str]:
        labels = alert.get("labels", {})
        svc = labels.get("service", "")
        for upstream, downstreams in SILENCEABLE_DEPENDENCIES.items():
            if svc in downstreams:
                upstream_down = any(
                    a.get("labels", {}).get("service") == upstream
                    and a.get("status") == "firing"
                    for a in active_alerts
                )
                if upstream_down:
                    return f"upstream {upstream} is down, suppressing cascade on {svc}"
        return None

    def _check_duplicate(self, alert: dict) -> Optional[str]:
        key = alert.get("fingerprint") or alert.get("labels", {}).get("alertname", "")
        if not key:
            return None
        now = time.time()
        self._alert_counters.setdefault(key, [])
        self._alert_counters[key] = [
            t for t in self._alert_counters[key] if now - t < 300
        ]
        if len(self._alert_counters[key]) >= 5:
            return f"duplicate suppressed (fired {len(self._alert_counters[key])}x in 5min)"
        self._alert_counters[key].append(now)
        return None

    def _check_low_severity(self, alert: dict) -> Optional[str]:
        labels = alert.get("labels", {})
        sev = labels.get("severity", "")
        svc = labels.get("service", "")
        non_critical = {"notification-service", "log-collector", "batch-job"}
        if sev in ("info", "low", "P2") and svc in non_critical:
            return f"low severity on non-critical service {svc}, logging only"
        return None


alert_suppressor = AlertSuppressor()
