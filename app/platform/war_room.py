"""War Room — collaborative incident response workspace.

P0 incidents trigger auto-War Room creation with shared timeline and multi-user annotation.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("superbizagent")


@dataclass
class WarRoomEvent:
    ts: float
    actor: str  # "agent" or username
    action: str
    detail: str = ""


@dataclass
class WarRoom:
    room_id: str
    incident_id: str
    title: str
    created_at: float = field(default_factory=time.time)
    events: list[WarRoomEvent] = field(default_factory=list)
    participants: set[str] = field(default_factory=set)

    def add_event(self, actor: str, action: str, detail: str = ""):
        self.events.append(WarRoomEvent(ts=time.time(), actor=actor, action=action, detail=detail))

    def add_participant(self, user: str):
        self.participants.add(user)

    def export_timeline(self) -> str:
        lines = [f"# War Room Timeline: {self.title}\n"]
        for e in sorted(self.events, key=lambda x: x.ts):
            ts_str = time.strftime("%H:%M:%S", time.localtime(e.ts))
            lines.append(f"[{ts_str}] {e.actor}: {e.action}" + (f" — {e.detail}" if e.detail else ""))
        return "\n".join(lines)


class WarRoomManager:
    """Manages active War Rooms."""

    def __init__(self):
        self._rooms: dict[str, WarRoom] = {}

    def create(self, incident_id: str, title: str) -> WarRoom:
        room = WarRoom(room_id=str(uuid.uuid4())[:8], incident_id=incident_id, title=title)
        self._rooms[room.room_id] = room
        return room

    def get(self, room_id: str) -> WarRoom | None:
        return self._rooms.get(room_id)

    def close(self, room_id: str) -> WarRoom | None:
        return self._rooms.pop(room_id, None)


war_room_manager = WarRoomManager()
