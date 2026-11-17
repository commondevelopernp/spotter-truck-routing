"""Truck ETA model.

The routing API returns car travel times. For a loaded truck we:
1. cap the speed of every segment at TRUCK_MAX_MPH (US trucks are commonly
   governed at 62–68 mph and many states have lower truck limits), and
2. optionally add FMCSA hours-of-service stops: a 30-minute break after 8 hours
   of driving and a 10-hour rest after 11 hours of driving.

Because weather is sampled at the truck's ETA at each checkpoint, these stops
matter: on a 900-mile trip the second half is driven the next day.
"""
from __future__ import annotations

from typing import Sequence

TRUCK_MAX_MPH = 65.0
BREAK_AFTER_H = 8.0
BREAK_H = 0.5
SHIFT_DRIVE_H = 11.0
REST_H = 10.0


def truck_segment_hours(seg_miles: Sequence[float], seg_car_seconds: Sequence[float], max_mph: float = TRUCK_MAX_MPH) -> list[float]:
    out = []
    for miles, secs in zip(seg_miles, seg_car_seconds):
        car_h = max(secs, 0.0) / 3600.0
        min_truck_h = miles / max_mph
        out.append(max(car_h, min_truck_h))
    return out


def elapsed_with_hos(driving_h: float) -> float:
    """Wall-clock hours needed to accumulate `driving_h` hours of driving under the simplified HOS rules."""
    elapsed = 0.0
    remaining = driving_h
    while True:
        # One shift: up to 11h of driving, with a 30-min break once 8h is reached.
        shift = min(remaining, SHIFT_DRIVE_H)
        elapsed += shift
        if shift > BREAK_AFTER_H:
            elapsed += BREAK_H
        remaining -= shift
        if remaining <= 1e-9:
            return elapsed
        elapsed += REST_H


def stops_for(driving_h: float) -> list[dict]:
    """The HOS stops the driver will take over a trip of `driving_h` driving hours (for display)."""
    stops = []
    driven = 0.0
    while driven + 1e-9 < driving_h:
        if driven + BREAK_AFTER_H < driving_h and BREAK_AFTER_H < SHIFT_DRIVE_H:
            stops.append({"type": "break", "after_driving_h": driven + BREAK_AFTER_H, "duration_h": BREAK_H})
        if driven + SHIFT_DRIVE_H < driving_h:
            stops.append({"type": "rest", "after_driving_h": driven + SHIFT_DRIVE_H, "duration_h": REST_H})
        driven += SHIFT_DRIVE_H
    return stops
