"""Pre-built AIOps task templates with severity levels for one-click incident response."""

SEVERITY = {
    "P0": {"label": "严重", "color": "red", "description": "服务不可用，需立即处理"},
    "P1": {"label": "警告", "color": "yellow", "description": "性能退化，需尽快处理"},
    "P2": {"label": "通知", "color": "blue", "description": "潜在风险，可计划处理"},
}

TASK_TEMPLATES = {
    "cpu_alert": {
        "label": "CPU 告警分析",
        "icon": "cpu",
        "severity": "P1",
        "prompt": (
            "收到 HighCPUUsage 告警。请查询 Prometheus 确认告警详情，"
            "然后查询 system-metrics 日志了解 CPU 使用趋势，"
            "最后查知识库获取 CPU 高负载处理方案，输出完整分析报告。"
        ),
    },
    "memory_alert": {
        "label": "内存泄漏排查",
        "icon": "memory",
        "severity": "P1",
        "prompt": (
            "收到 HighMemoryUsage 告警，order-service JVM 堆内存接近上限。"
            "请查询 Prometheus 告警、系统日志和应用日志，"
            "分析是否存在内存泄漏，给出排查和处理建议。"
        ),
    },
    "slow_response": {
        "label": "慢响应排查",
        "icon": "slow",
        "severity": "P1",
        "prompt": (
            "收到 SlowResponse 告警，user-service P99 响应时间超过 3 秒。"
            "请查询 Prometheus 确认告警，查询应用日志和数据库慢查询日志，"
            "分析慢响应的根因，给出处理建议。"
        ),
    },
    "service_down": {
        "label": "服务不可用",
        "icon": "down",
        "severity": "P0",
        "prompt": (
            "收到 ServiceUnavailable 告警，某个服务完全不可用。"
            "请立即查询 Prometheus 告警、K8s Events（Pod 重启/OOMKill）、"
            "系统事件日志，综合分析故障原因，给出紧急恢复步骤。"
            "P0 严重故障，需要立即通知团队。"
        ),
    },
    "k8s_pod_crash": {
        "label": "Pod 崩溃排查",
        "icon": "k8s",
        "severity": "P0",
        "prompt": (
            "收到 Pod CrashLoopBackOff 告警。"
            "请 query_k8s_events 查看 Pod 事件，query_logs 查应用日志，"
            "query_prometheus_alerts 确认告警详情，综合分析根因并给出恢复方案。"
        ),
    },
    "db_slow_query": {
        "label": "数据库慢查询",
        "icon": "db",
        "severity": "P1",
        "prompt": (
            "收到数据库慢查询告警。"
            "请 query_logs(log_topic='database-slow-query') 分析慢查询日志，"
            "search_knowledge_base 获取慢查询优化方案，输出分析和处理建议。"
        ),
    },
    "disk_space": {
        "label": "磁盘空间告警",
        "icon": "disk",
        "severity": "P2",
        "prompt": (
            "收到磁盘空间不足告警。请查询 Prometheus 确认当前使用率，"
            "分析增长趋势，给出清理或扩容建议。"
        ),
    },
    "cert_expiry": {
        "label": "证书过期检查",
        "icon": "cert",
        "severity": "P2",
        "prompt": (
            "定期巡检发现 TLS 证书即将过期。请确认影响的域名和服务，"
            "查询知识库获取证书续期步骤，输出处理清单。"
        ),
    },
}
