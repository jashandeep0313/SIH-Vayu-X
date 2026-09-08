"""Common interface for every alert channel.

Channels are independent: one failing must never block the others. During a
cyclone, network conditions are exactly when delivery paths start dropping.
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DispatchResult:
    channel: str
    status: str  # sent | partial | failed | skipped
    recipient_count: int = 0
    provider_message_id: str | None = None
    error: str | None = None
    attempts: int = 0


class BaseChannel(ABC):
    """Subclass per delivery channel."""

    name: str = "base"

    def __init__(self) -> None:
        self.dry_run = os.getenv("ALERT_DRY_RUN", "true").lower() == "true"

    @abstractmethod
    def is_configured(self) -> bool:
        """True when credentials are present. Unconfigured channels are skipped, not failed."""

    @abstractmethod
    async def send(
        self, recipients: list[str], subject: str, body: str, **kwargs
    ) -> DispatchResult:
        """Deliver the message. Must never raise — return a failed DispatchResult instead.

        A raised exception in one channel would abort the others in the dispatch loop.
        """

    async def dispatch(
        self, recipients: list[str], subject: str, body: str, **kwargs
    ) -> DispatchResult:
        """Entry point with dry-run and configuration guards applied."""
        if not recipients:
            return DispatchResult(channel=self.name, status="skipped", error="no recipients")

        if not self.is_configured():
            return DispatchResult(channel=self.name, status="skipped", error="not configured")

        if self.dry_run:
            # Default in development. A bug during a demo must never send real
            # warnings to real people.
            return DispatchResult(
                channel=self.name,
                status="skipped",
                recipient_count=len(recipients),
                error="dry_run enabled",
            )

        return await self.send(recipients, subject, body, **kwargs)
