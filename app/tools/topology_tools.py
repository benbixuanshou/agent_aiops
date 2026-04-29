"""Dependency topology analysis — discover service dependencies and blast radius."""

from langchain_core.tools import tool

MOCK_TOPOLOGY = {
    "nginx": {"upstream": [], "downstream": ["payment-service", "order-service", "user-service"]},
    "payment-service": {"upstream": ["nginx"], "downstream": ["mysql", "redis", "order-service"]},
    "order-service": {"upstream": ["nginx", "payment-service"], "downstream": ["mysql", "redis"]},
    "user-service": {"upstream": ["nginx"], "downstream": ["mysql", "redis"]},
    "mysql": {"upstream": ["payment-service", "order-service", "user-service"], "downstream": []},
    "redis": {"upstream": ["payment-service", "order-service", "user-service"], "downstream": []},
}


@tool
def query_service_topology(service: str = "") -> str:
    """查询服务依赖拓扑，了解服务间调用关系和受影响的下游。

    Args:
        service: 服务名，留空返回全局拓扑
    """
    if service and service in MOCK_TOPOLOGY:
        t = MOCK_TOPOLOGY[service]
        upstream = ", ".join(t["upstream"]) or "无"
        downstream = ", ".join(t["downstream"]) or "无"
        return (
            f"服务拓扑: {service}\n"
            f"  上游依赖: {upstream}\n"
            f"  下游影响: {downstream}"
        )

    lines = ["全局服务依赖拓扑:\n"]
    for svc, t in MOCK_TOPOLOGY.items():
        lines.append(f"  {svc}")
        if t["upstream"]:
            lines.append(f"    ← 依赖: {', '.join(t['upstream'])}")
        if t["downstream"]:
            lines.append(f"    → 影响: {', '.join(t['downstream'])}")
    return "\n".join(lines)


@tool
def query_blast_radius(service: str) -> str:
    """查询某个服务故障时的爆炸半径——所有直接和间接受影响的下游服务。

    Args:
        service: 故障服务名
    """
    if service not in MOCK_TOPOLOGY:
        return f"未找到服务 {service} 的拓扑信息"

    visited: set[str] = set()

    def walk(svc: str):
        if svc in visited:
            return
        visited.add(svc)
        for ds in MOCK_TOPOLOGY.get(svc, {}).get("downstream", []):
            walk(ds)

    walk(service)
    visited.discard(service)
    direct = set(MOCK_TOPOLOGY.get(service, {}).get("downstream", []))
    indirect = visited - direct

    return (
        f"服务 {service} 故障影响范围:\n"
        f"  直接影响: {', '.join(sorted(direct)) or '无'}\n"
        f"  间接影响: {', '.join(sorted(indirect)) or '无'}\n"
        f"  总影响: {len(visited)} 个服务"
    )
