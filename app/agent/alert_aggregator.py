"""Alert aggregation engine: merge related alerts into incidents."""

import time
from dataclasses import dataclass, field


@dataclass
class Incident:
    incident_id: str
    alerts: list[dict] = field(default_factory=list)
    severity: str = "P2"
    summary: str = ""
    started_at: float = 0.0
    affected_services: set[str] = field(default_factory=set)
    root_cause_candidates: list[str] = field(default_factory=list)


class AlertAggregator:
    """Merge related alerts into incidents based on tags + time window."""

    def __init__(self, window_seconds: int = 300):
        self.window = window_seconds
        self._incidents: dict[str, Incident] = {}

    def aggregate(self, alerts: list[dict]) -> list[Incident]:
        """Group alerts into incidents. Returns sorted (P0 first)."""
        if not alerts:
            return []

        now = time.time()
        firing = [a for a in alerts if a.get("status") == "firing"]

        for alert in firing:
            key = self._group_key(alert)

            if key in self._incidents:
                inc = self._incidents[key]
                last_ts = self._parse_ts(alert)
                if last_ts and (now - last_ts) < self.window:
                    inc.alerts.append(alert)
                    inc.affected_services.add(self._service(alert))
                    self._update_severity(inc, alert)
                else:
                    self._incidents[key] = self._new_incident(alert)
            else:
                self._incidents[key] = self._new_incident(alert)

        return sorted(self._incidents.values(), key=lambda i: self._severity_order(i.severity))

    def clear_stale(self):
        now = time.time()
        stale = [
            k for k, i in self._incidents.items()
            if now - i.started_at > self.window * 2
        ]
        for k in stale:
            del self._incidents[k]

    @staticmethod
    def _group_key(alert: dict) -> str:
        labels = alert.get("labels", {})
        ns = labels.get("namespace", "")
        svc = labels.get("service", "")
        rule = labels.get("alertname", "")
        return f"{ns}/{svc}/{rule}"

    @staticmethod
    def _service(alert: dict) -> str:
        return alert.get("labels", {}).get("service", "unknown")

    @staticmethod
    def _parse_ts(alert: dict) -> float | None:
        ts = alert.get("startsAt", "")
        if not ts:
            return None
        try:
            from datetime import datetime
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except Exception:
            return None

    def _update_severity(self, incident: Incident, alert: dict):
        sev = alert.get("labels", {}).get("severity", "")
        if sev == "critical":
            incident.severity = "P0"
        elif sev == "warning" and incident.severity != "P0":
            incident.severity = "P1"

    def _new_incident(self, alert: dict) -> Incident:
        import uuid
        sev = alert.get("labels", {}).get("severity", "")
        severity = "P0" if sev == "critical" else "P1" if sev == "warning" else "P2"
        names = []
        for a in [alert]:
            n = a.get("labels", {}).get("alertname") or a.get("annotations", {}).get("summary", "unknown")
            names.append(n)
        inc = Incident(
            incident_id=str(uuid.uuid4())[:8],
            alerts=[alert],
            severity=severity,
            summary=f"Incident: {', '.join(names)}",
            started_at=time.time(),
            affected_services={self._service(alert)},
        )
        return inc

    @staticmethod
    def _severity_order(sev: str) -> int:
        return {"P0": 0, "P1": 1, "P2": 2}.get(sev, 3)
