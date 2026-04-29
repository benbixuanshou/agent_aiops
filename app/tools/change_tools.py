"""Change correlation analysis — detect if recent deployments caused the incident."""

import logging
from datetime import datetime, timedelta, timezone

import httpx
from langchain_core.tools import tool

from app.config import settings

logger = logging.getLogger("superbizagent")

MOCK_DEPLOYMENTS = [
    {
        "service": "payment-service",
        "version": "v2.3.7",
        "author": "zhangsan",
        "timestamp": "2026-04-28T09:45:00+08:00",
        "summary": "优化支付回调超时逻辑，增加重试机制",
    },
    {
        "service": "order-service",
        "version": "v2.3.8",
        "author": "lisi",
        "timestamp": "2026-04-28T10:05:00+08:00",
        "summary": "修复订单状态机死锁问题",
    },
    {
        "service": "payment-service",
        "version": "v2.3.6",
        "author": "wangwu",
        "timestamp": "2026-04-27T18:30:00+08:00",
        "summary": "Redis 连接池从 10 改为 50",
    },
]


@tool
def query_recent_deployments(service: str = "", hours: int = 6) -> str:
    """查询最近的服务发布记录，用于判断变更是否与当前告警相关。

    Args:
        service: 服务名，留空查所有
        hours: 查询最近几小时内的发布
    """
    if not settings.change_tracking_enabled:
        return "变更追踪未启用。设置 CHANGE_TRACKING_ENABLED=true 开启。"

    # Try real GitLab API
    if not settings.change_tracking_mock and settings.gitlab_api_url and settings.gitlab_api_token:
        try:
            since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            gitlab_url = f"{settings.gitlab_api_url}/api/v4/events"
            params = {"after": since, "per_page": 20, "action": "pushed"}
            headers = {"PRIVATE-TOKEN": settings.gitlab_api_token}
            resp = httpx.get(gitlab_url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            events = resp.json()
            if not events:
                return f"最近 {hours} 小时内没有 GitLab 推送事件"

            lines = [f"最近 {hours} 小时内的 GitLab 变更:\n"]
            for ev in events[:10]:
                author = ev.get("author", {}).get("name", "unknown")
                ts = ev.get("created_at", "")
                msg = ev.get("push_data", {}).get("commit_title", "") or ev.get("action_name", "")
                project = ev.get("project", {}).get("name", "")
                lines.append(f"  {project} by {author} at {ts}\n    {msg}\n")
            lines.append("\n提示: 如果告警时间与某次变更接近，该变更可能是根因。")
            return "\n".join(lines)
        except Exception as e:
            logger.warning("gitlab_api_failed: %s, falling back to mock", e)

    deploys = MOCK_DEPLOYMENTS if settings.change_tracking_mock else []
    if service:
        deploys = [d for d in deploys if d["service"] == service]

    if not deploys:
        return f"最近 {hours} 小时内没有{' ' + service if service else ''}的发布记录"

    lines = [f"最近 {hours} 小时内的发布记录:\n"]
    for d in deploys:
        lines.append(
            f"  {d['service']} {d['version']} by {d['author']} at {d['timestamp']}\n"
            f"    变更: {d['summary']}\n"
        )

    lines.append("\n提示: 如果告警时间与某次发布接近，该变更可能是根因。")
    return "\n".join(lines)
