"""Case-study report generator — `token-economics report`.

Emits a markdown case study assembling the budget sensitivity table, routing
frontier, cache savings curve, and (when measured) latency percentiles.
Charts are stubbed: if matplotlib (extra: `charts`) is installed a placeholder
chart hook runs; otherwise the report notes charts were skipped.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from . import cache as cache_mod
from . import calculator, routing
from .latency import LatencyStats
from .pricing import PricingTable
from .workload import Workload


def _charts_available() -> bool:
    try:
        import matplotlib  # noqa: F401

        return True
    except ImportError:
        return False


def render_charts(out_dir: Path) -> list[Path]:
    """Chart generation stub — wired but intentionally minimal at scaffold stage.

    TODO(scaffold): frontier + savings-curve charts once measurements exist.
    """
    if not _charts_available():
        return []
    return []  # stub: no charts emitted yet


def generate_report(
    workload: Workload,
    pricing: PricingTable,
    latency_stats: LatencyStats | None = None,
    small_quality: float = 0.85,
    large_quality: float = 1.0,
    cache_false_hit_rate: float = 0.02,
    cache_false_hit_cost: float | None = None,
) -> str:
    """Assemble the full markdown case study. Returns the markdown string."""
    small = pricing.by_tier("small")
    large = pricing.by_tier("large")
    mid_est = calculator.estimate(workload, pricing.by_tier("medium"))
    if cache_false_hit_cost is None:
        # Default penalty: the cost of one large-tier retry per false hit.
        cache_false_hit_cost = large.cost_per_interaction(
            workload.input_tokens.mean, workload.output_tokens.mean
        )

    frontier_points = routing.frontier(
        workload, small, large, small_quality=small_quality, large_quality=large_quality
    )
    cache_points = cache_mod.savings_curve(
        base_cost_per_day=mid_est.estimate.cost_per_day,
        interactions_per_day=workload.interactions_per_day,
        false_hit_rate=cache_false_hit_rate,
        false_hit_cost=cache_false_hit_cost,
    )

    sections = [
        "# Token Economics — Case Study",
        "",
        f"_Generated {date.today().isoformat()}. All prices come from the pricing "
        "snapshot in `data/pricing.yaml` — **verify against current provider pricing "
        "before publishing or acting on any dollar figure below.**_",
        "",
        "## Workload",
        "",
        f"- Users: {workload.users:,}",
        f"- Interactions per user per day: {workload.interactions_per_user_per_day:g}",
        f"- Interactions per day: {workload.interactions_per_day:,.0f}",
        f"- Mean input tokens: {workload.input_tokens.mean:g}",
        f"- Mean output tokens: {workload.output_tokens.mean:g}",
        "",
        "## Budget sensitivity across model tiers",
        "",
        calculator.sensitivity_table(workload, pricing),
        "",
        "## Routing economics (share routed to small tier)",
        "",
        f"_Quality model: linear blend, small = {small_quality}, large = "
        f"{large_quality} (placeholder scores — replace with measured evals; "
        "see sibling repo `llm-router`)._",
        "",
        routing.frontier_table(frontier_points),
        "",
        "## Cache economics (hit rate -> net savings)",
        "",
        f"_Base cost: medium tier. False-hit rate {cache_false_hit_rate:.0%} of cache "
        f"serves, penalty ${cache_false_hit_cost:.6f}/false hit (one large-tier retry). "
        "Empirical hit/false-hit rates: see sibling repo `semantic-cache`._",
        "",
        cache_mod.savings_table(cache_points),
        "",
        "## Latency (streaming TTFT and tokens/sec)",
        "",
    ]
    if latency_stats is None:
        sections.append(
            "TBD — measurements not yet run. Run `token-economics measure --mock` "
            "(offline) or with the `claude`/`bedrock` extras for real numbers."
        )
    else:
        sections += [
            f"_n = {latency_stats.n} samples._",
            "",
            "| Metric | p50 | p95 | p99 |",
            "|---|---:|---:|---:|",
            f"| TTFT (s) | {latency_stats.ttft_p50:.3f} | "
            f"{latency_stats.ttft_p95:.3f} | {latency_stats.ttft_p99:.3f} |",
            f"| Tokens/sec | {latency_stats.tps_p50:.1f} | "
            f"{latency_stats.tps_p95:.1f} | {latency_stats.tps_p99:.1f} |",
        ]
    sections += [
        "",
        "## Charts",
        "",
        "Charts are stubbed at scaffold stage"
        + ("" if _charts_available() else " (matplotlib not installed — extra: `charts`)")
        + ".",
        "",
    ]
    return "\n".join(sections)


def write_report(markdown: str, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown)
    render_charts(out_path.parent)
    return out_path
