"""Webhook channel — machine-to-machine delivery to NDMA / state EOC dashboards.

Payloads follow shared/schemas/alert.schema.json and are HMAC-signed so the
receiver can verify the alert actually came from us. An unauthenticated cyclone
warning endpoint would be trivially abusable.
"""

import hashlib
import hmac
import json
import os

from src.channels.base import BaseChannel, DispatchResult


class WebhookChannel(BaseChannel):
    name = "webhook"

    def __init__(self) -> None:
        super().__init__()
        self.url = os.getenv("ALERT_WEBHOOK_URL", "")
        self.secret = os.getenv("ALERT_WEBHOOK_SECRET", "")

    def is_configured(self) -> bool:
        return bool(self.url)

    async def send(
        self, recipients: list[str], subject: str, body: str, **kwargs
    ) -> DispatchResult:
        alert_payload = kwargs.get("alert", {})
        _ = self.sign(alert_payload)
        # TODO(alerts): POST with the X-Vayux-Signature header, retry with backoff
        return DispatchResult(channel=self.name, status="failed", error="Not implemented — Phase 5")

    def sign(self, payload: dict) -> str:
        """HMAC-SHA256 over the canonical JSON body."""
        if not self.secret:
            return ""
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hmac.new(self.secret.encode(), body, hashlib.sha256).hexdigest()
