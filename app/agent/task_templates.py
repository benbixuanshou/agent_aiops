"""Pre-built AIOps task templates for one-click incident response."""

TASK_TEMPLATES = {
    "cpu_alert": {
        "label": "CPU 告警分析",
        "icon": "cpu",
        "prompt": (
            "收到 HighCPUUsage 告警。请查询 Prometheus 确认告警详情，"
            "然后查询 system-metrics 日志了解 CPU 使用趋势，"
            "最后查知识库获取 CPU 高负载处理方案，输出完整分析报告。"
        ),
    },
    "memory_alert": {
        "label": "内存泄漏排查",
        "icon": "memory",
        "prompt": (
            "收到 HighMemoryUsage 告警，order-service JVM 堆内存接近上限。"
            "请查询 Prometheus 告警、系统日志和应用日志，"
            "分析是否存在内存泄漏，给出排查和处理建议。"
        ),
    },
    "slow_response": {
        "label": "慢响应排查",
        "icon": "slow",
        "prompt": (
            "收到 SlowResponse 告警，user-service P99 响应时间超过 3 秒。"
            "请查询 Prometheus 确认告警，查询应用日志和数据库慢查询日志，"
            "分析慢响应的根因（是数据库问题还是下游依赖问题），给出处理建议。"
        ),
    },
    "service_down": {
        "label": "服务不可用",
        "icon": "down",
        "prompt": (
            "收到 ServiceUnavailable 告警，某个服务完全不可用。"
            "请查询 Prometheus 告警、系统事件日志（Pod重启/OOMKill），"
            "以及应用日志，综合分析故障原因，给出恢复步骤。"
        ),
    },
}
