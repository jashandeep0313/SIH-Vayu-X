"""Email channel — full detail for district administration, and the formal record."""

import os

from src.channels.base import BaseChannel, DispatchResult


class EmailChannel(BaseChannel):
    name = "email"

    def __init__(self) -> None:
        super().__init__()
        self.host = os.getenv("SMTP_HOST", "")
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.user = os.getenv("SMTP_USER", "")
        self.password = os.getenv("SMTP_PASSWORD", "")
        self.sender = os.getenv("SMTP_FROM", "alerts@vayux.local")

    def is_configured(self) -> bool:
        return bool(self.host and self.user and self.password)

    async def send(
        self, recipients: list[str], subject: str, body: str, **kwargs
    ) -> DispatchResult:
        # TODO(alerts): render the HTML template, attach the track map, send via SMTP,
        # BCC recipients so addresses are not exposed to each other.
        return DispatchResult(channel=self.name, status="failed", error="Not implemented — Phase 5")
