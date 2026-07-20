# token-economics

**The LLM-cost interview question, answered with measured data.**

Every LLM-engineering interview eventually asks some version of:

> *"You have 100K users, each sending ~10 interactions a day at ~2K tokens each.
> What does that cost per day? Per user? What's your TTFT budget? When does
> routing or caching pay for itself?"*

Recruiters explicitly test whether you can do token-level cost and latency
estimation on your feet. This repo **is that math**, a numbers-first case study
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
  snapshot, **verify against current provider pricing before using any dollar
  figure from this repo.**

```bash
pip install -e ".[dev]"            # + [claude] / [bedrock] / [charts] extras

token-economics estimate --mock                    # sensitivity across tiers
token-economics measure  --mock --samples 50       # TTFT & tok/s percentiles
token-economics frontier --mock                    # routing cost/quality frontier
token-economics report   --mock --with-latency     # full markdown case study
```

## Worked example: the canonical interview question

100,000 users × 10 interactions/day = **1,000,000 interactions/day**, each with
~2K tokens (1,500 input + 500 output). Symbolically:

```
cost/day = interactions/day × (E[input_tokens] × P_in + E[output_tokens] × P_out) / 1e6
```

Computed by the calculator from the mid-tier snapshot price in `data/pricing.yaml`
($3 in / $15 out per 1M tokens, *snapshot values, verify before use*):

```
input:  1e6 × 1,500 tokens × $3.00/1M  = $4,500/day
output: 1e6 ×   500 tokens × $15.00/1M = $7,500/day
total:  $12,000/day  ≈  $360K/month  =  $0.012/interaction  =  $3.60/user/month
```

This is pure arithmetic from the pricing snapshot (exactly what
`token-economics estimate --mock` prints), not a measurement, and the reason
output tokens dominate the bill at a 3:1 input:output ratio is that output
prices are ~5× input prices.

## Results

There are **two distinct categories** of number below, kept strictly separate:

- **(A) Cost/routing/cache math** is **real deterministic arithmetic** computed
  from the labeled pricing snapshot in [`data/pricing.yaml`](data/pricing.yaml).
  These are genuine computed results, not guesses, but they are only as current
  as the snapshot. **Verify against current provider pricing before quoting.**
- **(B) Latency** now has **two clearly separated sub-parts**: **(B1)** real
  measured TTFT/tokens-per-sec from streaming AWS Bedrock Claude Haiku 4.5 at
  temperature 0, and **(B2)** the original **mock-backend synthetic latency**
  (seeded, deterministic) kept for the reproducible offline path. The synthetic
  numbers are *not* real-provider latency and are labeled as such.

### (A) Computed from the pricing snapshot in `data/pricing.yaml`

*Computed from the pricing snapshot in `data/pricing.yaml` (verify against
current provider pricing before quoting).* All figures below are the exact
stdout of the listed commands; identical across two runs (pure arithmetic).

**Budget across tiers**, `token-economics estimate --mock`
(100,000 users × 10 interactions/day × (1,500 in + 500 out tokens)):

| Model | Tier | $/day | $/month | $/interaction | $/user/month |
|---|---|---:|---:|---:|---:|
| claude-haiku | small | 3,200.00 | 96,000.00 | 0.003200 | 0.9600 |
| claude-sonnet | medium | 12,000.00 | 360,000.00 | 0.012000 | 3.6000 |
| claude-opus | large | 60,000.00 | 1,800,000.00 | 0.060000 | 18.0000 |

**Routing cost/quality frontier**, `token-economics frontier --mock`
(quality scores are *placeholder policy inputs*, not measured, see
[llm-router](../llm-router)):

| Share → small | $/day | Quality | Cost vs all-large | Quality vs all-large |
|---:|---:|---:|---:|---:|
| 0% | 60,000.00 | 1.000 | 100.0% | 100.0% |
| 20% | 48,640.00 | 0.970 | 81.1% | 97.0% |
| 50% | 31,600.00 | 0.925 | 52.7% | 92.5% |
| 80% | 14,560.00 | 0.880 | 24.3% | 88.0% |
| 100% | 3,200.00 | 0.850 | 5.3% | 85.0% |

*(Full 11-row 0→100% table emitted by the command; abbreviated here.)*

**Cache savings curve**, from `token-economics report --mock --with-latency`
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
**$0.60/false hit**, above that price, every additional cache hit *loses* money.

### (B1) Real provider: measured against AWS Bedrock, Claude Haiku 4.5

