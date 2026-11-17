"""Hourly forecasts from Open-Meteo (no API key, many locations per request).

Units requested from the API: wind in mph, precipitation in inches.
Open-Meteo reports precipitation (rain, showers, snowfall) as the total over the
*preceding* hour, so the value stamped 13:00 is the rate for 12:00–13:00. Wind is
an instantaneous value at the timestamp. We respect both semantics:
  * wind/gusts → linear interpolation between the two surrounding hours;
  * rain/snow  → the hourly bucket the ETA falls in.
"Rain" is rain + showers (both liquid); snowfall is already in inches of snow.
"""
from __future__ import annotations

import bisect
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.cache import cache

from ..domain.geo import LatLon
from ..domain.risk import Weather
from .cachekeys import key as cache_key
from .http import UpstreamError, get_json

CHUNK = 100
VARIABLES = "wind_speed_10m,wind_gusts_10m,rain,showers,snowfall"


@dataclass
class Series:
    """Hourly series for one location. `hours` are unix hours (epoch seconds // 3600)."""

    hours: list[int]
    wind: list[float]
    gust: list[float]
    rain: list[float]
    snow: list[float]

    def _instant(self, values: list[float], t_hours: float) -> float:
        hs = self.hours
        if t_hours <= hs[0]:
            return values[0]
        if t_hours >= hs[-1]:
            return values[-1]
        i = bisect.bisect_right(hs, t_hours) - 1
        frac = t_hours - hs[i]
        return values[i] + (values[i + 1] - values[i]) * frac

    def _bucket(self, values: list[float], t_hours: float) -> float:
        label = math.floor(t_hours) + 1  # value stamped at the end of the hour
        i = bisect.bisect_left(self.hours, label)
        i = min(max(i, 0), len(values) - 1)
        return values[i]

    def at(self, when: datetime) -> Weather:
        t = when.timestamp() / 3600.0
        return Weather(
            wind_mph=self._instant(self.wind, t),
            gust_mph=self._instant(self.gust, t),
            rain_in_hr=self._bucket(self.rain, t),
            snow_in_hr=self._bucket(self.snow, t),
        )

    def hour(self, unix_hour: int) -> Weather:
        """Conditions for the hour starting at `unix_hour` (used by the heatmap)."""
        return self.at(datetime.fromtimestamp(unix_hour * 3600, tz=timezone.utc))


def _round(p: LatLon) -> LatLon:
    # Open-Meteo's grid is ~2–11 km; 2 decimals (~1 km) loses nothing and improves cache hits.
    return (round(p[0], 2), round(p[1], 2))


def _fmt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00")


def _num(v) -> float:
    return 0.0 if v is None else float(v)


def _fetch_chunk(points: list[LatLon], start: datetime, end: datetime) -> list[Series]:
    raw_key = f"{_fmt(start)}|{_fmt(end)}|" + ";".join(f"{a},{b}" for a, b in points)
    key = cache_key("wx", raw_key)
    cached = cache.get(key)
    if cached is not None:
        return cached
    data = get_json(
        "Open-Meteo weather",
        settings.OPEN_METEO_URL,
        {
            "latitude": ",".join(f"{p[0]:.2f}" for p in points),
            "longitude": ",".join(f"{p[1]:.2f}" for p in points),
            "hourly": VARIABLES,
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "GMT",
            "start_hour": _fmt(start),
            "end_hour": _fmt(end),
        },
    )
    if isinstance(data, dict) and data.get("error"):
        raise UpstreamError("Open-Meteo weather", data.get("reason", "error"))
    items = data if isinstance(data, list) else [data]
    if len(items) != len(points):
        raise UpstreamError("Open-Meteo weather", "unexpected number of locations in response")
    out = []
    for item in items:
        h = item["hourly"]
        hours = [int(datetime.fromisoformat(t).replace(tzinfo=timezone.utc).timestamp() // 3600) for t in h["time"]]
        rain = [_num(a) + _num(b) for a, b in zip(h["rain"], h["showers"])]
        out.append(Series(hours, [_num(v) for v in h["wind_speed_10m"]], [_num(v) for v in h["wind_gusts_10m"]], rain, [_num(v) for v in h["snowfall"]]))
    cache.set(key, out, 60 * 30)
    return out


def fetch(points: list[LatLon], start: datetime, end: datetime) -> list[Series]:
    """Series for each point covering [start, end] (both rounded outward to whole hours)."""
    start = start.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end = end.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)
    rounded = [_round(p) for p in points]
    unique = list(dict.fromkeys(rounded))
    chunks = [unique[i : i + CHUNK] for i in range(0, len(unique), CHUNK)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda c: _fetch_chunk(c, start, end), chunks))
    by_point = {p: s for chunk, series in zip(chunks, results) for p, s in zip(chunk, series)}
    return [by_point[p] for p in rounded]
