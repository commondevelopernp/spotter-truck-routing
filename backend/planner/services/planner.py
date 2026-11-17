"""Trip planning orchestration: geocode → routes → checkpoints & ETAs → weather → risk → ranking."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from django.core.cache import cache

from ..domain import corridor as corridor_mod
from ..domain.eta import elapsed_with_hos, stops_for, truck_segment_hours
from ..domain.geo import checkpoint_miles, interpolate, simplify_by_distance
from ..domain.recommend import explain, rank, summarize
from ..domain.risk import Risk, assess
from . import geocode, routing, weather

FORECAST_HORIZON = timedelta(days=15)
HEATMAP_HOURS = 48
PLAN_TTL_S = 60 * 60
ROUTE_NAMES = ("A", "B", "C")


class PlanError(Exception):
    """User-facing planning error (bad input or impossible request)."""


@dataclass
class TripRequest:
    origin: str
    destination: str
    departure: datetime
    load_lbs: float
    interval_mi: int
    hos: bool = True


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def plan(req: TripRequest) -> dict:
    origin = geocode.resolve(req.origin)
    dest = geocode.resolve(req.destination)
    raw_routes = routing.get_routes((origin["lat"], origin["lon"]), (dest["lat"], dest["lon"]))

    # 1. Checkpoints with truck ETAs for every route.
    prepared = []
    for idx, rr in enumerate(raw_routes):
        seg_h = truck_segment_hours(rr.seg_miles, rr.seg_car_seconds)
        cum_mi, cum_h = [0.0], [0.0]
        for m, h in zip(rr.seg_miles, seg_h):
            cum_mi.append(cum_mi[-1] + m)
            cum_h.append(cum_h[-1] + h)
        total_mi, drive_h = cum_mi[-1], cum_h[-1]
        trip_h = elapsed_with_hos(drive_h) if req.hos else drive_h
        cps = []
        for mile in checkpoint_miles(total_mi, req.interval_mi):
            (lat, lon), i, t = interpolate(rr.points, cum_mi, mile)
            driven = cum_h[i] + (cum_h[i + 1] - cum_h[i]) * t if len(cum_h) > 1 else 0.0
            elapsed = elapsed_with_hos(driven) if req.hos else driven
            cps.append({"mile": mile, "lat": lat, "lon": lon, "eta": req.departure + timedelta(hours=elapsed), "drive_h": driven})
        prepared.append({"id": ROUTE_NAMES[idx], "raw": rr, "distance_mi": total_mi, "drive_h": drive_h, "trip_h": trip_h, "checkpoints": cps})

    arrival_max = max(req.departure + timedelta(hours=p["trip_h"]) for p in prepared)
    if arrival_max > datetime.now(timezone.utc) + FORECAST_HORIZON:
        raise PlanError("The trip ends beyond the 15-day forecast horizon. Choose an earlier departure.")

    # 2. One batched weather fetch for every checkpoint of every route.
    all_cps = [cp for p in prepared for cp in p["checkpoints"]]
    series = weather.fetch([(cp["lat"], cp["lon"]) for cp in all_cps], req.departure, arrival_max)
    for cp, s in zip(all_cps, series):
        wx = s.at(cp["eta"])
        cp["weather"] = wx
        cp["risk"] = assess(wx, req.load_lbs)

    # 3. Summaries and recommendation.
    summaries = {
        p["id"]: summarize(p["id"], p["distance_mi"], p["trip_h"], [c["mile"] for c in p["checkpoints"]], [c["risk"].level for c in p["checkpoints"]])
        for p in prepared
    }
    ranked = rank(list(summaries.values()))
    best = ranked[0]
    reason = explain(best, ranked[1:])
    rank_of = {s.route_id: i + 1 for i, s in enumerate(ranked)}

    # 4. Heatmap corridor (weather for it is fetched lazily by /api/heatmap).
    display = {p["id"]: simplify_by_distance(p["raw"].points, 0.25) for p in prepared}
    corridor = corridor_mod.build(list(display.values()))
    plan_id = uuid.uuid4().hex
    cache.set(f"plan:{plan_id}", {"corridor": corridor, "departure": req.departure, "load_lbs": req.load_lbs}, PLAN_TTL_S)

    routes_out = []
    for p in prepared:
        s = summaries[p["id"]]
        routes_out.append(
            {
                "id": p["id"],
                "rank": rank_of[p["id"]],
                "recommended": p["id"] == best.route_id,
                "source": p["raw"].source,
                "geometry": [[round(a, 5), round(b, 5)] for a, b in display[p["id"]]],
                "distance_mi": round(p["distance_mi"], 1),
                "driving_h": round(p["drive_h"], 2),
                "trip_h": round(p["trip_h"], 2),
                "arrival": _iso(req.departure + timedelta(hours=p["trip_h"])),
                "stops": stops_for(p["drive_h"]) if req.hos else [],
                "summary": s.to_dict(),
                "checkpoints": [
                    {
                        "mile": round(c["mile"], 1),
                        "lat": round(c["lat"], 5),
                        "lon": round(c["lon"], 5),
                        "eta": _iso(c["eta"]),
                        "weather": {
                            "wind_mph": round(c["weather"].wind_mph, 1),
                            "gust_mph": round(c["weather"].gust_mph or 0, 1),
                            "rain_in_hr": round(c["weather"].rain_in_hr, 3),
                            "snow_in_hr": round(c["weather"].snow_in_hr, 3),
                        },
                        "risk": c["risk"].to_dict(),
                    }
                    for c in p["checkpoints"]
                ],
            }
        )

    return {
        "plan_id": plan_id,
        "origin": origin,
        "destination": dest,
        "departure": _iso(req.departure),
        "load_lbs": req.load_lbs,
        "interval_mi": req.interval_mi,
        "hos": req.hos,
        "routes": routes_out,
        "recommendation": {"route_id": best.route_id, "reason": reason, "all_no_travel": best.no_travel_mi > 1.0},
        "corridor": {k: v for k, v in corridor.to_dict().items() if k != "points"} | {"count": len(corridor.points)},
    }


def heatmap(plan_id: str) -> dict:
    stored = cache.get(f"plan:{plan_id}")
    if stored is None:
        raise PlanError("This plan has expired. Please plan the trip again.")
    corridor = stored["corridor"]
    start = stored["departure"].astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=HEATMAP_HOURS)
    series = weather.fetch(corridor.points, start, end)
    start_h = int(start.timestamp() // 3600)
    hours = list(range(start_h, start_h + HEATMAP_HOURS + 1))
    risk, wind, rain, snow = [], [], [], []
    for h in hours:
        wx = [s.hour(h) for s in series]
        risk.append([int(assess(w, stored["load_lbs"]).level) for w in wx])
        wind.append([round(w.wind_mph, 1) for w in wx])
        rain.append([round(w.rain_in_hr, 3) for w in wx])
        snow.append([round(w.snow_in_hr, 3) for w in wx])
    return {
        "plan_id": plan_id,
        "start": _iso(start),
        "hours": len(hours),
        **corridor.to_dict(),
        "layers": {"risk": risk, "wind": wind, "rain": rain, "snow": snow},
        "levels": [r.key for r in Risk],
    }
