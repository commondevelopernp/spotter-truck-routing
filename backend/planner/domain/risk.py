"""Weather risk classification, implementing the assessment's risk and load rules.

Boundaries: the spec's ranges share endpoints (e.g. rain "0.10–0.25" and
"0.25–0.50"). We treat every lower bound as inclusive and move to the next level
as soon as a value reaches it, except where the spec makes the upper bound
explicit with ">" (rain > 1.00, snow > 3.0 for No Travel) — there a value of
exactly 1.00 in/hr rain or 3.0 in/hr snow is still Severe.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Risk(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return {
            Risk.LOW: "Low",
            Risk.MODERATE: "Moderate",
            Risk.HIGH: "High",
            Risk.SEVERE: "Severe",
            Risk.NO_TRAVEL: "No Travel",
        }[self]

    @property
    def key(self) -> str:
        return self.name.lower()


def classify_wind(mph: float) -> Risk:
    if mph >= 55:
        return Risk.NO_TRAVEL
    if mph >= 45:
        return Risk.SEVERE
    if mph >= 35:
        return Risk.HIGH
    if mph >= 25:
        return Risk.MODERATE
    return Risk.LOW


def classify_rain(in_per_hr: float) -> Risk:
    if in_per_hr > 1.00:
        return Risk.NO_TRAVEL
    if in_per_hr >= 0.50:
        return Risk.SEVERE
    if in_per_hr >= 0.25:
        return Risk.HIGH
    if in_per_hr >= 0.10:
        return Risk.MODERATE
    return Risk.LOW


def classify_snow(in_per_hr: float) -> Risk:
    if in_per_hr > 3.0:
        return Risk.NO_TRAVEL
    if in_per_hr >= 2.0:
        return Risk.SEVERE
    if in_per_hr >= 1.0:
        return Risk.HIGH
    if in_per_hr >= 0.5:
        return Risk.MODERATE
    return Risk.LOW


def apply_load_rules(wind_mph: float, load_lbs: float) -> Risk | None:
    """Load-dependent escalation for wind. Returns None when no load rule fires."""
    if wind_mph >= 55:
        return Risk.NO_TRAVEL
    if 45 <= wind_mph < 55 and load_lbs > 30_000:
        return Risk.NO_TRAVEL
    if 35 <= wind_mph < 45 and load_lbs > 40_000:
        return Risk.SEVERE
    return None


@dataclass(frozen=True)
class Weather:
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float
    gust_mph: float | None = None


@dataclass
class RiskAssessment:
    level: Risk
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"level": self.level.key, "label": self.level.label, "score": int(self.level), "reasons": self.reasons}


def assess(weather: Weather, load_lbs: float) -> RiskAssessment:
    """Overall checkpoint risk = the worst of wind, rain, snow and the load rules."""
    candidates: list[tuple[Risk, str]] = [
        (classify_wind(weather.wind_mph), f"Wind {weather.wind_mph:.0f} mph"),
        (classify_rain(weather.rain_in_hr), f"Rain {weather.rain_in_hr:.2f} in/hr"),
        (classify_snow(weather.snow_in_hr), f"Snow {weather.snow_in_hr:.2f} in/hr"),
    ]
    load_risk = apply_load_rules(weather.wind_mph, load_lbs)
    if load_risk is not None:
        candidates.append((load_risk, f"Wind {weather.wind_mph:.0f} mph with {load_lbs:,.0f} lb load"))

    level = max(r for r, _ in candidates)
    reasons = [] if level == Risk.LOW else [text for r, text in candidates if r == level]
    return RiskAssessment(level=level, reasons=reasons)
