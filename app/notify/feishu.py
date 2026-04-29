"""Feishu (Lark) group bot notification."""

import hashlib
import hmac
import json
import logging
import time
import urllib.request
from urllib.parse import quote

from app.config import settings

logger = logging.getLogger("superbizagent")


def _build_feishu_sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    mac = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256)
    return quote(mac.digest().hex())


async def send_feishu_card(title: str, content: str, url: str = "") -> bool:
    if not settings.feishu_webhook_url:
        logger.info("feishu: webhook not configured, skipping")
        return False

    ts = str(int(time.time()))
    sign = _build_feishu_sign(ts, settings.feishu_secret) if settings.feishu_secret else ""
    full_url = f"{settings.feishu_webhook_url}?timestamp={ts}&sign={sign}" if sign else settings.feishu_webhook_url

    payload = json.dumps({
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}},
            "elements": [
                {"tag": "markdown", "content": content[:4000]},
            ],
        },
    }).encode()

    try:
        req = urllib.request.Request(full_url, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        logger.warning("feishu: send failed", exc_info=True)
        return False
