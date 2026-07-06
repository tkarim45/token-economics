"""Schema validation for data/pricing.yaml and the loader's failure modes."""

from pathlib import Path

import pytest

from tokeneconomics.pricing import PricingError, load_pricing

REPO_PRICING = Path(__file__).resolve().parents[1] / "data" / "pricing.yaml"


def test_repo_snapshot_loads_and_validates():
    table = load_pricing(REPO_PRICING)
    assert len(table.models) >= 3
    tiers = {p.tier for p in table.models.values()}
    assert tiers == {"small", "medium", "large"}
    for price in table.models.values():
        assert price.input_per_mtok > 0
        assert price.output_per_mtok > 0
        # Output tokens are never cheaper than input tokens in any real table.
        assert price.output_per_mtok >= price.input_per_mtok


def test_repo_snapshot_is_labeled_verify_before_use():
    # House rule: snapshot prices must never masquerade as current fact.
    table = load_pricing(REPO_PRICING)
    assert "verify" in table.snapshot_note.lower()


def test_cost_per_interaction_hand_computed():
    # 1000 in x $3/1M + 200 out x $15/1M = 0.003 + 0.003 = $0.006
    table = load_pricing(REPO_PRICING)
    mid = table.by_tier("medium")
    assert mid.cost_per_interaction(1_000, 200) == pytest.approx(
        (1_000 * mid.input_per_mtok + 200 * mid.output_per_mtok) / 1e6
    )


def test_missing_file_raises():
    with pytest.raises(PricingError, match="not found"):
        load_pricing("/nonexistent/pricing.yaml")


def test_missing_models_key_raises(tmp_path):
    bad = tmp_path / "p.yaml"
    bad.write_text("snapshot_note: x\n")
    with pytest.raises(PricingError, match="models"):
        load_pricing(bad)


def test_bad_tier_raises(tmp_path):
    bad = tmp_path / "p.yaml"
    bad.write_text(
        "models:\n  m:\n    tier: gigantic\n    input_per_mtok: 1\n    output_per_mtok: 2\n"
    )
    with pytest.raises(PricingError, match="tier"):
        load_pricing(bad)


def test_nonpositive_price_raises(tmp_path):
    bad = tmp_path / "p.yaml"
    bad.write_text(
        "models:\n  m:\n    tier: small\n    input_per_mtok: -1\n    output_per_mtok: 2\n"
    )
    with pytest.raises(PricingError, match="positive"):
        load_pricing(bad)


def test_unknown_model_lookup_raises():
    table = load_pricing(REPO_PRICING)
    with pytest.raises(PricingError, match="unknown model"):
        table.get("gpt-42")
