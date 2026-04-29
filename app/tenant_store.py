"""Tenant registry — JSON-backed API Key → Tenant + Role mapping.

Default config at .claude/tenants.json. If absent, all keys map to the default tenant.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger("superbizagent")

TENANT_CONFIG_PATH = Path(".claude/tenants.json")
DEFAULT_TENANT_ID = "default"


@dataclass
class TenantContext:
    tenant_id: str
    tenant_name: str
    role: str  # admin / operator / viewer


class TenantRegistry:
    def __init__(self):
        self._keys: dict[str, TenantContext] = {}
        self._tenants: dict[str, str] = {DEFAULT_TENANT_ID: "Default Tenant"}
        self.reload()

    def reload(self):
        self._keys.clear()
        if TENANT_CONFIG_PATH.exists():
            try:
                data = json.loads(TENANT_CONFIG_PATH.read_text(encoding="utf-8"))
                for tenant in data.get("tenants", []):
                    tid = tenant["id"]
                    name = tenant.get("name", tid)
                    self._tenants[tid] = name
                    for key_entry in tenant.get("keys", []):
                        key = key_entry["key"]
                        role = key_entry.get("role", "viewer")
                        self._keys[key] = TenantContext(
                            tenant_id=tid, tenant_name=name, role=role
                        )
            except Exception:
                logger.warning("tenant_config_parse_failed", exc_info=True)

        # Fallback: use API_KEYS env var to populate default tenant
        raw = [k.strip() for k in settings.api_keys.split(",") if k.strip()]
        for key in raw:
            if key not in self._keys:
                self._keys[key] = TenantContext(
                    tenant_id=DEFAULT_TENANT_ID,
                    tenant_name="Default Tenant",
                    role="admin",
                )

    def lookup(self, api_key: str) -> Optional[TenantContext]:
        return self._keys.get(api_key)

    @property
    def tenant_count(self) -> int:
        return len(self._tenants)

    @property
    def key_count(self) -> int:
        return len(self._keys)

    def get_tenant_name(self, tenant_id: str) -> str:
        return self._tenants.get(tenant_id, tenant_id)


tenant_registry = TenantRegistry()
