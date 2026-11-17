"""End-to-end API tests with every third-party provider mocked."""
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
import responses
from django.core.cache import cache
from rest_framework.test import APIClient

PLACES = {"Dallas": (32.7767, -96.7970), "Houston": (29.7604, -95.3698)}


def _line(a, b, n=40, bend=0.0):
    pts = []
    for i in range(n + 1):
        t = i / n
        lat = a[0] + (b[0] - a[0]) * t
        lon = a[1] + (b[1] - a[1]) * t + bend * (1 - (2 * t - 1) ** 2)
        pts.append([lon, lat])
    return pts


def _osrm_route(coords, mph):
    from planner.domain.geo import haversine_mi

    seg_m, seg_s = [], []
    for (lo1, la1), (lo2, la2) in zip(coords, coords[1:]):
        mi = haversine_mi((la1, lo1), (la2, lo2))
        seg_m.append(mi * 1609.344)
        seg_s.append(mi / mph * 3600)
    return {
        "geometry": {"type": "LineString", "coordinates": coords},
        "legs": [{"annotation": {"distance": seg_m, "duration": seg_s}}],
        "distance": sum(seg_m),
        "duration": sum(seg_s),
    }


def _photon(request):
    q = parse_qs(urlparse(request.url).query)["q"][0]
    for name, (lat, lon) in PLACES.items():
        if name.lower() in q.lower():
            return 200, {}, __import__("json").dumps(
                {"features": [{"geometry": {"coordinates": [lon, lat]}, "properties": {"name": name, "state": "Texas", "countrycode": "US"}}]}
            )
    return 200, {}, '{"features": []}'


def _meteo_factory(windy_lon_range):
    """Every location gets calm weather, except points whose longitude is inside `windy_lon_range` (45 mph wind)."""

    def handler(request):
        import json

        q = parse_qs(urlparse(request.url).query)
        lats = q["latitude"][0].split(",")
        lons = q["longitude"][0].split(",")
        start = datetime.fromisoformat(q["start_hour"][0])
        end = datetime.fromisoformat(q["end_hour"][0])
        times = []
        t = start
        while t <= end:
            times.append(t.strftime("%Y-%m-%dT%H:00"))
            t += timedelta(hours=1)
        out = []
        for lat, lon in zip(lats, lons):
            windy = windy_lon_range[0] <= float(lon) <= windy_lon_range[1]
            n = len(times)
            out.append({"latitude": float(lat), "longitude": float(lon), "hourly": {
                "time": times, "wind_speed_10m": [45.0 if windy else 8.0] * n, "wind_gusts_10m": [50.0] * n,
                "rain": [0.0] * n, "showers": [0.0] * n, "snowfall": [0.0] * n}})
        return 200, {}, json.dumps(out if len(out) > 1 else out[0])

    return handler


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def mocked():
    a, b = PLACES["Dallas"], PLACES["Houston"]
    fast_windy = _osrm_route(_line(a, b, bend=0.0), mph=60)        # straight, windy band
    slower_calm = _osrm_route(_line(a, b, bend=-0.9), mph=55)      # bends west, out of the wind
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_callback(responses.GET, re.compile(r"https://photon\.komoot\.io/.*"), callback=_photon)
        rsps.add(responses.GET, re.compile(r"https://router\.project-osrm\.org/route/v1/driving/[^;]+;[^;]+\?.*"),
                 json={"code": "Ok", "routes": [fast_windy, slower_calm]})
        # Via-point requests (3 coordinates): return a third, eastern route.
        rsps.add(responses.GET, re.compile(r"https://router\.project-osrm\.org/route/v1/driving/[^;]+;[^;]+;[^;]+\?.*"),
                 json={"code": "Ok", "routes": [_osrm_route(_line(a, b, bend=0.8), mph=50)]})
        rsps.add_callback(responses.GET, re.compile(r"https://api\.open-meteo\.com/.*"), callback=_meteo_factory((-96.3, -95.9)))
        yield rsps


def _body(**over):
    body = {
        "origin": "Dallas, TX",
        "destination": "Houston, TX",
        "departure": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "load_lbs": 35000,
        "interval_mi": 10,
    }
    body.update(over)
    return body


def test_plan_returns_three_routes_and_avoids_wind(mocked):
    res = APIClient().post("/api/plan", _body(), format="json")
    assert res.status_code == 200, res.content
    data = res.json()
    assert len(data["routes"]) == 3
    by_id = {r["id"]: r for r in data["routes"]}
    # Route A (fastest) crosses 45 mph wind with a 35,000 lb load → No Travel per load rules.
    assert by_id["A"]["summary"]["miles_by_level"]["no_travel"] > 0
    assert data["recommendation"]["route_id"] != "A"
    assert sum(r["recommended"] for r in data["routes"]) == 1
    # Checkpoints every 10 miles with increasing ETAs.
    cps = by_id["B"]["checkpoints"]
    assert cps[1]["mile"] == 10
    etas = [c["eta"] for c in cps]
    assert etas == sorted(etas)


def test_light_load_is_only_severe(mocked):
    data = APIClient().post("/api/plan", _body(load_lbs=20000), format="json").json()
    a = next(r for r in data["routes"] if r["id"] == "A")
    assert a["summary"]["miles_by_level"]["no_travel"] == 0
    assert a["summary"]["miles_by_level"]["severe"] > 0


def test_heatmap_has_49_hourly_frames(mocked):
    client = APIClient()
    plan = client.post("/api/plan", _body(), format="json").json()
    hm = client.get(f"/api/heatmap/{plan['plan_id']}").json()
    assert hm["hours"] == 49
    assert len(hm["layers"]["risk"]) == 49
    assert len(hm["layers"]["risk"][0]) == len(hm["points"]) > 0


def test_validation_errors():
    client = APIClient()
    res = client.post("/api/plan", _body(interval_mi=15, load_lbs=-1), format="json")
    assert res.status_code == 400
    assert set(res.json()["fields"]) >= {"interval_mi", "load_lbs"}
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert client.post("/api/plan", _body(departure=past), format="json").status_code == 400


def test_unknown_place(mocked):
    res = APIClient().post("/api/plan", _body(destination="Atlantis"), format="json")
    assert res.status_code == 422
    assert res.json()["field"] == "destination"


def test_expired_plan_heatmap():
    assert APIClient().get("/api/heatmap/doesnotexist").status_code == 404
