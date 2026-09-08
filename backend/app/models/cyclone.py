"""SQLAlchemy ORM models.

Spatial columns use PostGIS geometry; `observations` and `forecast_points` are
TimescaleDB hypertables (see scripts/init_db.sql) so time-range queries over long
cyclone histories stay fast.
"""

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CycloneEvent(Base):
    __tablename__ = "cyclone_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str | None] = mapped_column(String(100))
    basin: Mapped[str] = mapped_column(String(10), default="NIO")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    peak_intensity_category: Mapped[str | None] = mapped_column(String(10))
    event_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    observations: Mapped[list["Observation"]] = relationship(
        back_populates="event", cascade="all, delete-orphan", order_by="Observation.observed_at"
    )
    forecasts: Mapped[list["Forecast"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cyclone_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cyclone_events.id", ondelete="CASCADE"), index=True
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    location = mapped_column(Geometry("POINT", srid=4326))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    pattern_type: Mapped[str | None] = mapped_column(String(30))
    intensity_category: Mapped[str | None] = mapped_column(String(10))
    est_wind_kt: Mapped[float | None] = mapped_column(Float)
    est_pressure_hpa: Mapped[float | None] = mapped_column(Float)
    dvorak_t_number: Mapped[float | None] = mapped_column(Float)
    radius_max_wind_km: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    class_probabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    source_frame: Mapped[str | None] = mapped_column(String(200))
    model_versions: Mapped[dict] = mapped_column(JSON, default=dict)
    explanation_uri: Mapped[str | None] = mapped_column(String(500))

    event: Mapped[CycloneEvent] = relationship(back_populates="observations")

    __table_args__ = (Index("ix_observations_cyclone_time", "cyclone_id", "observed_at"),)


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cyclone_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cyclone_events.id", ondelete="CASCADE"), index=True
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    model_version: Mapped[str] = mapped_column(String(100))
    cone_geojson: Mapped[dict | None] = mapped_column(JSON)
    landfall_estimate: Mapped[dict | None] = mapped_column(JSON)
    environment_inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    rapid_intensification_risk: Mapped[float | None] = mapped_column(Float)

    event: Mapped[CycloneEvent] = relationship(back_populates="forecasts")
    points: Mapped[list["ForecastPoint"]] = relationship(
        back_populates="forecast", cascade="all, delete-orphan", order_by="ForecastPoint.lead_hours"
    )


class ForecastPoint(Base):
    __tablename__ = "forecast_points"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    forecast_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("forecasts.id", ondelete="CASCADE"), index=True
    )
    lead_hours: Mapped[int]
    valid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    est_wind_kt: Mapped[float | None] = mapped_column(Float)
    est_pressure_hpa: Mapped[float | None] = mapped_column(Float)
    intensity_category: Mapped[str | None] = mapped_column(String(10))
    radius_uncertainty_km: Mapped[float | None] = mapped_column(Float)

    forecast: Mapped[Forecast] = relationship(back_populates="points")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cyclone_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cyclone_events.id", ondelete="CASCADE"), index=True
    )
    severity: Mapped[str] = mapped_column(String(10), index=True)
    status: Mapped[str] = mapped_column(String(20), default="issued", index=True)
    headline: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(String(4000))
    matched_rule: Mapped[str | None] = mapped_column(String(100))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    geofence = mapped_column(Geometry("MULTIPOLYGON", srid=4326))
    affected_regions: Mapped[dict] = mapped_column(JSON, default=list)
    channels: Mapped[dict] = mapped_column(JSON, default=list)
    dispatches: Mapped[dict] = mapped_column(JSON, default=list)
    issued_by: Mapped[str] = mapped_column(String(100), default="system")
    dry_run: Mapped[bool] = mapped_column(default=False)
