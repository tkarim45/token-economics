"""Shared defaults and path resolution.

Everything deterministic: fixed seed, fixed days-per-month convention,
explicit pricing-file resolution order. No hidden global state.
"""

from __future__ import annotations

import os
from pathlib import Path

# Reproducibility: every stochastic component takes an explicit seeded RNG.
DEFAULT_SEED = 42

# Billing convention used throughout (documented, not hidden): 30-day month.
DAYS_PER_MONTH = 30

# Canonical interview workload: 100K users x 10 interactions/day x ~2K tokens.
DEFAULT_USERS = 100_000
DEFAULT_INTERACTIONS_PER_USER_PER_DAY = 10
DEFAULT_INPUT_TOKENS_MEAN = 1_500
DEFAULT_OUTPUT_TOKENS_MEAN = 500

# Real-provider runs are always temperature 0.
TEMPERATURE = 0.0

PRICING_ENV_VAR = "TOKEN_ECONOMICS_PRICING"


def default_pricing_path() -> Path:
    """Resolve the pricing snapshot file.

    Order: $TOKEN_ECONOMICS_PRICING -> ./data/pricing.yaml (cwd) ->
    <repo>/data/pricing.yaml relative to this file (editable install).
    """
    env = os.environ.get(PRICING_ENV_VAR)
    if env:
        return Path(env)
    cwd_candidate = Path.cwd() / "data" / "pricing.yaml"
    if cwd_candidate.is_file():
        return cwd_candidate
    # src/tokeneconomics/config.py -> repo root is parents[2]
    return Path(__file__).resolve().parents[2] / "data" / "pricing.yaml"
