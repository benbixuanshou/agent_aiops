"""Runbook Engine — YAML DSL → DAG execution with human-in-the-loop."""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

logger = logging.getLogger("superbizagent")


@dataclass
class RunbookNode:
    type: str  # tool_call | llm_think | human_approval | notify
    name: str
    config: dict = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)


@dataclass
class Runbook:
    name: str
    version: str
    severity: str
    description: str = ""
    steps: list[RunbookNode] = field(default_factory=list)

    @staticmethod
    def from_yaml(path: Path) -> "Runbook":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        steps = [RunbookNode(**s) for s in data.get("steps", [])]
        return Runbook(
            name=data.get("name", path.stem),
            version=data.get("version", "1.0"),
            severity=data.get("severity", "P2"),
            description=data.get("description", ""),
            steps=steps,
        )


class RunbookEngine:
    """Executes runbooks as DAGs. Supports tool_call, llm_think, human_approval, notify nodes."""

    def __init__(self, tool_registry: dict[str, Callable] = None):
        self.tools = tool_registry or {}
        self._approvals: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, bool] = {}

    async def execute(self, runbook: Runbook, context: dict = None) -> dict:
        context = context or {}
        pending: list[RunbookNode] = list(runbook.steps)
        completed: set[str] = set()
        results: dict[str, Any] = {}

        while pending:
            ready = [n for n in pending if set(n.depends_on).issubset(completed)]
            if not ready:
                if pending:
                    logger.warning("runbook: deadlock detected, %d steps stuck", len(pending))
                break

            tasks = [self._execute_node(n, context) for n in ready]
            node_results = await asyncio.gather(*tasks, return_exceptions=True)

            for node, result in zip(ready, node_results):
                if isinstance(result, Exception):
                    logger.error("runbook: node %s failed: %s", node.name, result)
                    results[node.name] = {"error": str(result)}
                else:
                    results[node.name] = result
                completed.add(node.name)
                pending.remove(node)

        return results

    async def _execute_node(self, node: RunbookNode, context: dict) -> Any:
        if node.type == "tool_call":
            tool = self.tools.get(node.config.get("tool", ""))
            if tool:
                params = {**context, **node.config.get("params", {})}
                return await asyncio.to_thread(tool.invoke, params) if hasattr(tool, "invoke") else tool(**params)
            return {"error": f"tool not found: {node.config.get('tool')}"}

        if node.type == "human_approval":
            event = asyncio.Event()
            self._approvals[node.name] = event
            logger.info("runbook: waiting for approval [%s]: %s", node.name, node.config.get("prompt", ""))
            await event.wait()
            return {"approved": self._approval_results.get(node.name, False)}

        if node.type == "notify":
            logger.info("runbook: notify [%s]: %s", node.name, node.config.get("message", ""))
            return {"notified": True}

        if node.type == "llm_think":
            return {"analysis": f"Analyzed: {node.config.get('prompt', '')}"}

        return {"error": f"unknown node type: {node.type}"}

    def approve(self, node_name: str):
        self._approval_results[node_name] = True
        if node_name in self._approvals:
            self._approvals[node_name].set()

    def reject(self, node_name: str):
        self._approval_results[node_name] = False
        if node_name in self._approvals:
            self._approvals[node_name].set()


class RunbookLoader:
    def __init__(self, runbook_dir: str = ".claude/runbooks"):
        self.dir = Path(runbook_dir)

    def load_all(self) -> list[Runbook]:
        if not self.dir.exists():
            return []
        runbooks = []
        for f in sorted(self.dir.glob("*.yml")):
            try:
                runbooks.append(Runbook.from_yaml(f))
            except Exception:
                logger.warning("runbook_parse_failed: %s", f.name)
        return runbooks
