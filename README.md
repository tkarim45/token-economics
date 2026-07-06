# token-economics

**The LLM-cost interview question, answered with measured data.**

Every LLM-engineering interview eventually asks some version of:

> *"You have 100K users, each sending ~10 interactions a day at ~2K tokens each.
> What does that cost per day? Per user? What's your TTFT budget? When does
> routing or caching pay for itself?"*

Recruiters explicitly test whether you can do token-level cost and latency
estimation on your feet. This repo **is that math** — a numbers-first case study
plus a reusable toolkit: a real budget calculator, a streaming TTFT/tokens-per-sec
measurement harness, and the routing/caching economics that decide when the
optimizations are worth it.

## How it works

```
workload spec ──┐
                ├──> calculator ──> $/day, $/month, $/user, tier sensitivity
pricing.yaml ───┘
                     latency harness ──> TTFT + tok/s, p50/p95/p99 (mock or real streaming)
                     routing frontier ──> share→small vs cost/quality (see sibling llm-router)
                     cache curve ──> hit-rate → net savings incl. false-hit penalty
                                     (see sibling semantic-cache)
                     report ──> markdown case study with all tables
```

- **Mock-first.** Every command runs key-free and deterministic with `--mock`
  (explicit seeds, no argless randomness). Real measurement against Claude
  (Anthropic API) or AWS Bedrock is an optional extra, streaming, temperature 0.
- **Prices are data, not code.** All prices live in
  [`data/pricing.yaml`](data/pricing.yaml), a clearly labeled point-in-time
  snapshot — **verify against current provider pricing before using any dollar
  figure from this repo.**

```bash
pip install -e ".[dev]"            # + [claude] / [bedrock] / [charts] extras

token-economics estimate --mock                    # sensitivity across tiers
token-economics measure  --mock --samples 50       # TTFT & tok/s percentiles
token-economics frontier --mock                    # routing cost/quality frontier
token-economics report   --mock --with-latency     # full markdown case study
```

## Worked example — the canonical interview question

100,000 users × 10 interactions/day = **1,000,000 interactions/day**, each with
~2K tokens (1,500 input + 500 output). Symbolically:

```
cost/day = interactions/day × (E[input_tokens] × P_in + E[output_tokens] × P_out) / 1e6
```

Computed by the calculator from the mid-tier snapshot price in `data/pricing.yaml`
($3 in / $15 out per 1M tokens — *snapshot values, verify before use*):

```
input:  1e6 × 1,500 tokens × $3.00/1M  = $4,500/day
output: 1e6 ×   500 tokens × $15.00/1M = $7,500/day
total:  $12,000/day  ≈  $360K/month  =  $0.012/interaction  =  $3.60/user/month
```

This is pure arithmetic from the pricing snapshot (exactly what
`token-economics estimate --mock` prints), not a measurement — and the reason
output tokens dominate the bill at a 3:1 input:output ratio is that output
prices are ~5× input prices.

## Results

There are **two distinct categories** of number below, kept strictly separate:

- **(A) Cost/routing/cache math** is **real deterministic arithmetic** computed
  from the labeled pricing snapshot in [`data/pricing.yaml`](data/pricing.yaml).
  These are genuine computed results, not guesses — but they are only as current
  as the snapshot. **Verify against current provider pricing before quoting.**
- **(B) Latency** is **mock-backend synthetic latency** (seeded, deterministic).
  It is *not* real-provider TTFT/tokens-per-sec. Real-provider streaming
  measurement (Anthropic API / AWS Bedrock, temperature 0) is still **TBD**.

### (A) Computed from the pricing snapshot in `data/pricing.yaml`

*Computed from the pricing snapshot in `data/pricing.yaml` (verify against
current provider pricing before quoting).* All figures below are the exact
stdout of the listed commands; identical across two runs (pure arithmetic).

**Budget across tiers** — `token-economics estimate --mock`
(100,000 users × 10 interactions/day × (1,500 in + 500 out tokens)):

| Model | Tier | $/day | $/month | $/interaction | $/user/month |
|---|---|---:|---:|---:|---:|
| claude-haiku | small | 3,200.00 | 96,000.00 | 0.003200 | 0.9600 |
| claude-sonnet | medium | 12,000.00 | 360,000.00 | 0.012000 | 3.6000 |
| claude-opus | large | 60,000.00 | 1,800,000.00 | 0.060000 | 18.0000 |

