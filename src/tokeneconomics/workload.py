"""Workload specification: users x interactions/day x token distributions.

Cost math uses expected (mean) token counts — that is exactly what a budget
estimate is. The distribution carries an optional p95 so reports can show a
tail-scenario column without pretending the mean is the whole story.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import config


@dataclass(frozen=True)
class TokenDistribution:
    """Token-count distribution for one direction (input or output)."""

    mean: float
    p95: float | None = None

    def __post_init__(self) -> None:
        if self.mean <= 0:
            raise ValueError(f"token mean must be > 0, got {self.mean}")
        if self.p95 is not None and self.p95 < self.mean:
            raise ValueError(f"p95 ({self.p95}) cannot be below mean ({self.mean})")


@dataclass(frozen=True)
class Workload:
    """A daily traffic spec: who calls, how often, with how many tokens."""

    users: int
    interactions_per_user_per_day: float
    input_tokens: TokenDistribution
    output_tokens: TokenDistribution

    def __post_init__(self) -> None:
        if self.users <= 0:
            raise ValueError(f"users must be > 0, got {self.users}")
        if self.interactions_per_user_per_day <= 0:
            raise ValueError(
                f"interactions_per_user_per_day must be > 0, "
                f"got {self.interactions_per_user_per_day}"
            )

    @property
    def interactions_per_day(self) -> float:
        return self.users * self.interactions_per_user_per_day

    @property
    def input_tokens_per_day(self) -> float:
        return self.interactions_per_day * self.input_tokens.mean

    @property
    def output_tokens_per_day(self) -> float:
        return self.interactions_per_day * self.output_tokens.mean


def default_workload() -> Workload:
    """The canonical interview workload: 100K users x 10/day x (1500 in + 500 out)."""
    return Workload(
        users=config.DEFAULT_USERS,
        interactions_per_user_per_day=config.DEFAULT_INTERACTIONS_PER_USER_PER_DAY,
        input_tokens=TokenDistribution(mean=config.DEFAULT_INPUT_TOKENS_MEAN),
        output_tokens=TokenDistribution(mean=config.DEFAULT_OUTPUT_TOKENS_MEAN),
    )
