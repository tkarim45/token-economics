"""Cache economics — hit-rate -> savings curve, including false-hit penalty.

Model: at hit rate h, a fraction h of interactions are served from cache and
pay no model cost (gross savings = h x base cost). But a semantic cache can
serve the *wrong* cached answer to a near-miss: a fraction f of cache serves
are false hits, each costing `false_hit_cost` (e.g. the cost of the retry it
forces, or a dollarized quality penalty).

    gross_savings(h) = base_cost_per_day x h
    false_hit_cost(h) = interactions_per_day x h x f x false_hit_cost
    net_savings(h)   = gross - false-hit cost

This conceptually mirrors the sibling repo `semantic-cache`, which measures
h and f empirically across similarity thresholds; here we price the tradeoff.
No import between the projects.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CachePoint:
    """Savings economics at one cache hit rate."""

    hit_rate: float
    gross_savings_per_day: float
    false_hit_cost_per_day: float

    @property
    def net_savings_per_day(self) -> float:
        return self.gross_savings_per_day - self.false_hit_cost_per_day


def savings_curve(
    base_cost_per_day: float,
    interactions_per_day: float,
    false_hit_rate: float,
    false_hit_cost: float,
    hit_rates: list[float] | None = None,
) -> list[CachePoint]:
    """Net savings across hit rates.

    false_hit_rate: fraction of cache *serves* that are wrong (per-serve).
    false_hit_cost: USD cost incurred per false hit.
    """
    if base_cost_per_day < 0 or interactions_per_day <= 0:
        raise ValueError("base_cost_per_day must be >= 0 and interactions_per_day > 0")
    if not 0 <= false_hit_rate <= 1:
        raise ValueError(f"false_hit_rate must be in [0, 1], got {false_hit_rate}")
    if false_hit_cost < 0:
        raise ValueError(f"false_hit_cost must be >= 0, got {false_hit_cost}")
    if hit_rates is None:
        hit_rates = [i / 10 for i in range(11)]  # 0.0, 0.1, ..., 1.0
    points = []
    for h in hit_rates:
        if not 0 <= h <= 1:
            raise ValueError(f"hit rate must be in [0, 1], got {h}")
        gross = base_cost_per_day * h
        penalty = interactions_per_day * h * false_hit_rate * false_hit_cost
        points.append(
            CachePoint(
                hit_rate=h,
                gross_savings_per_day=gross,
                false_hit_cost_per_day=penalty,
            )
        )
    return points


def breakeven_false_hit_cost(
    base_cost_per_day: float, interactions_per_day: float, false_hit_rate: float
) -> float:
    """False-hit cost at which caching saves exactly nothing (any h > 0).

    net = h*(base - interactions*f*c) = 0  =>  c* = base / (interactions * f).
    Above c*, every additional hit *loses* money.
    """
    if false_hit_rate <= 0:
        return float("inf")
    return base_cost_per_day / (interactions_per_day * false_hit_rate)


def savings_table(points: list[CachePoint]) -> str:
    """Markdown table of the cache savings curve."""
    lines = [
        "| Hit rate | Gross savings $/day | False-hit cost $/day | Net savings $/day |",
        "|---:|---:|---:|---:|",
    ]
    for p in points:
        lines.append(
            f"| {p.hit_rate:.0%} | {p.gross_savings_per_day:,.2f} | "
            f"{p.false_hit_cost_per_day:,.2f} | {p.net_savings_per_day:,.2f} |"
        )
    return "\n".join(lines)
