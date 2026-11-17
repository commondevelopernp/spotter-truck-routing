"""Route options from OSRM.

OSRM's `alternatives` often returns only 1–2 routes. The spec asks for three
options, so when OSRM comes up short we create extra candidates by forcing the
route through a via-point offset perpendicular to the origin→destination line
(on both sides, at two distances), then keep the ones that are genuinely
different from what we already have and not absurd detours.
"""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

from ..domain.geo import METERS_PER_MILE, LatLon, cumulative_miles, fast_distance_mi, haversine_mi
from .cachekeys import key as cache_key
from .http import UpstreamError, get_json

WANTED_ROUTES = 3
MAX_DETOUR_RATIO = 1.6       # vs. fastest option's duration
MAX_OVERLAP = 0.85           # share of a candidate's samples lying on an existing route
OVERLAP_RADIUS_MI = 1.0
VIA_OFFSETS = (0.12, -0.12, 0.25, -0.25)  # fraction of straight-line distance


class NoRouteFound(Exception):
    pass


@dataclass
class RawRoute:
    points: list[LatLon]
    seg_miles: list[float]
    seg_car_seconds: list[float]
    distance_mi: float
    car_duration_s: float
    source: str  # "osrm" | "via"


def _parse(route: dict, source: str) -> RawRoute:
    coords = [(c[1], c[0]) for c in route["geometry"]["coordinates"]]
    seg_m, seg_s = [], []
    for leg in route["legs"]:
        ann = leg.get("annotation") or {}
        seg_m.extend(ann.get("distance", []))
        seg_s.extend(ann.get("duration", []))
    if len(seg_m) != len(coords) - 1 or len(seg_s) != len(seg_m):
        # Fallback: derive segment lengths from geometry, spread time proportionally.
        seg_mi = [haversine_mi(a, b) for a, b in zip(coords, coords[1:])]
        total = sum(seg_mi) or 1.0
        seg_s = [route["duration"] * m / total for m in seg_mi]
    else:
        seg_mi = [m / METERS_PER_MILE for m in seg_m]
    return RawRoute(coords, seg_mi, seg_s, route["distance"] / METERS_PER_MILE, route["duration"], source)


def _osrm(points: list[LatLon], alternatives: bool) -> list[dict]:
    coord_str = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in points)
    key = cache_key("osrm", f"{coord_str}:{alternatives}")
    cached = cache.get(key)
    if cached is not None:
        return cached
    data = get_json(
        "OSRM routing",
        f"{settings.OSRM_URL}/route/v1/driving/{coord_str}",
        {
            "overview": "full",
            "geometries": "geojson",
            "annotations": "distance,duration",
            "alternatives": str(WANTED_ROUTES).lower() if alternatives else "false",
            "steps": "false",
        },
    )
    if data.get("code") != "Ok":
        if data.get("code") in ("NoRoute", "NoSegment"):
            return []
        raise UpstreamError("OSRM routing", data.get("message") or data.get("code", "unknown error"))
    routes = data.get("routes", [])
    cache.set(key, routes, 60 * 60 * 6)
    return routes


def _via_point(origin: LatLon, dest: LatLon, offset_frac: float) -> LatLon:
    """Point at the middle of origin→dest, pushed sideways by offset_frac × distance."""
    mid_lat = (origin[0] + dest[0]) / 2
    mid_lon = (origin[1] + dest[1]) / 2
    k = math.cos(math.radians(mid_lat))
    dx = (dest[1] - origin[1]) * k  # east, in "latitude degrees"
    dy = dest[0] - origin[0]        # north
    # Perpendicular (left of travel) vector, same length as the trip.
    px, py = -dy, dx
    return (mid_lat + py * offset_frac, mid_lon + (px * offset_frac) / max(k, 1e-6))


def _samples(route: RawRoute, n: int = 60) -> list[LatLon]:
    step = max(1, len(route.points) // n)
    return route.points[::step]


def _overlap(candidate: RawRoute, existing: RawRoute) -> float:
    ref = _samples(existing, 400)
    pts = _samples(candidate, 60)
    on = sum(1 for p in pts if min(fast_distance_mi(p, q) for q in ref) <= OVERLAP_RADIUS_MI)
    return on / len(pts)


def _is_distinct(candidate: RawRoute, chosen: list[RawRoute]) -> bool:
    return all(_overlap(candidate, r) < MAX_OVERLAP for r in chosen)


def get_routes(origin: LatLon, dest: LatLon) -> list[RawRoute]:
    if haversine_mi(origin, dest) < 0.5:
        raise NoRouteFound("Origin and destination are the same place.")
    chosen = [_parse(r, "osrm") for r in _osrm([origin, dest], alternatives=True)]
    if not chosen:
        raise NoRouteFound("No drivable route between these places.")
    chosen = chosen[:WANTED_ROUTES]

    if len(chosen) < WANTED_ROUTES:
        vias = [_via_point(origin, dest, f) for f in VIA_OFFSETS]
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda v: _safe_via(origin, v, dest), vias))
        fastest = min(r.car_duration_s for r in chosen)
        candidates = sorted((r for r in results if r is not None), key=lambda r: r.car_duration_s)
        for cand in candidates:
            if len(chosen) >= WANTED_ROUTES:
                break
            if cand.car_duration_s > fastest * MAX_DETOUR_RATIO:
                continue
            if _is_distinct(cand, chosen):
                chosen.append(cand)
    return chosen


def _safe_via(origin: LatLon, via: LatLon, dest: LatLon) -> RawRoute | None:
    try:
        routes = _osrm([origin, via, dest], alternatives=False)
    except UpstreamError:
        return None
    if not routes:
        return None
    route = _parse(routes[0], "via")
    if _has_backtrack(route):
        return None
    return route


def _has_backtrack(route: RawRoute) -> bool:
    """Reject via-routes that drive into a dead end and turn around (a classic via-point artefact):
    the path returns within 0.25 mi of a point it passed at least 2 road-miles earlier."""
    pts = _samples(route, 300)
    cum = cumulative_miles(pts)
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            gap = cum[j] - cum[i]
            if gap < 2.0:
                continue
            if gap > 60.0:
                break
            if fast_distance_mi(pts[i], pts[j]) < 0.25:
                return True
    return False
