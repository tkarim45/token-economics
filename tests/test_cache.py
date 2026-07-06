"""Cache savings-curve math verified by hand.

Setup: base cost $1,000/day, 1,000,000 interactions/day.

Case A — false-hit rate 1% of serves, $0.02 per false hit, hit rate 50%:
  gross   = 1000 x 0.5 = $500
  penalty = 1e6 x 0.5 x 0.01 x 0.02 = $100
  net     = $400

Case B (exact breakeven) — false-hit rate 5%, $0.02 per false hit:
  at ANY hit rate h: gross = 1000h ; penalty = 1e6 x h x 0.05 x 0.02 = 1000h
  -> net = 0 for every h. And breakeven cost c* = 1000/(1e6 x 0.05) = $0.02.
"""

import pytest

from tokeneconomics.cache import breakeven_false_hit_cost, savings_curve

BASE = 1_000.0
INTERACTIONS = 1_000_000.0


def test_case_a_hand_computed():
    (pt,) = savings_curve(BASE, INTERACTIONS, false_hit_rate=0.01,
                          false_hit_cost=0.02, hit_rates=[0.5])
    assert pt.gross_savings_per_day == pytest.approx(500.0)
    assert pt.false_hit_cost_per_day == pytest.approx(100.0)
    assert pt.net_savings_per_day == pytest.approx(400.0)


def test_case_b_exact_breakeven_at_every_hit_rate():
    pts = savings_curve(BASE, INTERACTIONS, false_hit_rate=0.05, false_hit_cost=0.02)
    for pt in pts:
        assert pt.net_savings_per_day == pytest.approx(0.0)
    assert breakeven_false_hit_cost(BASE, INTERACTIONS, 0.05) == pytest.approx(0.02)


def test_zero_hit_rate_saves_nothing():
    (pt,) = savings_curve(BASE, INTERACTIONS, false_hit_rate=0.02,
                          false_hit_cost=0.05, hit_rates=[0.0])
    assert pt.gross_savings_per_day == 0.0
    assert pt.false_hit_cost_per_day == 0.0
    assert pt.net_savings_per_day == 0.0


def test_perfect_cache_no_false_hits():
    # h=1, f=0: net savings = the entire base cost.
    (pt,) = savings_curve(BASE, INTERACTIONS, false_hit_rate=0.0,
                          false_hit_cost=1.0, hit_rates=[1.0])
    assert pt.net_savings_per_day == pytest.approx(BASE)
    assert breakeven_false_hit_cost(BASE, INTERACTIONS, 0.0) == float("inf")


def test_default_hit_rates_and_monotone_gross():
    pts = savings_curve(BASE, INTERACTIONS, false_hit_rate=0.01, false_hit_cost=0.001)
    assert [p.hit_rate for p in pts] == pytest.approx([i / 10 for i in range(11)])
    gross = [p.gross_savings_per_day for p in pts]
    assert gross == sorted(gross)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        savings_curve(BASE, 0, 0.01, 0.02)  # no traffic
    with pytest.raises(ValueError):
        savings_curve(BASE, INTERACTIONS, 1.5, 0.02)  # false-hit rate > 1
    with pytest.raises(ValueError):
        savings_curve(BASE, INTERACTIONS, 0.01, -0.02)  # negative penalty
    with pytest.raises(ValueError):
        savings_curve(BASE, INTERACTIONS, 0.01, 0.02, hit_rates=[2.0])
