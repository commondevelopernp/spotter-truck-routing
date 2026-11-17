from planner.domain.recommend import explain, owned_miles, rank, summarize
from planner.domain.risk import Risk

L, M, H, S, N = Risk.LOW, Risk.MODERATE, Risk.HIGH, Risk.SEVERE, Risk.NO_TRAVEL


def test_owned_miles_cover_route_exactly_once():
    w = owned_miles([0, 25, 50, 60])
    assert w == [12.5, 25, 17.5, 5]
    assert sum(w) == 60


def test_summary_counts_miles_by_level():
    s = summarize("A", 50, 1, [0, 25, 50], [L, S, L])
    assert s.miles_by_level["severe"] == 25
    assert s.miles_by_level["low"] == 25
    assert s.avg_risk == 3 * 25 / 50
    assert s.max_level == S


def test_ranking_follows_spec_priority():
    fast_but_severe = summarize("A", 100, 1.5, [0, 50, 100], [L, S, L])
    slow_but_high = summarize("B", 120, 2.5, [0, 60, 120], [L, H, L])
    slowest_clean = summarize("C", 150, 3.0, [0, 75, 150], [L, M, L])
    order = [s.route_id for s in rank([fast_but_severe, slow_but_high, slowest_clean])]
    assert order == ["C", "B", "A"]


def test_ties_fall_back_to_travel_time():
    a = summarize("A", 100, 2.0, [0, 100], [L, L])
    b = summarize("B", 90, 1.8, [0, 90], [L, L])
    assert rank([a, b])[0].route_id == "B"


def test_no_travel_routes_are_last_resort():
    blocked = summarize("A", 100, 1, [0, 50, 100], [L, N, L])
    severe = summarize("B", 100, 2, [0, 50, 100], [S, S, S])
    assert rank([blocked, severe])[0].route_id == "B"


def test_explanation_names_deciding_criterion():
    a = summarize("A", 100, 2.0, [0, 100], [L, L])
    b = summarize("B", 100, 1.0, [0, 50, 100], [L, H, L])
    best, *others = rank([a, b])
    assert best.route_id == "A"
    assert "High miles" in explain(best, others)
