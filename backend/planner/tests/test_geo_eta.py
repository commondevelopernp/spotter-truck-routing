import pytest

from planner.domain.eta import elapsed_with_hos, stops_for, truck_segment_hours
from planner.domain.geo import checkpoint_miles, cumulative_miles, haversine_mi, interpolate


def test_haversine_known_distance():
    # Dallas → Houston downtowns ≈ 225 mi great-circle
    assert haversine_mi((32.7767, -96.7970), (29.7604, -95.3698)) == pytest.approx(225, abs=3)


def test_checkpoints_include_origin_and_destination():
    assert checkpoint_miles(60, 25) == [0, 25, 50, 60]
    assert checkpoint_miles(50, 25) == [0, 25, 50]
    assert checkpoint_miles(8, 10) == [0, 8]


def test_interpolate_midpoint():
    pts = [(0.0, 0.0), (0.0, 1.0), (0.0, 2.0)]
    cum = cumulative_miles(pts)
    (lat, lon), i, t = interpolate(pts, cum, cum[-1] * 0.75)
    assert lat == pytest.approx(0)
    assert lon == pytest.approx(1.5)
    assert i == 1 and t == pytest.approx(0.5)


def test_truck_speed_cap():
    # 70 mi that a car does in 1 h (70 mph) take a truck capped at 65 mph longer.
    assert truck_segment_hours([70], [3600])[0] == pytest.approx(70 / 65)
    # Slow city segment is unchanged.
    assert truck_segment_hours([10], [1800])[0] == pytest.approx(0.5)


@pytest.mark.parametrize(
    "drive, elapsed",
    [(5, 5), (8, 8), (9, 9.5), (11, 11.5), (12, 11.5 + 10 + 1), (22, 11.5 + 10 + 11.5)],
)
def test_hours_of_service(drive, elapsed):
    assert elapsed_with_hos(drive) == pytest.approx(elapsed)


def test_hos_stops_listing():
    kinds = [s["type"] for s in stops_for(20)]
    assert kinds == ["break", "rest", "break"]
