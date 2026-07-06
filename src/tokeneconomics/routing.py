"""Routing economics — cost/quality frontier for a two-tier routing policy.

Policy model: route a share s of interactions to the small tier and 1-s to the
large tier. Cost blends linearly by construction; quality is modeled as a
linear blend of per-tier quality scores, which is the standard first-order
assumption (a routed query gets the quality of whichever model served it).

This mirrors the sibling repo `llm-router` (which *learns/decides* the share
per query); here we take the share as a policy input and price it. The two
projects integrate conceptually — no import between them.
"""

from __future__ import annotations

from dataclasses import dataclass

from .calculator import estimate
from .pricing import ModelPrice
from .workload import Workload


@dataclass(frozen=True)
class FrontierPoint:
    """Economics of routing `share_small` of traffic to the small tier."""

    share_small: float
    cost_per_day: float
    quality: float
    cost_vs_all_large: float  # fraction of the all-large bill (1.0 = same)
    quality_vs_all_large: float  # fraction of all-large quality (1.0 = same)


def frontier(
    workload: Workload,
    small: ModelPrice,
    large: ModelPrice,
    small_quality: float,
    large_quality: float,
    shares: list[float] | None = None,
) -> list[FrontierPoint]:
    """Cost/quality frontier across small-tier routing shares.

    Quality scores are on an arbitrary consistent scale (e.g. eval accuracy in
    [0, 1]); only ratios and blends of them are reported.
    """
    if not 0 < small_quality <= large_quality:
        raise ValueError(
            f"expected 0 < small_quality <= large_quality, "
            f"got {small_quality} / {large_quality}"
        )
    if shares is None:
        shares = [i / 10 for i in range(11)]  # 0.0, 0.1, ..., 1.0
    cost_small = estimate(workload, small).estimate.cost_per_day
    cost_large = estimate(workload, large).estimate.cost_per_day
    points = []
    for s in shares:
        if not 0 <= s <= 1:
            raise ValueError(f"share must be in [0, 1], got {s}")
        cost = s * cost_small + (1 - s) * cost_large
        quality = s * small_quality + (1 - s) * large_quality
        points.append(
            FrontierPoint(
                share_small=s,
                cost_per_day=cost,
                quality=quality,
                cost_vs_all_large=cost / cost_large,
                quality_vs_all_large=quality / large_quality,
            )
        )
    return points


def frontier_table(points: list[FrontierPoint]) -> str:
    """Markdown table of the routing frontier."""
    lines = [
        "| Share → small | $/day | Quality | Cost vs all-large | Quality vs all-large |",
        "|---:|---:|---:|---:|---:|",
    ]
    for p in points:
        lines.append(
            f"| {p.share_small:.0%} | {p.cost_per_day:,.2f} | {p.quality:.3f} | "
            f"{p.cost_vs_all_large:.1%} | {p.quality_vs_all_large:.1%} |"
        )
    return "\n".join(lines)
