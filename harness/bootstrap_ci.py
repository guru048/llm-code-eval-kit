"""
Bootstrap confidence intervals for evaluation metrics.

Uses the percentile bootstrap (Efron, 1979) with B=10,000 resamples.
Returns 95% CI by default; any confidence level is supported.

Metrics supported
-----------------
- TAS (Test Adequacy Score)          : binary pass/fail per requirement
- Pass rate                          : binary pass/fail per test
- Coverage score (per-requirement)   : continuous [0, 1]
- Sensitivity index                  : CV across N code variants
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass


@dataclass
class BootstrapCI:
    metric: str
    observed: float
    lower: float
    upper: float
    confidence: float
    n_resamples: int
    std_error: float

    def __str__(self) -> str:
        pct = int(self.confidence * 100)
        return (
            f"{self.metric}: {self.observed:.4f} "
            f"[{pct}% CI: {self.lower:.4f} – {self.upper:.4f}] "
            f"(SE={self.std_error:.4f})"
        )


def _bootstrap_ci(
    values: np.ndarray,
    statistic,
    B: int = 10_000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float, float]:
    rng  = np.random.default_rng(seed)
    obs  = float(statistic(values))
    boot = np.array([
        statistic(rng.choice(values, size=len(values), replace=True))
        for _ in range(B)
    ])
    alpha = 1 - confidence
    lo    = float(np.percentile(boot, 100 * alpha / 2))
    hi    = float(np.percentile(boot, 100 * (1 - alpha / 2)))
    se    = float(np.std(boot, ddof=1))
    return obs, lo, hi, se


def compute_pass_rate_ci(
    passed: list[bool],
    B: int = 10_000,
    confidence: float = 0.95,
) -> BootstrapCI:
    vals = np.array([1.0 if p else 0.0 for p in passed])
    obs, lo, hi, se = _bootstrap_ci(vals, np.mean, B=B, confidence=confidence)
    return BootstrapCI(
        metric="pass_rate",
        observed=round(obs, 4),
        lower=round(lo, 4),
        upper=round(hi, 4),
        confidence=confidence,
        n_resamples=B,
        std_error=round(se, 4),
    )


def compute_tas_ci(
    req_met: list[bool],
    B: int = 10_000,
    confidence: float = 0.95,
) -> BootstrapCI:
    vals = np.array([1.0 if m else 0.0 for m in req_met])
    obs, lo, hi, se = _bootstrap_ci(vals, np.mean, B=B, confidence=confidence)
    return BootstrapCI(
        metric="TAS",
        observed=round(obs, 4),
        lower=round(lo, 4),
        upper=round(hi, 4),
        confidence=confidence,
        n_resamples=B,
        std_error=round(se, 4),
    )


def compute_sensitivity_ci(
    variant_scores: list[float],
    B: int = 10_000,
    confidence: float = 0.95,
) -> tuple[BootstrapCI, float]:
    """
    Returns (CI on mean TAS across variants, sensitivity index = CV).
    Sensitivity index = std / mean; higher → more unstable LLM outputs.
    """
    vals = np.array(variant_scores)
    obs, lo, hi, se = _bootstrap_ci(vals, np.mean, B=B, confidence=confidence)
    sensitivity_index = float(np.std(vals, ddof=1) / max(np.mean(vals), 1e-9))
    ci = BootstrapCI(
        metric="mean_TAS_across_variants",
        observed=round(obs, 4),
        lower=round(lo, 4),
        upper=round(hi, 4),
        confidence=confidence,
        n_resamples=B,
        std_error=round(se, 4),
    )
    return ci, round(sensitivity_index, 4)
