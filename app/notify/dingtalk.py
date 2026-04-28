import hashlib
import hmac
import json
import logging
import time
import urllib.request

from app.config import settings

logger = logging.getLogger("superbizagent")


def _build_sign(timestamp: str, secret: str) -> str:
    if not secret:
        return ""
    string_to_sign = f"{timestamp}\n{secret}"
    mac = hmac.new(secret.encode(), string_to_sign.encode(), hashlib.sha256)
    return urllib.request.quote(mac.digest().hex())


def _build_url() -> str | None:
    url = settings.dingtalk_webhook_url
    if not url:
        return None
    if settings.dingtalk_secret:
        ts = str(round(time.time() * 1000))
        sign = _build_sign(ts, settings.dingtalk_secret)
        return f"{url}&timestamp={ts}&sign={sign}"
    return url


async def send_dingtalk(text: str) -> bool:
    url = _build_url()
    if not url:
        logger.info("dingtalk: webhook not configured, skipping")
        return False

    payload = json.dumps({
        "msgtype": "text",
        "text": {"content": text},
    }).encode()

    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception:
        logger.warning("dingtalk: send failed", exc_info=True)
        return False


async def send_dingtalk_markdown(title: str, markdown: str) -> bool:
    url = _build_url()
    if not url:
        logger.info("dingtalk: webhook not configured, skipping")
        return False

    payload = json.dumps({
        "msgtype": "markdown",
        "markdown": {"title": title, "text": markdown},
    }).encode()

    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        logger.warning("dingtalk: markdown send failed", exc_info=True)
        return False
