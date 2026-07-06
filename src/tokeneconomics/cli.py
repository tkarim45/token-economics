"""CLI: token-economics estimate | measure | frontier | report (all take --mock).

`estimate`, `frontier`, and `report`'s economics are pure deterministic math —
--mock is accepted everywhere for a uniform interface. `measure` actually
contacts a provider unless --mock is given.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from . import config
from .calculator import estimate as calc_estimate
from .calculator import sensitivity_table
from .latency import AnthropicBackend, Backend, BedrockBackend, MockBackend, measure
from .pricing import PricingError, load_pricing
from .routing import frontier, frontier_table
from .report import generate_report, write_report
from .workload import TokenDistribution, Workload


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mock", action="store_true",
                        help="key-free deterministic mode (no provider calls)")
    parser.add_argument("--pricing", type=Path, default=None,
                        help="path to pricing YAML (default: data/pricing.yaml)")
    parser.add_argument("--users", type=int, default=config.DEFAULT_USERS)
    parser.add_argument("--interactions", type=float,
                        default=config.DEFAULT_INTERACTIONS_PER_USER_PER_DAY,
                        help="interactions per user per day")
    parser.add_argument("--input-tokens", type=float,
                        default=config.DEFAULT_INPUT_TOKENS_MEAN,
                        help="mean input tokens per interaction")
    parser.add_argument("--output-tokens", type=float,
                        default=config.DEFAULT_OUTPUT_TOKENS_MEAN,
                        help="mean output tokens per interaction")


def _workload(args: argparse.Namespace) -> Workload:
    return Workload(
        users=args.users,
        interactions_per_user_per_day=args.interactions,
        input_tokens=TokenDistribution(mean=args.input_tokens),
        output_tokens=TokenDistribution(mean=args.output_tokens),
    )


def _pricing(args: argparse.Namespace):
    return load_pricing(args.pricing)


def cmd_estimate(args: argparse.Namespace) -> int:
    pricing = _pricing(args)
    workload = _workload(args)
    print(f"# Workload: {workload.users:,} users x {workload.interactions_per_user_per_day:g} "
          f"interactions/day x ({workload.input_tokens.mean:g} in + "
          f"{workload.output_tokens.mean:g} out tokens)")
    print(f"# Pricing: {pricing.snapshot_note}")
    if args.model:
        row = calc_estimate(workload, pricing.get(args.model))
        e = row.estimate
        print(f"{e.model_id}: ${e.cost_per_day:,.2f}/day  ${e.cost_per_month:,.2f}/month  "
              f"${row.cost_per_user_per_month:.4f}/user/month  "
              f"${row.cost_per_interaction:.6f}/interaction")
    else:
        print()
        print(sensitivity_table(workload, pricing))
    return 0


def cmd_measure(args: argparse.Namespace) -> int:
    backend: Backend
    if args.mock:
        backend = MockBackend(rng=random.Random(args.seed))
    elif args.backend == "anthropic":
        backend = AnthropicBackend(model=args.model) if args.model else AnthropicBackend()
    elif args.backend == "bedrock":
        backend = BedrockBackend(model=args.model) if args.model else BedrockBackend()
    else:
        print("without --mock, pass --backend anthropic|bedrock", file=sys.stderr)
        return 2
    samples, stats = measure(backend, n_samples=args.samples, max_tokens=args.max_tokens)
    print(f"# backend={backend.name} n={stats.n} seed={args.seed if args.mock else 'n/a'}")
    print(f"TTFT (s):    p50={stats.ttft_p50:.3f}  p95={stats.ttft_p95:.3f}  p99={stats.ttft_p99:.3f}")
    print(f"Tokens/sec:  p50={stats.tps_p50:.1f}  p95={stats.tps_p95:.1f}  p99={stats.tps_p99:.1f}")
    return 0


def cmd_frontier(args: argparse.Namespace) -> int:
    pricing = _pricing(args)
    workload = _workload(args)
    points = frontier(
        workload,
        small=pricing.by_tier("small"),
        large=pricing.by_tier("large"),
        small_quality=args.small_quality,
        large_quality=args.large_quality,
    )
    print(f"# Pricing: {pricing.snapshot_note}")
    print(f"# Quality scores are placeholders unless measured (see llm-router).")
    print()
    print(frontier_table(points))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    pricing = _pricing(args)
    workload = _workload(args)
    stats = None
    if args.with_latency:
        backend = MockBackend(rng=random.Random(args.seed))
        _, stats = measure(backend, n_samples=args.samples)
    markdown = generate_report(workload, pricing, latency_stats=stats)
    out = write_report(markdown, args.out)
    print(f"wrote {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="token-economics",
        description="LLM token cost & latency economics — mock-first, snapshot-priced.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_est = sub.add_parser("estimate", help="workload x pricing -> $/day, $/month, per-user")
    _add_common(p_est)
    p_est.add_argument("--model", default=None, help="single model id (default: all tiers)")
    p_est.set_defaults(func=cmd_estimate)

    p_meas = sub.add_parser("measure", help="streaming TTFT + tokens/sec percentiles")
    _add_common(p_meas)
    p_meas.add_argument("--backend", choices=["anthropic", "bedrock"], default=None)
    p_meas.add_argument("--model", default=None, help="provider model id")
    p_meas.add_argument("--samples", type=int, default=20)
    p_meas.add_argument("--max-tokens", type=int, default=256)
    p_meas.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    p_meas.set_defaults(func=cmd_measure)

    p_front = sub.add_parser("frontier", help="routing cost/quality frontier table")
    _add_common(p_front)
    p_front.add_argument("--small-quality", type=float, default=0.85)
    p_front.add_argument("--large-quality", type=float, default=1.0)
    p_front.set_defaults(func=cmd_frontier)

    p_rep = sub.add_parser("report", help="emit the markdown case study")
    _add_common(p_rep)
    p_rep.add_argument("--out", type=Path, default=Path("reports/case-study.md"))
    p_rep.add_argument("--with-latency", action="store_true",
                       help="include mock latency percentiles in the report")
    p_rep.add_argument("--samples", type=int, default=20)
    p_rep.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    p_rep.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (PricingError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
