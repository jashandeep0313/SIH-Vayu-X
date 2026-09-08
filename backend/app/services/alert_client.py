"""HTTP client for the alert-system service."""

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings


class AlertServiceClient:
    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = base_url or settings.ALERT_SERVICE_URL
        self.timeout = timeout

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def evaluate(self, cyclone_event: dict) -> dict:
        """Run a CycloneEvent through the rule engine; dispatch if a rule matches."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/evaluate", json=cyclone_event)
            response.raise_for_status()
            return response.json()

    async def dispatch(self, alert: dict) -> dict:
        """Force-send a specific alert, bypassing the rule engine (admin/manual path)."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/dispatch", json=alert)
            response.raise_for_status()
            return response.json()

    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{self.base_url}/health")
            return response.json()
