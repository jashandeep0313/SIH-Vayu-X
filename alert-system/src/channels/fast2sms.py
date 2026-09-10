"""Fast2SMS channel — SMS delivery for Indian numbers.

Chosen over Twilio for the Indian market: no sender-ID registration needed for
the quick-transactional route, and credits are cheap enough for a hackathon.

On making the phone vibrate or play a sound — that is **not controllable from
the sending side**. A standard SMS triggers whatever notification profile the
recipient has configured; there is no field that forces vibration or a custom
tone. The strongest attention signal SMS offers is a *flash* message (GSM class
0), which renders over the lock screen immediately instead of sitting silently
in the inbox. That is exposed here as `flash=True`. Genuine control over sound
and vibration requires a companion app receiving FCM push, which is why the
push channel exists alongside this one.

Docs: https://docs.fast2sms.com/
"""

from __future__ import annotations

import os

import httpx

from src.channels.base import BaseChannel, DispatchResult

ENDPOINT = "https://www.fast2sms.com/dev/bulkV2"
SMS_SEGMENT = 160


class Fast2SMSChannel(BaseChannel):
    name = "sms"

    def __init__(self) -> None:
        super().__init__()
        self.api_key = os.getenv("FAST2SMS_API_KEY", "")
        # 'q' is the quick transactional route: no DLT template approval needed,
        # which matters because DLT registration takes days.
        self.route = os.getenv("FAST2SMS_ROUTE", "q")
        self.flash = os.getenv("FAST2SMS_FLASH", "false").lower() == "true"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def send(
        self, recipients: list[str], subject: str, body: str, **kwargs
    ) -> DispatchResult:
        numbers = ",".join(self._normalise(n) for n in recipients if n)
        if not numbers:
            return DispatchResult(channel=self.name, status="skipped", error="no valid numbers")

        message = body.strip() or subject
        if len(message) > SMS_SEGMENT:
            message = message[: SMS_SEGMENT - 1].rsplit(" ", 1)[0] + "…"

        payload = {
            "route": self.route,
            "message": message,
            "language": "english",
            "flash": "1" if kwargs.get("flash", self.flash) else "0",
            "numbers": numbers,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    ENDPOINT, data=payload, headers={"authorization": self.api_key}
                )
            data = (
                r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            )
        except Exception as exc:  # never raise: one channel must not abort the others
            return DispatchResult(channel=self.name, status="failed", error=str(exc), attempts=1)

        if r.status_code == 200 and data.get("return") is True:
            return DispatchResult(
                channel=self.name,
                status="sent",
                recipient_count=len(numbers.split(",")),
                provider_message_id=str(data.get("request_id") or ""),
                attempts=1,
            )

        return DispatchResult(
            channel=self.name,
            status="failed",
            recipient_count=len(numbers.split(",")),
            error=str(data.get("message") or r.text)[:300],
            attempts=1,
        )

    @staticmethod
    def _normalise(number: str) -> str:
        """Fast2SMS wants bare 10-digit Indian numbers, no +91 and no spaces."""
        digits = "".join(c for c in str(number) if c.isdigit())
        if len(digits) > 10 and digits.startswith("91"):
            digits = digits[2:]
        return digits[-10:]
