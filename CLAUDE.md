# CLAUDE.md — token-economics dev guide

The LLM-cost interview question ("100K users x 10 interactions x 2K tokens ≈ $/day?")
answered with a real calculator and a measurement harness. Mock-first: everything runs
key-free and deterministic; real Claude / Bedrock measurement is an optional extra.

## Layout

- `src/tokeneconomics/` — src-layout package (hatchling)
  - `config.py` — defaults (seed 42, 30-day month, canonical workload), pricing-path resolution
  - `pricing.py` — load + validate `data/pricing.yaml` (`PricingError` on any problem)
  - `workload.py` — `Workload` / `TokenDistribution` dataclasses
  - `calculator.py` — REAL cost math: $/day, $/month, per-user, tier sensitivity
  - `latency.py` — streaming TTFT + tokens/sec harness; `MockBackend` (deterministic,
    seeded `random.Random` passed in — never argless randomness), `AnthropicBackend`,
    `BedrockBackend`; p50/p95/p99 aggregation
  - `routing.py` — REAL frontier math (share -> cost/quality); mirrors sibling `llm-router`
  - `cache.py` — REAL savings-curve math incl. false-hit penalty; mirrors sibling `semantic-cache`
  - `report.py` — markdown case-study generator (charts stubbed)
  - `cli.py` — `token-economics estimate|measure|frontier|report`, all accept `--mock`
- `data/pricing.yaml` — per-1M-token price SNAPSHOT. Never hardcode prices in code;
  never present snapshot values as current fact — always "verify before use".
- `tests/` — hand-computed expected values (math worked in the test docstrings)

## Commands

```bash
# NEVER conda base / system python — use the claude env
~/miniconda3/envs/claude/bin/pip install -e ".[dev]"
~/miniconda3/envs/claude/bin/python -m pytest -q

token-economics estimate --mock                 # sensitivity table, all tiers
token-economics estimate --mock --model claude-sonnet
token-economics measure --mock --samples 50 --seed 42
token-economics measure --backend bedrock       # real (extras: bedrock; creds via ~/.env)
token-economics frontier --mock
token-economics report --mock --with-latency --out reports/case-study.md
```

Extras: `dev` (pytest), `claude` (anthropic), `bedrock` (anthropic[bedrock]+dotenv),
`charts` (matplotlib).

## House rules

- Deterministic mock first; real providers at temperature 0.
- Explicit seeds everywhere — RNGs are constructed by the caller and passed in.
- NEVER fabricate measured numbers. README results stay "TBD" until actually run.
- Pricing lives only in `data/pricing.yaml`, always labeled "snapshot — verify
  against current provider pricing before use".
- Quality scores in the routing frontier are placeholder policy inputs until
  measured (the sibling repo `llm-router` is where they get measured).

## Scaffold status

Calculator / routing / cache math and the mock latency path are real and tested.
Real-provider latency measurement, chart rendering, and the measured case study
are TODO (see README roadmap).
