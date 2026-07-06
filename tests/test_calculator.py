"""Calculator math verified against hand-computed values.

Canonical interview workload: 100,000 users x 10 interactions/day
= 1,000,000 interactions/day, with 1,500 input + 500 output tokens each.

Hand computation on the mid-tier snapshot price ($3 in / $15 out per 1M):
  input tokens/day  = 1e6 x 1500 = 1.5e9  -> 1.5e9 x 3.00 / 1e6 = $4,500/day
  output tokens/day = 1e6 x  500 = 5.0e8  -> 5.0e8 x 15.0 / 1e6 = $7,500/day
  total             = $12,000/day = $360,000 per 30-day month
  per interaction   = 12000 / 1e6 = $0.012
  per user per day  = 12000 / 1e5 = $0.12  -> $3.60/user/month
"""

import pytest

from tokeneconomics.calculator import estimate, sensitivity
from tokeneconomics.pricing import ModelPrice, PricingTable
from tokeneconomics.workload import TokenDistribution, Workload

MID = ModelPrice("mid", "medium", input_per_mtok=3.00, output_per_mtok=15.00)
SMALL = ModelPrice("small", "small", input_per_mtok=0.80, output_per_mtok=4.00)
LARGE = ModelPrice("large", "large", input_per_mtok=15.00, output_per_mtok=75.00)

CANONICAL = Workload(
    users=100_000,
    interactions_per_user_per_day=10,
    input_tokens=TokenDistribution(mean=1_500),
    output_tokens=TokenDistribution(mean=500),
)


def test_canonical_workload_mid_tier():
    row = estimate(CANONICAL, MID)
    e = row.estimate
    assert e.input_cost_per_day == pytest.approx(4_500.0)
    assert e.output_cost_per_day == pytest.approx(7_500.0)
    assert e.cost_per_day == pytest.approx(12_000.0)
    assert e.cost_per_month == pytest.approx(360_000.0)  # 30-day convention
    assert row.cost_per_interaction == pytest.approx(0.012)
    assert row.cost_per_user_per_day == pytest.approx(0.12)
    assert row.cost_per_user_per_month == pytest.approx(3.60)


def test_small_and_large_tiers_hand_computed():
    # small: 1.5e9 x 0.80/1e6 = 1200 ; 5e8 x 4.00/1e6 = 2000 ; total 3200/day
    assert estimate(CANONICAL, SMALL).estimate.cost_per_day == pytest.approx(3_200.0)
    # large: 1.5e9 x 15/1e6 = 22500 ; 5e8 x 75/1e6 = 37500 ; total 60000/day
    assert estimate(CANONICAL, LARGE).estimate.cost_per_day == pytest.approx(60_000.0)


def test_tiny_workload_exact():
    # 10 users x 2/day = 20 interactions x (100 in + 50 out)
    # input:  20 x 100 = 2000 tokens -> 2000 x 3 / 1e6 = $0.006
    # output: 20 x  50 = 1000 tokens -> 1000 x 15 / 1e6 = $0.015
    w = Workload(10, 2, TokenDistribution(mean=100), TokenDistribution(mean=50))
    row = estimate(w, MID)
    assert row.estimate.input_cost_per_day == pytest.approx(0.006)
    assert row.estimate.output_cost_per_day == pytest.approx(0.015)
    assert row.estimate.cost_per_day == pytest.approx(0.021)


def test_sensitivity_sorted_cheapest_first():
    table = PricingTable(
        models={"large": LARGE, "small": SMALL, "mid": MID}, snapshot_note="test"
    )
    rows = sensitivity(CANONICAL, table)
    assert [r.estimate.model_id for r in rows] == ["small", "mid", "large"]
    costs = [r.estimate.cost_per_day for r in rows]
    assert costs == sorted(costs)


def test_workload_validation():
    with pytest.raises(ValueError):
        Workload(0, 1, TokenDistribution(mean=1), TokenDistribution(mean=1))
    with pytest.raises(ValueError):
        TokenDistribution(mean=0)
    with pytest.raises(ValueError):
        TokenDistribution(mean=100, p95=50)  # p95 below mean is nonsense