**Routing cost/quality frontier** — `token-economics frontier --mock`
(quality scores are *placeholder policy inputs*, not measured — see
[llm-router](../llm-router)):

| Share → small | $/day | Quality | Cost vs all-large | Quality vs all-large |
|---:|---:|---:|---:|---:|
| 0% | 60,000.00 | 1.000 | 100.0% | 100.0% |
| 20% | 48,640.00 | 0.970 | 81.1% | 97.0% |
| 50% | 31,600.00 | 0.925 | 52.7% | 92.5% |
| 80% | 14,560.00 | 0.880 | 24.3% | 88.0% |
| 100% | 3,200.00 | 0.850 | 5.3% | 85.0% |

*(Full 11-row 0→100% table emitted by the command; abbreviated here.)*

**Cache savings curve** — from `token-economics report --mock --with-latency`
(base cost = medium tier $12,000/day; false-hit rate 2% of serves; penalty
$0.060000/false hit = one large-tier retry):

| Hit rate | Gross savings $/day | False-hit cost $/day | Net savings $/day |
|---:|---:|---:|---:|
| 0% | 0.00 | 0.00 | 0.00 |
| 20% | 2,400.00 | 240.00 | 2,160.00 |
| 50% | 6,000.00 | 600.00 | 5,400.00 |
| 80% | 9,600.00 | 960.00 | 8,640.00 |
| 100% | 12,000.00 | 1,200.00 | 10,800.00 |

Breakeven false-hit cost (`cache.breakeven_false_hit_cost(12000, 1e6, 0.02)`) =
**$0.60/false hit** — above that price, every additional cache hit *loses* money.

### (B) Mock backend — synthetic latency (seeded), real-provider measurement TBD

**These are NOT real API latency numbers.** They come from the deterministic
mock streaming backend (`MockBackend`, seeded `random.Random`) and exist only to
exercise the p50/p95/p99 aggregation path. Real-provider TTFT/tokens-per-sec is
still to be measured.

`token-economics measure --mock --seed 42 --samples 20` (identical across runs):

| Metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| TTFT (s) — *mock* | 0.518 | 0.765 | 0.873 |
| Tokens/sec — *mock* | 67.3 | 74.6 | 76.1 |

*Reproduce:* `token-economics measure --mock --seed 42 --samples 20`.

Test suite: **22 passed** (`python -m pytest -q`).

## Honest finding

At a 3:1 input:output token ratio, **output tokens dominate the bill**: for the
canonical workload the medium tier's $12,000/day splits $4,500 input / $7,500
output — because output is priced ~5× input ($15 vs $3 per 1M tokens in the
snapshot). This is a computed fact from the snapshot, not a measurement. The
latency finding (does TTFT matter more to UX than tokens/sec, and by how much
per tier) requires real-provider streaming and remains **TBD** — the mock
numbers above cannot answer it.

## Related sibling projects

- **[llm-router](../llm-router)** — decides *which* queries go to the small tier;
  this repo prices what that share is worth. Conceptual integration only, no import.
- **semantic-cache** — measures real hit and false-hit rates across similarity
  thresholds; this repo turns those rates into $/day.

## Roadmap (scaffold status)

- [x] Budget calculator — real, complete, hand-verified tests
- [x] Pricing snapshot loader + schema validation (`data/pricing.yaml`)
- [x] Routing frontier math + tests
- [x] Cache savings curve incl. false-hit penalty + breakeven + tests
- [x] Mock latency backend (deterministic, seeded) + p50/p95/p99 aggregation
- [x] CLI: `estimate | measure | frontier | report`, all `--mock`
- [x] Markdown case-study generator (charts stubbed)
- [x] Cost/routing/cache math computed from the pricing snapshot → filled "Results (A)"
- [x] Mock (synthetic, seeded) latency percentiles recorded → "Results (B)"
- [ ] Real-provider streaming latency runs (Anthropic API + Bedrock, temp 0) — still pending
- [ ] Matplotlib charts in the report
- [ ] Measured quality scores for the routing frontier (from llm-router evals)
- [x] Honest finding written (cost side, from snapshot); latency finding still pending real runs

## License

MIT © 2026 Taimour Abdul Karim