**Real provider: AWS Bedrock, Claude Haiku 4.5**
(`us.anthropic.claude-haiku-4-5-20251001-v1:0`), region **us-east-1**,
temperature 0, **N = 20** streamed generations (max_tokens 256), measured
2026-07-06. TTFT = wall-clock to first streamed text delta; tokens/sec =
output tokens / (total − TTFT). Reproduces with:

```bash
set -a; source .env; set +a; export AWS_REGION=us-east-1
token-economics measure --backend bedrock --samples 20 --max-tokens 256
# (needs Bedrock creds in .env; the harness pins the Haiku 4.5 model id above)
```

| Metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| TTFT (s), *real Bedrock Haiku 4.5* | 1.050 | 1.941 | 2.011 |
| Tokens/sec, *real Bedrock Haiku 4.5* | 89.2 | 107.9 | 125.4 |

These are the exact stdout of one N=20 run. **Network/throttle variance is
real:** a second N=20 run agreed on p50/p95 TTFT (1.120 / 3.796 s) and
tokens/sec (90.0 / 104.4), but its TTFT **p99 spiked to 41.9 s** on a single
throttled request, the TTFT tail is dominated by occasional Bedrock throttling
/ retry, not steady-state decode. Median TTFT (~1.0 to 1.1 s) and tokens/sec
(~89 to 90 median, ~105 to 108 p95) were stable across both runs. Treat the p99 TTFT
as throttle-sensitive; re-measure for your own account/region before quoting.

### (B2) Mock backend: synthetic latency (seeded), for the offline path

**These are NOT real API latency numbers.** They come from the deterministic
mock streaming backend (`MockBackend`, seeded `random.Random`) and exist only to
exercise the p50/p95/p99 aggregation path key-free and reproducibly. Compare to
(B1) above for the real numbers.

`token-economics measure --mock --seed 42 --samples 20` (identical across runs):

| Metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| TTFT (s), *mock/synthetic* | 0.518 | 0.765 | 0.873 |
| Tokens/sec, *mock/synthetic* | 67.3 | 74.6 | 76.1 |

*Reproduce:* `token-economics measure --mock --seed 42 --samples 20`.

Test suite: **22 passed** (`python -m pytest -q`).

## Honest finding

At a 3:1 input:output token ratio, **output tokens dominate the bill**: for the
canonical workload the medium tier's $12,000/day splits $4,500 input / $7,500
output, because output is priced ~5× input ($15 vs $3 per 1M tokens in the
snapshot). This is a computed fact from the snapshot, not a measurement.

On latency, the **real** Bedrock Haiku 4.5 measurement (B1) shows the interesting
tension is in the **TTFT tail, not the median**: median TTFT sits near ~1.0 s and
tokens/sec near ~90 tok/s, and both are stable, but TTFT p99 is throttle-dominated
,  one N=20 run measured 2.0 s, another 41.9 s, entirely from a single throttled
request. So for a user-facing streaming app the p99 budget is set by provider
throttling behavior, not by steady-state decode speed, you provision for the
retry, not the median. The synthetic mock numbers (B2) understate real TTFT
(0.5 s mock median vs ~1.0 s measured) and cannot show this tail at all.

## Related sibling projects

- **[llm-router](../llm-router)**, decides *which* queries go to the small tier;
  this repo prices what that share is worth. Conceptual integration only, no import.
- **semantic-cache**, measures real hit and false-hit rates across similarity
  thresholds; this repo turns those rates into $/day.

## Roadmap (scaffold status)

- [x] Budget calculator, real, complete, hand-verified tests
- [x] Pricing snapshot loader + schema validation (`data/pricing.yaml`)
- [x] Routing frontier math + tests
- [x] Cache savings curve incl. false-hit penalty + breakeven + tests
- [x] Mock latency backend (deterministic, seeded) + p50/p95/p99 aggregation
- [x] CLI: `estimate | measure | frontier | report`, all `--mock`
- [x] Markdown case-study generator (charts stubbed)
- [x] Cost/routing/cache math computed from the pricing snapshot → filled "Results (A)"
- [x] Mock (synthetic, seeded) latency percentiles recorded → "Results (B2)"
- [x] Real-provider streaming latency runs, measured against AWS Bedrock Claude
  Haiku 4.5 (temp 0, N=20, us-east-1) → "Results (B1)"
- [ ] Matplotlib charts in the report
- [ ] Measured quality scores for the routing frontier (from llm-router evals)
- [x] Honest finding written, cost side (from snapshot) + latency side (real
  Bedrock Haiku 4.5: TTFT tail is throttle-dominated, not decode-bound)

## License

MIT © 2026 Taimour Abdul Karim
