"""Load and validate the pricing snapshot (data/pricing.yaml).

Prices are NEVER hardcoded in code — they live in the YAML snapshot, which is
explicitly labeled "verify against current provider pricing before use".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .config import default_pricing_path

VALID_TIERS = ("small", "medium", "large")


class PricingError(ValueError):
    """Raised when the pricing file is missing, malformed, or fails validation."""


@dataclass(frozen=True)
class ModelPrice:
    """Per-1M-token prices for one model. Snapshot values — verify before use."""

    model_id: str
    tier: str
    input_per_mtok: float
    output_per_mtok: float
    notes: str = ""

    def cost_per_interaction(self, input_tokens: float, output_tokens: float) -> float:
        """USD cost of a single interaction with the given token counts."""
        return (
            input_tokens * self.input_per_mtok + output_tokens * self.output_per_mtok
        ) / 1_000_000


@dataclass(frozen=True)
class PricingTable:
    models: dict[str, ModelPrice]
    snapshot_note: str

    def get(self, model_id: str) -> ModelPrice:
        try:
            return self.models[model_id]
        except KeyError:
            raise PricingError(
                f"unknown model {model_id!r}; known: {sorted(self.models)}"
            ) from None

    def by_tier(self, tier: str) -> ModelPrice:
        """First model in the given tier (tables are expected to have one per tier)."""
        for price in self.models.values():
            if price.tier == tier:
                return price
        raise PricingError(f"no model with tier {tier!r}; known tiers: "
                           f"{sorted({p.tier for p in self.models.values()})}")


def _validate_model(model_id: str, raw: object) -> ModelPrice:
    if not isinstance(raw, dict):
        raise PricingError(f"models.{model_id} must be a mapping, got {type(raw).__name__}")
    tier = raw.get("tier")
    if tier not in VALID_TIERS:
        raise PricingError(f"models.{model_id}.tier must be one of {VALID_TIERS}, got {tier!r}")
    prices: dict[str, float] = {}
    for key in ("input_per_mtok", "output_per_mtok"):
        value = raw.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise PricingError(f"models.{model_id}.{key} must be a positive number, got {value!r}")
        prices[key] = float(value)
    return ModelPrice(
        model_id=model_id,
        tier=tier,
        input_per_mtok=prices["input_per_mtok"],
        output_per_mtok=prices["output_per_mtok"],
        notes=str(raw.get("notes", "")),
    )


def load_pricing(path: str | Path | None = None) -> PricingTable:
    """Load and validate a pricing YAML file. Raises PricingError on any problem."""
    resolved = Path(path) if path is not None else default_pricing_path()
    if not resolved.is_file():
        raise PricingError(f"pricing file not found: {resolved}")
    raw = yaml.safe_load(resolved.read_text())
    if not isinstance(raw, dict) or not isinstance(raw.get("models"), dict) or not raw["models"]:
        raise PricingError(f"{resolved}: expected a top-level 'models' mapping with entries")
    models = {
        model_id: _validate_model(model_id, spec)
        for model_id, spec in raw["models"].items()
    }
    return PricingTable(
        models=models,
        snapshot_note=str(raw.get("snapshot_note", "snapshot — verify before use")),
    )
