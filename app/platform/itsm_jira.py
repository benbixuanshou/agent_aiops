"""ITSM Connector — Jira REST API integration with basic auth / token."""

import base64
import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger("superbizagent")


class JiraConnector:
    """Real Jira REST API connector. Configure via env vars: JIRA_URL, JIRA_API_TOKEN, JIRA_PROJECT_KEY."""

    def __init__(self):
        self._configured = bool(settings.jira_url and settings.jira_api_token)

    def _headers(self) -> dict:
        token = settings.jira_api_token
        # Support both basic auth (email:token) and bearer token
        if ":" in token:
            encoded = base64.b64encode(token.encode()).decode()
            return {"Authorization": f"Basic {encoded}", "Content-Type": "application/json"}
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def create_ticket(self, title: str, description: str, severity: str = "P2") -> str | None:
        if not self._configured:
            logger.info("jira: not configured, skipping ticket creation")
            return None

        priority = {"P0": "Highest", "P1": "High", "P2": "Medium"}.get(severity, "Medium")
        payload = {
            "fields": {
                "project": {"key": settings.jira_project_key},
                "summary": f"[{severity}] {title[:200]}",
                "description": description[:3000],
                "issuetype": {"name": "Bug"},
                "priority": {"name": priority},
            }
        }
        try:
            resp = httpx.post(
                f"{settings.jira_url}/rest/api/2/issue",
                headers=self._headers(), json=payload, timeout=15,
            )
            resp.raise_for_status()
            key = resp.json().get("key", "")
            logger.info("jira_ticket_created: %s", key)
            return key
        except Exception:
            logger.warning("jira_create_failed", exc_info=True)
            return None

    async def update_ticket(self, ticket_id: str, status: str, comment: str = "") -> bool:
        if not self._configured:
            return False
        try:
            # Get available transitions
            resp = httpx.get(
                f"{settings.jira_url}/rest/api/2/issue/{ticket_id}/transitions",
                headers=self._headers(), timeout=10,
            )
            resp.raise_for_status()
            transitions = resp.json().get("transitions", [])
            target = next((t for t in transitions if status.lower() in t.get("name", "").lower()), None)
            if not target:
                return False
            payload = {"transition": {"id": target["id"]}}
            if comment:
                payload["update"] = {"comment": [{"add": {"body": comment}}]}
            resp = httpx.post(
                f"{settings.jira_url}/rest/api/2/issue/{ticket_id}/transitions",
                headers=self._headers(), json=payload, timeout=10,
            )
            resp.raise_for_status()
            return True
        except Exception:
            logger.warning("jira_update_failed: %s", ticket_id, exc_info=True)
            return False

    async def close_ticket(self, ticket_id: str, resolution: str = "Done") -> bool:
        return await self.update_ticket(ticket_id, "Done", f"Resolution: {resolution}")


jira_connector = JiraConnector()
