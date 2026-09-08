"""Model inference service.

Stateless FastAPI app. Loads checkpoints at startup and exposes the three tasks
plus a chained `/infer`. No database — the backend owns persistence.

Contract: docs/api-contract.md §2
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.serve.registry import ModelRegistry

registry = ModelRegistry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.load_all()
    yield
    registry.unload_all()


app = FastAPI(
    title="Vayu-X Model Inference Service",
    version="0.1.0",
    description="Identification, classification and prediction of tropical cyclones "
    "from multi-source satellite imagery. SIH PS 26070 — Team Vayu-X (152).",
    lifespan=lifespan,
)


# ----------------------------------------------------------------- schemas
class EnvironmentFeatures(BaseModel):
    sst_c: float | None = None
    shear_kt: float | None = None
    rh_mid_pct: float | None = None
    vorticity_850: float | None = None
    steering_u: float | None = None
    steering_v: float | None = None
    ocean_heat_content: float | None = None


class InferOptions(BaseModel):
    min_confidence: float = Field(default=0.65, ge=0, le=1)
    return_explanation: bool = False


class InferRequest(BaseModel):
    frame_id: str
    frame_uri: str
    sequence_uris: list[str] = []
    environment: EnvironmentFeatures = EnvironmentFeatures()
    options: InferOptions = InferOptions()


class IdentifyRequest(BaseModel):
    frame_uri: str
    min_confidence: float = Field(default=0.65, ge=0, le=1)


class ClassifyRequest(BaseModel):
    crop_uri: str


class PredictRequest(BaseModel):
    sequence_uris: list[str]
    environment: EnvironmentFeatures = EnvironmentFeatures()


# ------------------------------------------------------------------ routes
@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {
        "status": "ok",
        "service": "vayux-ai-model",
        "device": registry.device,
        "models_loaded": registry.loaded_names(),
    }


@app.get("/models", tags=["meta"])
async def models() -> dict:
    """Loaded checkpoints and their input specs — used by the backend to record
    `model_version` on every observation and forecast."""
    return registry.describe()


@app.post("/identify", tags=["inference"])
async def identify(request: IdentifyRequest) -> dict:
    """Detect and locate cyclonic systems in a satellite frame."""
    # TODO(ml): load frame from URI, run detector, return centres + confidence
    raise HTTPException(status_code=501, detail="Not implemented — Phase 2")


@app.post("/classify", tags=["inference"])
async def classify(request: ClassifyRequest) -> dict:
    """Classify cloud pattern and estimate intensity for a storm-centred crop."""
    # TODO(ml): run multi-task classifier, return pattern + category + wind/pressure
    raise HTTPException(status_code=501, detail="Not implemented — Phase 2")


@app.post("/predict", tags=["inference"])
async def predict(request: PredictRequest) -> dict:
    """Forecast track and intensity from a sequence of frames."""
    # TODO(ml): run ConvLSTM over the sequence, return points + uncertainty radii
    raise HTTPException(status_code=501, detail="Not implemented — Phase 3")


@app.post("/infer", tags=["inference"])
async def infer(request: InferRequest) -> dict:
    """Full chain: identify -> classify -> predict.

    This is what the data pipeline calls on every new frame.
    """
    # TODO(ml): chain the three stages; drop detections below min_confidence
    _ = datetime.now(UTC)
    raise HTTPException(status_code=501, detail="Not implemented — Phase 2/3")
