"""War Room — collaborative incident response workspace with shared timeline."""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("superbizagent")


@dataclass
class TimelineEvent:
    ts: float
    actor: str
    action: str
    detail: str = ""


@dataclass
class WarRoom:
    room_id: str
    incident_id: str
    title: str
    severity: str = "P1"
    created_at: float = field(default_factory=time.time)
    events: list[TimelineEvent] = field(default_factory=list)
    participants: set[str] = field(default_factory=set)
    annotations: list[dict] = field(default_factory=list)

    def add_event(self, actor: str, action: str, detail: str = ""):
        self.events.append(TimelineEvent(ts=time.time(), actor=actor, action=action, detail=detail))

    def add_annotation(self, user: str, note: str, event_index: int = -1):
        self.annotations.append({"user": user, "note": note, "event_idx": event_index, "ts": time.time()})

    def export_rca(self) -> str:
        lines = [f"# RCA Report: {self.title}", "", f"**Severity**: {self.severity}",
                 f"**Participants**: {', '.join(self.participants) or 'none'}", "",
                 "## Timeline", ""]
        for e in sorted(self.events, key=lambda x: x.ts):
            ts_str = time.strftime("%H:%M:%S", time.localtime(e.ts))
            lines.append(f"`{ts_str}` **{e.actor}**: {e.action}" + (f" — {e.detail}" if e.detail else ""))
        if self.annotations:
            lines.append("")
            lines.append("## Annotations")
            for a in self.annotations:
                lines.append(f"- **{a['user']}**: {a['note']}")
        return "\n".join(lines)


class WarRoomManager:
    def __init__(self):
        self._rooms: dict[str, WarRoom] = {}
        self._lock = asyncio.Lock()

    async def create(self, incident_id: str, title: str, severity: str = "P1") -> WarRoom:
        async with self._lock:
            room = WarRoom(
                room_id=str(uuid.uuid4())[:8],
                incident_id=incident_id,
                title=title,
                severity=severity,
            )
            self._rooms[room.room_id] = room
            return room

    async def get(self, room_id: str) -> Optional[WarRoom]:
        return self._rooms.get(room_id)

    async def close(self, room_id: str) -> Optional[str]:
        async with self._lock:
            room = self._rooms.pop(room_id, None)
            return room.export_rca() if room else None

    @property
    def active_count(self) -> int:
        return len(self._rooms)


warroom_manager = WarRoomManager()
