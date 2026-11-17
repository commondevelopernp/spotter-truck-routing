"""Grid of points covering the trip corridor, used for the weather heatmap."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .geo import LatLon, cumulative_miles, fast_distance_mi, interpolate

TARGET_CELLS = 350
MIN_CELL_MI = 8.0
MAX_CELL_MI = 60.0


@dataclass
class Corridor:
    points: list[LatLon]
    cell_lat_deg: float
    cell_lon_deg: float
    cell_mi: float
    buffer_mi: float

    def to_dict(self) -> dict:
        return {
            "points": [[round(a, 4), round(b, 4)] for a, b in self.points],
            "cell_lat_deg": round(self.cell_lat_deg, 5),
            "cell_lon_deg": round(self.cell_lon_deg, 5),
            "cell_mi": round(self.cell_mi, 2),
            "buffer_mi": round(self.buffer_mi, 1),
        }


def _resample(points: list[LatLon], step_mi: float) -> list[LatLon]:
    cum = cumulative_miles(points)
    n = max(2, int(cum[-1] / step_mi) + 1)
    return [interpolate(points, cum, cum[-1] * i / (n - 1))[0] for i in range(n)]


def build(routes: list[list[LatLon]]) -> Corridor:
    lengths = [cumulative_miles(r)[-1] for r in routes]
    longest = max(lengths)
    buffer_mi = min(60.0, max(20.0, 0.12 * longest))
    # Union of corridors ≈ sum of lengths (overlap makes this an over-estimate → slightly finer grid, fine).
    area = sum(lengths) * 2 * buffer_mi
    cell_mi = min(MAX_CELL_MI, max(MIN_CELL_MI, math.sqrt(area / TARGET_CELLS)))

    samples = [p for r in routes for p in _resample(r, cell_mi / 2)]
    lats = [p[0] for p in samples]
    lons = [p[1] for p in samples]
    mid_lat = (min(lats) + max(lats)) / 2
    dlat = cell_mi / 69.0
    dlon = cell_mi / (69.0 * max(0.2, math.cos(math.radians(mid_lat))))
    pad_lat = buffer_mi / 69.0
    pad_lon = buffer_mi / (69.0 * max(0.2, math.cos(math.radians(mid_lat))))

    # Bucket samples so each grid point only checks nearby route samples.
    bucket: dict[tuple[int, int], list[LatLon]] = {}
    bsize_lat, bsize_lon = pad_lat, pad_lon
    for p in samples:
        bucket.setdefault((int(p[0] // bsize_lat), int(p[1] // bsize_lon)), []).append(p)

    points: list[LatLon] = []
    lat = min(lats) - pad_lat
    while lat <= max(lats) + pad_lat:
        lon = min(lons) - pad_lon
        while lon <= max(lons) + pad_lon:
            bi, bj = int(lat // bsize_lat), int(lon // bsize_lon)
            near = (q for di in (-1, 0, 1) for dj in (-1, 0, 1) for q in bucket.get((bi + di, bj + dj), ()))
            if any(fast_distance_mi((lat, lon), q) <= buffer_mi for q in near):
                points.append((lat, lon))
            lon += dlon
        lat += dlat
    return Corridor(points, dlat, dlon, cell_mi, buffer_mi)
