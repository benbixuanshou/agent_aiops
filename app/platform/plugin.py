"""Plugin SDK — standardized interface for third-party tool/skill extensions.

A plugin is a Python module or directory with:
  - A `register()` function that returns a list of @tool-decorated functions
  - Optional `SKILL.md` for progressive disclosure
"""

import importlib
import logging
from pathlib import Path

logger = logging.getLogger("superbizagent")

PLUGIN_DIR = Path(".claude/plugins")


class PluginRegistry:
    def __init__(self):
        self._tools: dict[str, callable] = {}

    def discover(self):
        if not PLUGIN_DIR.exists():
            return
        for plugin_dir in PLUGIN_DIR.iterdir():
            if not plugin_dir.is_dir():
                continue
            try:
                spec = importlib.util.spec_from_file_location(
                    plugin_dir.name, plugin_dir / "__init__.py"
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    if hasattr(mod, "register"):
                        tools = mod.register()
                        for t in tools:
                            self._tools[t.name] = t
                        logger.info("plugin_loaded: %s (%d tools)", plugin_dir.name, len(tools))
            except Exception:
                logger.warning("plugin_load_failed: %s", plugin_dir.name)

    def get_all(self) -> dict[str, callable]:
        return dict(self._tools)


plugin_registry = PluginRegistry()
