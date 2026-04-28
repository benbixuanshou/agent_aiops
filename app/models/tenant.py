"""Multi-tenant model — data isolation per tenant."""

from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


@dataclass
class Tenant:
    tenant_id: str
    name: str
    api_keys: list[str] = field(default_factory=list)

    @staticmethod
    def default():
        return Tenant(tenant_id="default", name="Default Tenant")


@dataclass
class TenantUser:
    user_id: str
    tenant_id: str
    role: Role = Role.VIEWER
    api_key: str = ""

    def can_write(self) -> bool:
        return self.role in (Role.ADMIN, Role.OPERATOR)

    def can_admin(self) -> bool:
        return self.role == Role.ADMIN
