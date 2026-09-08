"""Geofencing — turn a forecast cone into a list of districts to warn.

Precision keeps trust intact: an alert for an Odisha landfall must not reach Kerala.
Over-broadcasting is how a warning system trains people to ignore it.

See docs/alerting.md §4.
"""

from pathlib import Path

KM_PER_DEGREE = 111.0


def build_cone_polygon(forecast_points: list[dict], buffer_km: float = 100.0):
    """Build the cone of uncertainty from forecast points and their uncertainty radii.

    Each point contributes a circle of `radius_uncertainty_km + buffer_km`; the cone
    is the convex hull of those circles along the track.
    """
    # TODO(alerts): shapely — buffer each point, union, convex hull along the track
    raise NotImplementedError("Phase 5 — see docs/roadmap.md")


def intersect_with_districts(
    cone_polygon,
    boundaries_path: str | Path,
    min_area_km2: float = 25.0,
):
    """Return districts whose area intersects the cone by more than `min_area_km2`.

    The area threshold drops slivers where the cone barely clips a district border.
    """
    # TODO(alerts): load GeoJSON boundaries, spatial index, intersect, filter by area
    raise NotImplementedError


def distance_to_coast_km(lat: float, lon: float, coastline_path: str | Path) -> float:
    """Great-circle distance from a position to the nearest coastline point.

    Feeds the `distance_to_coast_km` rule condition — intensity alone never
    determines severity.
    """
    # TODO(alerts): nearest-point query against the coastline geometry
    raise NotImplementedError


def hours_to_landfall(forecast: dict, issued_at) -> float | None:
    """Hours from now until the forecast landfall, or None if no landfall is predicted."""
    landfall = forecast.get("landfall_estimate")
    if not landfall or not landfall.get("expected_at"):
        return None
    # TODO(alerts): parse expected_at, return the delta in hours
    raise NotImplementedError
