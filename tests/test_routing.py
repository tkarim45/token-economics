"""Routing frontier math verified by hand.

Workload: 1,000 users x 1/day = 1,000 interactions/day, 1,000 in + 1,000 out.
  small ($1 in / $2 out per 1M): (1000x1 + 1000x2)/1e6 = $0.003/interaction
      -> $3.00/day
  large ($10 in / $20 out per 1M): (1000x10 + 1000x20)/1e6 = $0.030/interaction
      -> $30.00/day

Frontier at share s (linear blend):
  s=0.0 -> cost 30.00, quality 1.00 (all large)
  s=0.5 -> cost 0.5x3 + 0.5x30 = 16.50, quality 0.5x0.8 + 0.5x1.0 = 0.90
  s=1.0 -> cost  3.00, quality 0.80 (all small)
"""

import pytest

from tokeneconomics.pricing import ModelPrice
from tokeneconomics.routing import frontier
from tokeneconomics.workload import TokenDistribution, Workload

SMALL = ModelPrice("s", "small", input_per_mtok=1.0, output_per_mtok=2.0)
LARGE = ModelPrice("l", "large", input_per_mtok=10.0, output_per_mtok=20.0)
W = Workload(1_000, 1, TokenDistribution(mean=1_000), TokenDistribution(mean=1_000))


def test_frontier_endpoints_and_midpoint():
    pts = frontier(W, SMALL, LARGE, small_quality=0.8, large_quality=1.0,
                   shares=[0.0, 0.5, 1.0])
    all_large, mid, all_small = pts

    assert all_large.cost_per_day == pytest.approx(30.0)
    assert all_large.quality == pytest.approx(1.0)
    assert all_large.cost_vs_all_large == pytest.approx(1.0)
    assert all_large.quality_vs_all_large == pytest.approx(1.0)

    assert mid.cost_per_day == pytest.approx(16.5)
    assert mid.quality == pytest.approx(0.9)
    assert mid.cost_vs_all_large == pytest.approx(16.5 / 30.0)  # 55%
    assert mid.quality_vs_all_large == pytest.approx(0.9)

    assert all_small.cost_per_day == pytest.approx(3.0)
    assert all_small.quality == pytest.approx(0.8)
    assert all_small.cost_vs_all_large == pytest.approx(0.1)  # 10% of the bill


def test_default_shares_are_zero_to_one_by_tenths():
    pts = frontier(W, SMALL, LARGE, small_quality=0.8, large_quality=1.0)
    assert [p.share_small for p in pts] == pytest.approx([i / 10 for i in range(11)])
    # Cost is monotonically decreasing as more traffic goes small.
    costs = [p.cost_per_day for p in pts]
    assert costs == sorted(costs, reverse=True)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        frontier(W, SMALL, LARGE, small_quality=1.1, large_quality=1.0)  # small > large
    with pytest.raises(ValueError):
        frontier(W, SMALL, LARGE, small_quality=0.0, large_quality=1.0)  # non-positive
    with pytest.raises(ValueError):
        frontier(W, SMALL, LARGE, small_quality=0.8, large_quality=1.0, shares=[1.5])
