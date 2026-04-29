"""Compliance check engine — security baselines, TLS, password strength, K8s policies."""

from langchain_core.tools import tool

MOCK_CHECKS = [
    {"id": "C001", "rule": "数据库密码强度", "target": "mysql", "status": "pass", "detail": "密码长度 16，含大小写+数字+特殊字符"},
    {"id": "C002", "rule": "TLS 版本", "target": "nginx", "status": "warn", "detail": "TLS 1.2 支持，建议升级到 TLS 1.3"},
    {"id": "C003", "rule": "K8s Resource Limit", "target": "payment-service", "status": "fail", "detail": "未设置 memory limit，存在 OOM 风险"},
    {"id": "C004", "rule": "K8s Network Policy", "target": "all", "status": "fail", "detail": "未配置 NetworkPolicy，缺少网络隔离"},
    {"id": "C005", "rule": "PodDisruptionBudget", "target": "all", "status": "warn", "detail": "核心服务未配置 PDB，节点维护时可能中断"},
    {"id": "C006", "rule": "Secret 轮换周期", "target": "all", "status": "pass", "detail": "Secret 在 90 天内均有更新记录"},
    {"id": "C007", "rule": "容器非 root 运行", "target": "order-service", "status": "fail", "detail": "order-service 容器以 root 用户运行"},
    {"id": "C008", "rule": "镜像来源", "target": "all", "status": "pass", "detail": "所有镜像来自私有仓库 registry.internal"},
]


@tool
def run_compliance_check(scope: str = "all") -> str:
    """运行安全合规检查，扫描 K8s 安全基线、数据库配置、TLS 等。

    Args:
        scope: 检查范围 (all / k8s / database / network)
    """
    checks = MOCK_CHECKS
    if scope == "k8s":
        checks = [c for c in checks if "k8s" in c["rule"].lower() or "K8s" in c["rule"] or "Pod" in c["rule"]]
    elif scope == "database":
        checks = [c for c in checks if "数据库" in c["rule"] or "mysql" in c["target"]]
    elif scope == "network":
        checks = [c for c in checks if "tls" in c["rule"].lower() or "network" in c["rule"].lower()]

    pass_count = sum(1 for c in checks if c["status"] == "pass")
    warn_count = sum(1 for c in checks if c["status"] == "warn")
    fail_count = sum(1 for c in checks if c["status"] == "fail")

    lines = [
        f"合规检查报告 (scope={scope})",
        f"通过: {pass_count} | 警告: {warn_count} | 未通过: {fail_count}",
        "",
    ]

    for c in sorted(checks, key=lambda x: {"fail": 0, "warn": 1, "pass": 2}[x["status"]]):
        icon = "✅" if c["status"] == "pass" else "⚠️" if c["status"] == "warn" else "❌"
        lines.append(f"{icon} [{c['id']}] {c['rule']}")
        lines.append(f"   Target: {c['target']} | Status: {c['status']}")
        lines.append(f"   {c['detail']}")
        lines.append("")

    return "\n".join(lines)
