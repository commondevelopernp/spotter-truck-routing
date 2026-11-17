import pytest

from planner.domain.risk import Risk, Weather, apply_load_rules, assess, classify_rain, classify_snow, classify_wind


@pytest.mark.parametrize(
    "mph, expected",
    [(0, Risk.LOW), (24.9, Risk.LOW), (25, Risk.MODERATE), (34.9, Risk.MODERATE), (35, Risk.HIGH),
     (44.9, Risk.HIGH), (45, Risk.SEVERE), (54.9, Risk.SEVERE), (55, Risk.NO_TRAVEL), (80, Risk.NO_TRAVEL)],
)
def test_wind_thresholds(mph, expected):
    assert classify_wind(mph) == expected


@pytest.mark.parametrize(
    "rate, expected",
    [(0, Risk.LOW), (0.099, Risk.LOW), (0.10, Risk.MODERATE), (0.25, Risk.HIGH), (0.49, Risk.HIGH),
     (0.50, Risk.SEVERE), (1.00, Risk.SEVERE), (1.01, Risk.NO_TRAVEL)],
)
def test_rain_thresholds(rate, expected):
    assert classify_rain(rate) == expected


@pytest.mark.parametrize(
    "rate, expected",
    [(0.49, Risk.LOW), (0.5, Risk.MODERATE), (1.0, Risk.HIGH), (2.0, Risk.SEVERE), (3.0, Risk.SEVERE), (3.1, Risk.NO_TRAVEL)],
)
def test_snow_thresholds(rate, expected):
    assert classify_snow(rate) == expected


@pytest.mark.parametrize(
    "wind, load, expected",
    [
        (60, 0, Risk.NO_TRAVEL),           # >=55 mph: No Travel for any load
        (50, 30_000, None),                 # exactly 30,000 lb is not "> 30,000"
        (50, 30_001, Risk.NO_TRAVEL),
        (40, 40_000, None),
        (40, 40_001, Risk.SEVERE),
        (30, 80_000, None),                 # below 35 mph, load does not matter
    ],
)
def test_load_rules(wind, load, expected):
    assert apply_load_rules(wind, load) == expected


def test_assess_takes_worst_condition_and_explains_it():
    a = assess(Weather(wind_mph=10, rain_in_hr=0.3, snow_in_hr=0.6), load_lbs=20_000)
    assert a.level == Risk.HIGH
    assert a.reasons == ["Rain 0.30 in/hr"]


def test_assess_load_escalates_wind():
    light = assess(Weather(wind_mph=48, rain_in_hr=0, snow_in_hr=0), load_lbs=20_000)
    heavy = assess(Weather(wind_mph=48, rain_in_hr=0, snow_in_hr=0), load_lbs=35_000)
    assert light.level == Risk.SEVERE
    assert heavy.level == Risk.NO_TRAVEL
    assert any("load" in r for r in heavy.reasons)


def test_assess_calm_has_no_reasons():
    assert assess(Weather(5, 0, 0), 10_000).reasons == []
