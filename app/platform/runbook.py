"""Runbook Engine — YAML DSL for defining incident response workflows.

Nodes: tool_call | llm_think | human_approval | notify
Version controlled via Git. Executed as a DAG.
"""

import logging
import yaml
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("superbizagent")


@dataclass
class RunbookNode:
    type: str  # tool_call, llm_think, human_approval, notify
    name: str
    config: dict
    depends_on: list[str] | None = None


@dataclass
class Runbook:
    name: str
    version: str
    severity: str  # P0/P1/P2
    description: str
    steps: list[RunbookNode]


class RunbookLoader:
    def __init__(self, runbook_dir: str = ".claude/runbooks"):
        self.dir = Path(runbook_dir)

    def load_all(self) -> list[Runbook]:
        if not self.dir.exists():
            return []
        runbooks = []
        for f in sorted(self.dir.glob("*.yml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                steps = [RunbookNode(**s) for s in data.get("steps", [])]
                runbooks.append(Runbook(
                    name=data.get("name", f.stem),
                    version=data.get("version", "1.0"),
                    severity=data.get("severity", "P2"),
                    description=data.get("description", ""),
                    steps=steps,
                ))
            except Exception:
                logger.warning("runbook_parse_failed: %s", f.name)
        return runbooks
