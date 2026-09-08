"""Push notification channel — citizen app, rich content with a map deep-link."""

import os

from src.channels.base import BaseChannel, DispatchResult

SEVERITY_COLORS = {
    "GREEN": "#2E7D32",
    "YELLOW": "#F9A825",
    "ORANGE": "#EF6C00",
    "RED": "#C62828",
}


class PushChannel(BaseChannel):
    name = "push"

    def __init__(self) -> None:
        super().__init__()
        self.server_key = os.getenv("FCM_SERVER_KEY", "")
        self.project_id = os.getenv("FCM_PROJECT_ID", "")

    def is_configured(self) -> bool:
        return bool(self.server_key)

    async def send(
        self, recipients: list[str], subject: str, body: str, **kwargs
    ) -> DispatchResult:
        severity = kwargs.get("severity", "YELLOW")
        payload = {
            "notification": {"title": subject, "body": body},
            "data": {
                "severity": severity,
                "color": SEVERITY_COLORS.get(severity, "#F9A825"),
                "cyclone_id": kwargs.get("cyclone_id", ""),
                "deep_link": kwargs.get("deep_link", ""),
            },
        }
        # TODO(alerts): POST to FCM in batches of 500 tokens; prune tokens FCM reports invalid
        _ = payload
        return DispatchResult(channel=self.name, status="failed", error="Not implemented — Phase 5")
