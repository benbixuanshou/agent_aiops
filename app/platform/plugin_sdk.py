"""Plugin SDK — standardized interface for third-party tool extensions.

A plugin is a Python module or directory with a `register()` function that
returns a list of @tool-decorated callables. Optional `SKILL.md` for discovery.
"""

import importlib.util
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("superbizagent")

PLUGIN_DIR = Path(".claude/plugins")


@dataclass
class PluginInfo:
    name: str
    version: str = "1.0"
    tools: list[Callable] = field(default_factory=list)
    skill_path: Optional[Path] = None


class PluginRegistry:
    """Discovers and manages third-party plugins from .claude/plugins/."""

    def __init__(self):
        self._plugins: dict[str, PluginInfo] = {}
        self._tools: dict[str, Callable] = {}

    def discover(self):
        if not PLUGIN_DIR.exists():
            PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
            return

        for plugin_dir in sorted(PLUGIN_DIR.iterdir()):
            if not plugin_dir.is_dir():
                continue
            self._load_plugin(plugin_dir)

    def _load_plugin(self, plugin_dir: Path):
        name = plugin_dir.name
        try:
            init_py = plugin_dir / "__init__.py"
            if not init_py.exists():
                logger.info("plugin_skip: %s (no __init__.py)", name)
                return

            spec = importlib.util.spec_from_file_location(name, init_py)
            if not spec or not spec.loader:
                return

            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            if not hasattr(mod, "register"):
                logger.info("plugin_skip: %s (no register() function)", name)
                return

            tools = mod.register()
            if not isinstance(tools, list):
                return

            info = PluginInfo(name=name)
            for t in tools:
                tool_name = getattr(t, "name", str(t))
                self._tools[tool_name] = t
                info.tools.append(t)

            skill_md = plugin_dir / "SKILL.md"
            if skill_md.exists():
                info.skill_path = skill_md

            self._plugins[name] = info
            logger.info("plugin_loaded: %s (%d tools)", name, len(tools))

        except Exception:
            logger.warning("plugin_load_failed: %s", name, exc_info=True)

    def get_all_tools(self) -> list[Callable]:
        return list(self._tools.values())

    def get_plugin(self, name: str) -> Optional[PluginInfo]:
        return self._plugins.get(name)

    @property
    def loaded_plugins(self) -> list[str]:
        return list(self._plugins.keys())


plugin_registry = PluginRegistry()
