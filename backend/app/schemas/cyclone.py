"""Pydantic models mirroring shared/schemas/*.json.

Keep these in sync with the JSON schemas — those are the contract, this is the
Python binding for it.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class IntensityCategory(StrEnum):
    LPA = "LPA"
    D = "D"
    DD = "DD"
    CS = "CS"
    SCS = "SCS"
    VSCS = "VSCS"
    ESCS = "ESCS"
    SUCS = "SuCS"


class PatternType(StrEnum):
    CURVED_BAND = "curved_band"
    SHEAR = "shear"
    CDO = "CDO"
    BANDING_EYE = "banding_eye"
    EYE = "eye"
    CENTRAL_COLD_COVER = "central_cold_cover"


class CycloneStatus(StrEnum):
    ACTIVE = "active"
    WEAKENED = "weakened"
    DISSIPATED = "dissipated"
    LANDFALL = "landfall"
    ARCHIVED = "archived"


class Observation(BaseModel):
    observed_at: datetime
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    bbox: list[float] | None = None
    pattern_type: PatternType | None = None
    intensity_category: IntensityCategory | None = None
    est_wind_kt: float | None = Field(default=None, ge=0)
    est_pressure_hpa: float | None = None
    dvorak_t_number: float | None = Field(default=None, ge=0, le=8)
    radius_max_wind_km: float | None = None
    # Holland-derived radial structure: R34/R50/R64 wind radii and closed isobars
    wind_field: dict | None = None
    confidence: float = Field(ge=0, le=1)
    class_probabilities: dict[str, float] | None = None
    source_frame: str | None = None
    source_channels: list[str] | None = None
    model_versions: dict[str, str] | None = None
    explanation_uri: str | None = None


class ForecastPoint(BaseModel):
    lead_hours: int = Field(ge=0)
    valid_at: datetime
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    est_wind_kt: float | None = None
    est_pressure_hpa: float | None = None
    intensity_category: IntensityCategory | None = None
    radius_uncertainty_km: float | None = Field(default=None, ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)


class LandfallEstimate(BaseModel):
    expected_at: datetime
    lat: float
    lon: float
    region: str
    confidence: float = Field(ge=0, le=1)


class Forecast(BaseModel):
    id: UUID | None = None
    cyclone_id: UUID
    issued_at: datetime
    model_version: str
    points: list[ForecastPoint]
    landfall_estimate: LandfallEstimate | None = None
    cone_geojson: dict | None = None
    environment_inputs: dict | None = None
    rapid_intensification_risk: float | None = Field(default=None, ge=0, le=1)

    # Provenance and scoring. Present when the forecast came from the trained
    # model; `verification` is populated for replayed storms whose real outcome
    # is known, so a forecast can be shown beside what actually happened.
    source: str | None = None
    trained_on: dict | None = None
    verification: list[dict] | None = None
    model_error: str | None = None


class CycloneEvent(BaseModel):
    id: UUID
    name: str | None = None
    basin: str = "NIO"
    status: CycloneStatus
    first_seen: datetime
    last_seen: datetime
    peak_intensity_category: IntensityCategory | None = None
    observations: list[Observation] = []
    latest_forecast: Forecast | None = None
    metadata: dict = {}


class CycloneSummary(BaseModel):
    """Lightweight event row for list views — avoids shipping full history to the map."""

    id: UUID
    name: str | None
    basin: str
    status: CycloneStatus
    first_seen: datetime
    last_seen: datetime
    latest_observation: Observation | None = None


class CycloneListResponse(BaseModel):
    count: int
    limit: int = 50
    offset: int = 0
    items: list[CycloneSummary]
