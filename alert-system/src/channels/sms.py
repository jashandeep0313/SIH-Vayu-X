"""SMS channel — the most important one.

SMS works on any handset without internet, which is exactly the condition during
a cyclone when data networks degrade first.
"""

import os

from src.channels.base import BaseChannel, DispatchResult

SMS_MAX_LENGTH = 160


class SMSChannel(BaseChannel):
    name = "sms"

    def __init__(self) -> None:
        super().__init__()
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.getenv("TWILIO_FROM_NUMBER", "")

    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.from_number)

    async def send(
        self, recipients: list[str], subject: str, body: str, **kwargs
    ) -> DispatchResult:
        message = truncate_for_sms(body)
        # TODO(alerts): send via Twilio (or an Indian SMS gateway), batch, retry x3
        # with exponential backoff, and count partial successes.
        _ = message
        return DispatchResult(channel=self.name, status="failed", error="Not implemented — Phase 5")


def truncate_for_sms(text: str, limit: int = SMS_MAX_LENGTH) -> str:
    """Trim to one SMS segment on a word boundary.

    Multi-segment messages can arrive out of order or partially, which is
    unacceptable for a warning.
    """
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return f"{cut}…"
