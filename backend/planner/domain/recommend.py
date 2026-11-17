"""Route summaries and recommendation.

Mile attribution: each checkpoint "owns" the stretch of road closest to it
(half the gap to the previous checkpoint plus half the gap to the next one).
That way every mile of the route is counted exactly once and a single bad
reading is not smeared over two whole intervals.

Recommendation, as the spec orders it:
  1. fewest Severe miles  2. fewest High miles  3. lowest average risk  4. shortest time.
Routes with any No Travel miles are only recommended when every route has them
(then the one with the fewest No Travel miles wins and the UI warns the driver).
Comparisons use small tolerances so that, e.g., 0.3 Severe miles of difference —
well below the sampling resolution — does not force a much longer route.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cmp_to_key
from typing import Sequence

from .risk import Risk

MILES_TOLERANCE = 1.0  # below sampling resolution; treat as equal
AVG_RISK_TOLERANCE = 0.001  # float noise only; the spec ranks average risk strictly above time


@dataclass
class RouteSummary:
    route_id: str
    distance_mi: float
    duration_h: float
    miles_by_level: dict[str, float]
    avg_risk: float
    max_level: Risk

    @property
    def no_travel_mi(self) -> float:
        return self.miles_by_level[Risk.NO_TRAVEL.key]

    @property
    def severe_mi(self) -> float:
        return self.miles_by_level[Risk.SEVERE.key]

    @property
    def high_mi(self) -> float:
        return self.miles_by_level[Risk.HIGH.key]

    def to_dict(self) -> dict:
        return {
            "distance_mi": round(self.distance_mi, 1),
            "duration_h": round(self.duration_h, 2),
            "miles_by_level": {k: round(v, 1) for k, v in self.miles_by_level.items()},
            "avg_risk": round(self.avg_risk, 3),
            "max_level": self.max_level.key,
        }


def owned_miles(checkpoint_miles: Sequence[float]) -> list[float]:
    n = len(checkpoint_miles)
    if n == 1:
        return [0.0]
    out = []
    for i, m in enumerate(checkpoint_miles):
        left = (m - checkpoint_miles[i - 1]) / 2 if i > 0 else 0.0
        right = (checkpoint_miles[i + 1] - m) / 2 if i < n - 1 else 0.0
        out.append(left + right)
    return out


def summarize(route_id: str, distance_mi: float, duration_h: float, checkpoint_miles: Sequence[float], levels: Sequence[Risk]) -> RouteSummary:
    weights = owned_miles(checkpoint_miles)
    by_level = {r.key: 0.0 for r in Risk}
    for w, lvl in zip(weights, levels):
        by_level[lvl.key] += w
    total = sum(weights)
    avg = sum(w * int(l) for w, l in zip(weights, levels)) / total if total else float(int(max(levels)))
    return RouteSummary(route_id, distance_mi, duration_h, by_level, avg, max(levels))


def _cmp_float(a: float, b: float, tol: float) -> int:
    if abs(a - b) <= tol:
        return 0
    return -1 if a < b else 1


def compare(a: RouteSummary, b: RouteSummary) -> int:
    for x, y, tol in (
        (a.no_travel_mi, b.no_travel_mi, MILES_TOLERANCE),
        (a.severe_mi, b.severe_mi, MILES_TOLERANCE),
        (a.high_mi, b.high_mi, MILES_TOLERANCE),
        (a.avg_risk, b.avg_risk, AVG_RISK_TOLERANCE),
        (a.duration_h, b.duration_h, 0.0),
    ):
        c = _cmp_float(x, y, tol)
        if c:
            return c
    return 0


def rank(summaries: Sequence[RouteSummary]) -> list[RouteSummary]:
    return sorted(summaries, key=cmp_to_key(compare))


def explain(best: RouteSummary, others: Sequence[RouteSummary]) -> str:
    """One human-readable sentence on why `best` beat the runner-up."""
    if not others:
        return "Only one route option was available."
    if best.no_travel_mi > MILES_TOLERANCE:
        return (
            f"Every option crosses No Travel conditions; this one has the fewest ({best.no_travel_mi:.0f} mi). "
            "Consider delaying departure."
        )
    runner = others[0]
    criteria = [
        ("No Travel miles", best.no_travel_mi, runner.no_travel_mi, MILES_TOLERANCE, "{:.0f} mi"),
        ("Severe miles", best.severe_mi, runner.severe_mi, MILES_TOLERANCE, "{:.0f} mi"),
        ("High miles", best.high_mi, runner.high_mi, MILES_TOLERANCE, "{:.0f} mi"),
        ("average risk", best.avg_risk, runner.avg_risk, AVG_RISK_TOLERANCE, "{:.2f}"),
        ("travel time", best.duration_h, runner.duration_h, 0.0, "{:.1f} h"),
    ]
    tied = []
    for name, mine, theirs, tol, fmt in criteria:
        if _cmp_float(mine, theirs, tol) == 0:
            if mine > tol or theirs > tol:
                tied.append(name)
            continue
        prefix = f"Ties on {', '.join(tied)}; " if tied else ""
        return f"{prefix}{'w' if prefix else 'W'}ins on {name}: {fmt.format(mine)} vs {fmt.format(theirs)} on the next-best option."
    return "All options are equivalent; picked the first one."
