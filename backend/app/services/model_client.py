"""HTTP client for the ai-model inference service.

Wrapped in retries because the model service may be reloading a checkpoint or
cold-starting a GPU worker. A transient failure here must never lose a detection.
"""

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings


class ModelServiceClient:
    def __init__(self, base_url: str | None = None, timeout: float = 60.0) -> None:
        self.base_url = base_url or settings.MODEL_SERVICE_URL
        self.timeout = timeout

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _post(self, path: str, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}{path}", json=payload)
            response.raise_for_status()
            return response.json()

    async def infer(
        self,
        frame_id: str,
        frame_uri: str,
        sequence_uris: list[str] | None = None,
        environment: dict | None = None,
        min_confidence: float = 0.65,
    ) -> dict:
        """Full chain: identify -> classify -> predict."""
        return await self._post(
            "/infer",
            {
                "frame_id": frame_id,
                "frame_uri": frame_uri,
                "sequence_uris": sequence_uris or [],
                "environment": environment or {},
                "options": {"min_confidence": min_confidence, "return_explanation": True},
            },
        )

    async def identify(self, frame_uri: str) -> dict:
        return await self._post("/identify", {"frame_uri": frame_uri})

    async def classify(self, crop_uri: str) -> dict:
        return await self._post("/classify", {"crop_uri": crop_uri})

    async def predict(self, sequence_uris: list[str], environment: dict) -> dict:
        return await self._post(
            "/predict", {"sequence_uris": sequence_uris, "environment": environment}
        )

    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{self.base_url}/health")
            return response.json()
