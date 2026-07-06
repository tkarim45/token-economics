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

## Measured results

**TBD — measurements not yet run.** The latency harness, routing frontier with
measured quality scores, and the generated case study will be populated from
real runs (Anthropic API / AWS Bedrock, streaming, temperature 0). No number
will appear here that wasn't actually measured.

| Question | Status |
|---|---|
| TTFT p50/p95/p99 per tier (real streaming) | TBD |
| Tokens/sec per tier (real streaming) | TBD |
| Routing frontier with *measured* quality (via [llm-router](../llm-router)) | TBD |
| Cache breakeven with *measured* hit/false-hit rates (via semantic-cache) | TBD |

## Honest finding

**TBD** — to be written after measurement. Candidate hypotheses to test rather
than assume: output-token price, not input volume, dominates cost at typical
chat ratios; TTFT differences between tiers matter more to UX than tokens/sec;
and cache false hits can erase savings entirely (the breakeven penalty for the
canonical workload is computable — `cache.breakeven_false_hit_cost`).

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
- [ ] Real streaming measurement runs (Anthropic API + Bedrock) → fill "Measured results"
- [ ] Matplotlib charts in the report
- [ ] Measured quality scores for the routing frontier (from llm-router evals)
- [ ] Honest finding written from data

## License

MIT © 2026 Taimour Abdul Karim
