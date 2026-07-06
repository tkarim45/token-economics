"""Budget calculator — the real, complete cost math.

cost/day = interactions/day x (E[input_tokens] x input_price
                               + E[output_tokens] x output_price) / 1e6

All figures are pure deterministic arithmetic over a workload spec and a
pricing snapshot; nothing here is measured or estimated by a model.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import DAYS_PER_MONTH
from .pricing import ModelPrice, PricingTable
from .workload import Workload


@dataclass(frozen=True)
class CostEstimate:
    """Cost breakdown for one (workload, model) pair. USD throughout."""

    model_id: str
    tier: str
    input_cost_per_day: float
    output_cost_per_day: float

    @property
    def cost_per_day(self) -> float:
        return self.input_cost_per_day + self.output_cost_per_day

    @property
    def cost_per_month(self) -> float:
        return self.cost_per_day * DAYS_PER_MONTH


@dataclass(frozen=True)
class WorkloadEstimate:
    """CostEstimate plus per-user / per-interaction unit economics."""

    estimate: CostEstimate
    interactions_per_day: float
    users: int

    @property
    def cost_per_interaction(self) -> float:
        return self.estimate.cost_per_day / self.interactions_per_day

    @property
    def cost_per_user_per_day(self) -> float:
        return self.estimate.cost_per_day / self.users

    @property
    def cost_per_user_per_month(self) -> float:
        return self.cost_per_user_per_day * DAYS_PER_MONTH


def estimate(workload: Workload, price: ModelPrice) -> WorkloadEstimate:
    """Expected daily/monthly/per-user cost of running the workload on one model."""
    input_cost = workload.input_tokens_per_day * price.input_per_mtok / 1_000_000
    output_cost = workload.output_tokens_per_day * price.output_per_mtok / 1_000_000
    return WorkloadEstimate(
        estimate=CostEstimate(
            model_id=price.model_id,
            tier=price.tier,
            input_cost_per_day=input_cost,
            output_cost_per_day=output_cost,
        ),
        interactions_per_day=workload.interactions_per_day,
        users=workload.users,
    )


def sensitivity(workload: Workload, pricing: PricingTable) -> list[WorkloadEstimate]:
    """Same workload priced across every model tier, cheapest first."""
    rows = [estimate(workload, price) for price in pricing.models.values()]
    return sorted(rows, key=lambda r: r.estimate.cost_per_day)


def sensitivity_table(workload: Workload, pricing: PricingTable) -> str:
    """Markdown sensitivity table across model tiers."""
    lines = [
        "| Model | Tier | $/day | $/month | $/interaction | $/user/month |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in sensitivity(workload, pricing):
        e = row.estimate
        lines.append(
            f"| {e.model_id} | {e.tier} | {e.cost_per_day:,.2f} | "
            f"{e.cost_per_month:,.2f} | {row.cost_per_interaction:.6f} | "
            f"{row.cost_per_user_per_month:.4f} |"
        )
    return "\n".join(lines)
