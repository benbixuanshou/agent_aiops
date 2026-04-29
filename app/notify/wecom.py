"""WeCom (企业微信) group bot notification."""

import json
import logging
import urllib.request

from app.config import settings

logger = logging.getLogger("superbizagent")


async def send_wecom_markdown(content: str) -> bool:
    if not settings.wecom_webhook_url:
        logger.info("wecom: webhook not configured, skipping")
        return False

    payload = json.dumps({
        "msgtype": "markdown",
        "markdown": {"content": content[:4000]},
    }).encode()

    try:
        req = urllib.request.Request(settings.wecom_webhook_url, data=payload,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        logger.warning("wecom: send failed", exc_info=True)
        return False
