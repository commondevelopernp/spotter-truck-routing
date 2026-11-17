"""Small, dependency-free geometry helpers. Coordinates are (lat, lon) in degrees."""
from __future__ import annotations

import bisect
import math
from typing import Sequence

EARTH_RADIUS_MI = 3958.8
METERS_PER_MILE = 1609.344

LatLon = tuple[float, float]


def haversine_mi(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(h)))


def cumulative_miles(points: Sequence[LatLon]) -> list[float]:
    out = [0.0]
    for prev, cur in zip(points, points[1:]):
        out.append(out[-1] + haversine_mi(prev, cur))
    return out


def interpolate(points: Sequence[LatLon], cum: Sequence[float], mile: float) -> tuple[LatLon, int, float]:
    """Point at `mile` along the polyline. Also returns the segment index and the
    fraction along that segment, so callers can interpolate other per-vertex values
    (e.g. elapsed time) the same way."""
    if mile <= 0:
        return points[0], 0, 0.0
    if mile >= cum[-1]:
        return points[-1], len(points) - 2, 1.0
    i = bisect.bisect_right(cum, mile) - 1
    seg = cum[i + 1] - cum[i]
    t = 0.0 if seg == 0 else (mile - cum[i]) / seg
    (la1, lo1), (la2, lo2) = points[i], points[i + 1]
    return (la1 + (la2 - la1) * t, lo1 + (lo2 - lo1) * t), i, t


def checkpoint_miles(total_miles: float, interval: float) -> list[float]:
    """Origin, every `interval` miles, and the destination."""
    if total_miles <= 0:
        return [0.0]
    miles = [0.0]
    m = interval
    while m < total_miles - 1e-6:
        miles.append(m)
        m += interval
    miles.append(total_miles)
    return miles


def simplify_by_distance(points: Sequence[LatLon], min_step_mi: float) -> list[LatLon]:
    """Keep a vertex only when it is at least `min_step_mi` from the last kept one.
    Cheap and good enough to cut a full-resolution route down for the map."""
    if len(points) <= 2:
        return list(points)
    kept = [points[0]]
    for p in points[1:-1]:
        if haversine_mi(kept[-1], p) >= min_step_mi:
            kept.append(p)
    kept.append(points[-1])
    return kept


def fast_distance_mi(a: LatLon, b: LatLon) -> float:
    """Equirectangular approximation; accurate to <1% over the short distances used for corridor tests."""
    x = math.radians(b[1] - a[1]) * math.cos(math.radians((a[0] + b[0]) / 2))
    y = math.radians(b[0] - a[0])
    return EARTH_RADIUS_MI * math.hypot(x, y)
