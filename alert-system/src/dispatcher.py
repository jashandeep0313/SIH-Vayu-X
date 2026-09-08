"""Dispatcher — fans an alert out across every configured channel.

Channels run concurrently and independently. One failing channel must not stop
the others, so results are gathered rather than awaited in sequence.
"""

import asyncio

from src.channels.base import BaseChannel, DispatchResult
from src.channels.email import EmailChannel
from src.channels.push import PushChannel
from src.channels.sms import SMSChannel
from src.channels.webhook import WebhookChannel


class Dispatcher:
    def __init__(self) -> None:
        self.channels: dict[str, BaseChannel] = {
            "sms": SMSChannel(),
            "email": EmailChannel(),
            "push": PushChannel(),
            "webhook": WebhookChannel(),
        }

    async def dispatch(
        self,
        alert: dict,
        recipients_by_channel: dict[str, list[str]],
    ) -> list[DispatchResult]:
        """Send an alert on each requested channel, concurrently."""
        tasks = []
        for channel_name in alert.get("channels", []):
            channel = self.channels.get(channel_name)
            if channel is None:
                continue
            tasks.append(
                channel.dispatch(
                    recipients=recipients_by_channel.get(channel_name, []),
                    subject=alert.get("headline", "Cyclone Alert"),
                    body=alert.get("body", ""),
                    severity=alert.get("severity", "YELLOW"),
                    cyclone_id=alert.get("cyclone_id", ""),
                    alert=alert,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # A channel that raised despite the no-raise contract still must not lose
        # the results of the others.
        return [
            r
            if isinstance(r, DispatchResult)
            else DispatchResult(channel="unknown", status="failed", error=str(r))
            for r in results
        ]

    def channel_status(self) -> dict[str, bool]:
        return {name: channel.is_configured() for name, channel in self.channels.items()}
