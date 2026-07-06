"""Latency measurement harness — streaming TTFT and tokens/sec.

Backends:
- MockBackend: real, deterministic, key-free. Draws samples from configurable
  synthetic distributions using an *explicitly passed* seeded random.Random —
  no argless randomness anywhere, so runs are exactly reproducible.
- AnthropicBackend / BedrockBackend: measure a real provider over streaming
  (extras: `claude` / `bedrock`). Temperature 0.

Aggregation reports p50/p95/p99 for both TTFT and tokens/sec.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Protocol

from .config import TEMPERATURE

DEFAULT_PROMPT = "In one sentence, what is a token in the context of language models?"


@dataclass(frozen=True)
class LatencySample:
    """One measured (or synthesized) streaming completion."""

    ttft_s: float
    tokens_per_s: float
    output_tokens: int
    total_s: float


@dataclass(frozen=True)
class LatencyStats:
    """Percentile summary over a batch of samples."""

    n: int
    ttft_p50: float
    ttft_p95: float
    ttft_p99: float
    tps_p50: float
    tps_p95: float
    tps_p99: float


class Backend(Protocol):
    """Anything that can produce one streaming latency sample."""

    name: str

    def sample(self, prompt: str, max_tokens: int) -> LatencySample: ...


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolation percentile (same convention as numpy default).

    q is in [0, 100]. Deterministic, stdlib-only.
    """
    if not values:
        raise ValueError("percentile of empty list")
    if not 0 <= q <= 100:
        raise ValueError(f"q must be in [0, 100], got {q}")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (q / 100) * (len(ordered) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def aggregate(samples: list[LatencySample]) -> LatencyStats:
    ttfts = [s.ttft_s for s in samples]
    tps = [s.tokens_per_s for s in samples]
    return LatencyStats(
        n=len(samples),
        ttft_p50=percentile(ttfts, 50),
        ttft_p95=percentile(ttfts, 95),
        ttft_p99=percentile(ttfts, 99),
        tps_p50=percentile(tps, 50),
        tps_p95=percentile(tps, 95),
        tps_p99=percentile(tps, 99),
    )


class MockBackend:
    """Deterministic synthetic backend so the whole pipeline runs offline.

    TTFT ~ lognormal-ish around ttft_mean_s; tokens/sec ~ gaussian around
    tps_mean, clamped positive. The RNG is injected — the caller owns the seed.
    """

    name = "mock"

    def __init__(
        self,
        rng: random.Random,
        ttft_mean_s: float = 0.45,
        ttft_sigma: float = 0.30,
        tps_mean: float = 65.0,
        tps_sigma: float = 8.0,
    ) -> None:
        self._rng = rng
        self._ttft_mean_s = ttft_mean_s
        self._ttft_sigma = ttft_sigma
        self._tps_mean = tps_mean
        self._tps_sigma = tps_sigma

    def sample(self, prompt: str, max_tokens: int) -> LatencySample:
        # lognormalvariate(mu, sigma) has median e^mu; anchor the median at ttft_mean_s.
        import math

        ttft = self._rng.lognormvariate(math.log(self._ttft_mean_s), self._ttft_sigma)
        tps = max(1.0, self._rng.gauss(self._tps_mean, self._tps_sigma))
        output_tokens = max(1, min(max_tokens, int(self._rng.gauss(max_tokens * 0.8, max_tokens * 0.1))))
        total = ttft + output_tokens / tps
        return LatencySample(
            ttft_s=ttft, tokens_per_s=tps, output_tokens=output_tokens, total_s=total
        )


class AnthropicBackend:
    """Real streaming measurement against the Anthropic API (extra: `claude`).

    TTFT = time from request start to first text delta; tokens/sec = output
    tokens / (total time - TTFT).
    """

    def __init__(self, model: str = "claude-3-5-haiku-latest") -> None:
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:  # pragma: no cover - extras path
            raise RuntimeError(
                "AnthropicBackend requires the `claude` extra: pip install -e '.[claude]'"
            ) from exc
        import anthropic

        self._client = anthropic.Anthropic()
        self._model = model
        self.name = f"anthropic:{model}"

    def sample(self, prompt: str, max_tokens: int) -> LatencySample:  # pragma: no cover - network path
        start = time.perf_counter()
        ttft: float | None = None
        output_tokens = 0
        with self._client.messages.stream(
            model=self._model,
            max_tokens=max_tokens,
            temperature=TEMPERATURE,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for _text in stream.text_stream:
                if ttft is None:
                    ttft = time.perf_counter() - start
            usage = stream.get_final_message().usage
            output_tokens = usage.output_tokens
        total = time.perf_counter() - start
        if ttft is None:
            ttft = total
        decode_time = max(total - ttft, 1e-9)
        return LatencySample(
            ttft_s=ttft,
            tokens_per_s=output_tokens / decode_time,
            output_tokens=output_tokens,
            total_s=total,
        )


class BedrockBackend(AnthropicBackend):
    """Real streaming measurement against Claude on AWS Bedrock (extra: `bedrock`)."""

    def __init__(self, model: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0") -> None:
        try:
            from anthropic import AnthropicBedrock
        except ImportError as exc:  # pragma: no cover - extras path
            raise RuntimeError(
                "BedrockBackend requires the `bedrock` extra: pip install -e '.[bedrock]'"
            ) from exc
        self._client = AnthropicBedrock()
        self._model = model
        self.name = f"bedrock:{model}"


def measure(
    backend: Backend,
    n_samples: int,
    prompt: str = DEFAULT_PROMPT,
    max_tokens: int = 256,
) -> tuple[list[LatencySample], LatencyStats]:
    """Collect n samples from a backend and aggregate to percentiles."""
    if n_samples <= 0:
        raise ValueError(f"n_samples must be > 0, got {n_samples}")
    samples = [backend.sample(prompt, max_tokens) for _ in range(n_samples)]
    return samples, aggregate(samples)
