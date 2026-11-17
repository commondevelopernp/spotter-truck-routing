"""Geocoding via Photon (OpenStreetMap data, no API key)."""
from __future__ import annotations

import re

from django.conf import settings
from django.core.cache import cache

from .cachekeys import key as cache_key
from .http import UpstreamError, get_json

_COORD_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


class PlaceNotFound(Exception):
    def __init__(self, query: str):
        super().__init__(f"Could not find a place for “{query}”.")
        self.query = query


def _label(props: dict) -> str:
    parts = [props.get("name"), props.get("city") if props.get("city") != props.get("name") else None, props.get("state"), props.get("countrycode")]
    return ", ".join(p for p in parts if p)


def search(query: str, limit: int = 5) -> list[dict]:
    query = query.strip()
    if not query:
        return []
    m = _COORD_RE.match(query)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return [{"name": f"{lat:.5f}, {lon:.5f}", "lat": lat, "lon": lon}]
    key = cache_key("geo", f"{limit}:{query.lower()}")
    cached = cache.get(key)
    if cached is not None:
        return cached
    data = get_json("Photon geocoder", settings.PHOTON_URL, {"q": query, "limit": limit, "lang": "en"})
    results = []
    for f in data.get("features", []):
        try:
            lon, lat = f["geometry"]["coordinates"][:2]
        except (KeyError, ValueError, TypeError):
            continue
        results.append({"name": _label(f.get("properties", {})) or query, "lat": float(lat), "lon": float(lon)})
    cache.set(key, results, 60 * 60 * 24)
    return results


def resolve(query: str) -> dict:
    results = search(query, limit=1)
    if not results:
        raise PlaceNotFound(query)
    return results[0]


__all__ = ["search", "resolve", "PlaceNotFound", "UpstreamError"]
