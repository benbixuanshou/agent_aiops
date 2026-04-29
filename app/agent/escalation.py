"""Smart alert escalation — auto-upgrade if unacknowledged."""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("superbizagent")

ESCALATION_POLICY = {
    "P2": {"timeout_minutes": 30, "upgrade_to": "P1", "notify": "team-lead"},
    "P1": {"timeout_minutes": 10, "upgrade_to": "P0", "notify": "oncall-primary"},
    "P0": {"timeout_minutes": 5, "upgrade_to": "P0_ESCALATED", "notify": "manager"},
}


@dataclass
class EscalationState:
    incident_id: str
    severity: str
    created_at: float
    acknowledged: bool = False
    acknowledged_by: str = ""
    escalated_at: float = 0
    escalated_to: str = ""


class EscalationEngine:
    """Tracks alert acknowledgements and auto-escalates if nobody responds."""

    def __init__(self):
        self._states: dict[str, EscalationState] = {}

    def register(self, incident_id: str, severity: str = "P2"):
        self._states[incident_id] = EscalationState(
            incident_id=incident_id,
            severity=severity,
            created_at=time.time(),
        )

    def acknowledge(self, incident_id: str, user: str = "unknown"):
        state = self._states.get(incident_id)
        if state:
            state.acknowledged = True
            state.acknowledged_by = user

    def check(self) -> list[dict]:
        """Returns list of incidents that need escalation."""
        now = time.time()
        escalations = []
        for inc_id, state in list(self._states.items()):
            if state.acknowledged:
                continue
            policy = ESCALATION_POLICY.get(state.severity)
            if not policy:
                continue
            elapsed_minutes = (now - state.created_at) / 60
            if elapsed_minutes >= policy["timeout_minutes"] and not state.escalated_at:
                state.escalated_at = now
                state.escalated_to = policy["notify"]
                escalations.append({
                    "incident_id": inc_id,
                    "severity": state.severity,
                    "escalated_to": policy["upgrade_to"],
                    "notify": policy["notify"],
                    "elapsed_minutes": round(elapsed_minutes, 1),
                })
        return escalations

    def cleanup(self, max_age_hours: int = 24):
        now = time.time()
        stale = [
            iid for iid, s in self._states.items()
            if now - s.created_at > max_age_hours * 3600
        ]
        for iid in stale:
            del self._states[iid]


escalation_engine = EscalationEngine()
