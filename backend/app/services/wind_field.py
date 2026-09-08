"""Parametric cyclone wind and pressure field (Holland 1980).

Turns the three numbers the model already produces — central pressure, maximum
wind, radius of maximum wind — into the radial structure operational forecasters
actually use: wind radii (R34/R50/R64) and closed isobars.

Holland, G.J. (1980), "An Analytic Model of the Wind and Pressure Profiles in
Hurricanes", Monthly Weather Review 108(8).

    P(r) = Pc + dP * exp(-(Rmw/r)^B)
    V(r) = sqrt( (B/rho) * (Rmw/r)^B * dP * exp(-(Rmw/r)^B) )

R34/R50/R64 are the standard IMD/RSMC operational product: the radius out to
which winds reach 34, 50 and 64 knots. Emergency managers plan evacuations off
these, not off the centre position alone.
"""

import math

AIR_DENSITY = 1.15  # kg/m^3, typical near-surface tropical value
ENVIRONMENTAL_PRESSURE_HPA = 1010.0
KT_TO_MS = 0.514444

# Holland B controls profile peakedness. Outside ~[1.0, 2.5] the profile stops
# resembling a real cyclone, so estimates are clamped.
B_MIN, B_MAX = 1.0, 2.5


def holland_b(
    max_wind_kt: float,
    central_pressure_hpa: float,
    environmental_hpa: float = ENVIRONMENTAL_PRESSURE_HPA,
) -> float:
    """Estimate the Holland B shape parameter from peak wind and pressure drop."""
    delta_p_pa = max(1.0, (environmental_hpa - central_pressure_hpa)) * 100.0
    v_ms = max_wind_kt * KT_TO_MS
    b = (v_ms**2) * AIR_DENSITY * math.e / delta_p_pa
    return min(B_MAX, max(B_MIN, b))


def pressure_at_radius(
    radius_km: float,
    central_pressure_hpa: float,
    rmw_km: float,
    b: float,
    environmental_hpa: float = ENVIRONMENTAL_PRESSURE_HPA,
) -> float:
    if radius_km <= 0:
        return central_pressure_hpa
    delta_p = environmental_hpa - central_pressure_hpa
    return central_pressure_hpa + delta_p * math.exp(-((rmw_km / radius_km) ** b))


def radius_of_pressure(
    target_hpa: float,
    central_pressure_hpa: float,
    rmw_km: float,
    b: float,
    environmental_hpa: float = ENVIRONMENTAL_PRESSURE_HPA,
) -> float | None:
    """Radius of a given isobar, inverting the Holland pressure profile.

    Returns None when the isobar lies outside the storm's pressure range.
    """
    delta_p = environmental_hpa - central_pressure_hpa
    excess = target_hpa - central_pressure_hpa
    if delta_p <= 0 or excess <= 0 or excess >= delta_p:
        return None
    inner = math.log(delta_p / excess)
    if inner <= 0:
        return None
    return rmw_km / (inner ** (1.0 / b))


def radius_of_wind(
    target_kt: float,
    max_wind_kt: float,
    central_pressure_hpa: float,
    rmw_km: float,
    b: float,
    environmental_hpa: float = ENVIRONMENTAL_PRESSURE_HPA,
) -> float | None:
    """Outer radius at which the wind falls to `target_kt`.

    Substituting x = (Rmw/r)^B gives V^2 = (B*dP/rho) * x * exp(-x). That has two
    roots; the outer branch (x < 1, r > Rmw) is the operationally meaningful one,
    found here by bisection.
    """
    if target_kt >= max_wind_kt:
        return None

    delta_p_pa = max(1.0, environmental_hpa - central_pressure_hpa) * 100.0
    v_ms = target_kt * KT_TO_MS
    k = (v_ms**2) * AIR_DENSITY / (b * delta_p_pa)

    # x*exp(-x) peaks at x=1 with value 1/e; beyond that no solution exists.
    if k >= 1.0 / math.e:
        return None

    lo, hi = 1e-9, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if mid * math.exp(-mid) < k:
            lo = mid
        else:
            hi = mid
    x = (lo + hi) / 2
    if x <= 0:
        return None
    return rmw_km / (x ** (1.0 / b))


def wind_field(
    max_wind_kt: float,
    central_pressure_hpa: float,
    rmw_km: float,
    environmental_hpa: float = ENVIRONMENTAL_PRESSURE_HPA,
) -> dict:
    """Full radial structure for one cyclone position.

    Returns the standard wind radii plus closed isobars at 4 hPa intervals — the
    same products IMD publishes, derived from our own model output rather than a
    third-party weather service.
    """
    b = holland_b(max_wind_kt, central_pressure_hpa, environmental_hpa)

    radii = {}
    for threshold in (34, 50, 64):
        r = radius_of_wind(
            threshold, max_wind_kt, central_pressure_hpa, rmw_km, b, environmental_hpa
        )
        radii[f"r{threshold}_km"] = round(r, 1) if r else None

    isobars = []
    start = math.ceil((central_pressure_hpa + 2) / 4) * 4
    for p in range(int(start), int(environmental_hpa), 4):
        r = radius_of_pressure(p, central_pressure_hpa, rmw_km, b, environmental_hpa)
        if r and r < 1200:
            isobars.append({"pressure_hpa": p, "radius_km": round(r, 1)})

    return {
        "holland_b": round(b, 3),
        "environmental_pressure_hpa": environmental_hpa,
        "rmw_km": round(rmw_km, 1),
        "wind_radii": radii,
        "isobars": isobars,
    }
