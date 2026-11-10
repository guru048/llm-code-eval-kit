"""
Sensitivity analysis across multiple LLM-generated code variants.

Given N code files for the same spec, evaluates each one and computes:
  - Per-variant TAS, pass rate, failure distribution
  - Mean and std of TAS across variants
  - Sensitivity Index (SI) = CV of TAS = std / mean
  - Bootstrap CI on mean TAS
  - Rank ordering of variants by TAS

SI interpretation
-----------------
  SI < 0.05 : LLM is highly consistent (low spread).
  SI 0.05–0.20 : Moderate sensitivity — worth regenerating.
  SI > 0.20 : High sensitivity — LLM output unstable on this spec.
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path

from harness.spec_loader import Spec
from harness.static_checks import run_static_checks
from harness.dynamic_checks import run_dynamic_checks
from harness.requirement_tracer import trace_requirements
from harness.failure_taxonomy import classify_failures
from harness.bootstrap_ci import compute_sensitivity_ci, BootstrapCI


@dataclass
class VariantResult:
    variant_name: str
    code_path: str
    tas: float
    weighted_tas: float
    pass_rate: float
    static_score: float
    n_fully_met: int
    n_unmet: int
    dominant_failure: str | None
    rank: int = 0


@dataclass
class SensitivityReport:
    spec_name: str
    n_variants: int
    variant_results: list[VariantResult]
    mean_tas: float
    std_tas: float
    min_tas: float
    max_tas: float
    sensitivity_index: float
    si_label: str
    tas_ci: BootstrapCI
    best_variant: str
    worst_variant: str


def _si_label(si: float) -> str:
    if si < 0.05:
        return "LOW (consistent)"
    if si < 0.20:
        return "MEDIUM (moderate spread)"
    return "HIGH (unstable)"


def run_sensitivity_analysis(
    spec: Spec,
    code_paths: list[str],
    B: int = 10_000,
) -> SensitivityReport:
    required_fns = list({tc.function for tc in spec.tests})
    variant_results = []

    for path in code_paths:
        source = Path(path).read_text()
        static = run_static_checks(source, required_fns)
        dyn    = run_dynamic_checks(path, spec)
        trace  = trace_requirements(spec, dyn)
        tax    = classify_failures(spec, dyn)

        variant_results.append(VariantResult(
            variant_name=Path(path).stem,
            code_path=path,
            tas=trace.tas,
            weighted_tas=trace.weighted_tas,
            pass_rate=dyn.pass_rate,
            static_score=static.score(),
            n_fully_met=trace.n_fully_met,
            n_unmet=trace.n_unmet,
            dominant_failure=tax.dominant_mode,
        ))

    # Sort by TAS descending, assign ranks
    variant_results.sort(key=lambda v: v.tas, reverse=True)
    for i, v in enumerate(variant_results):
        v.rank = i + 1

    tas_scores = [v.tas for v in variant_results]
    ci, si     = compute_sensitivity_ci(tas_scores, B=B)

    return SensitivityReport(
        spec_name=spec.name,
        n_variants=len(variant_results),
        variant_results=variant_results,
        mean_tas=round(float(np.mean(tas_scores)), 4),
        std_tas=round(float(np.std(tas_scores, ddof=1 if len(tas_scores) > 1 else 0)), 4),
        min_tas=round(min(tas_scores), 4),
        max_tas=round(max(tas_scores), 4),
        sensitivity_index=si,
        si_label=_si_label(si),
        tas_ci=ci,
        best_variant=variant_results[0].variant_name,
        worst_variant=variant_results[-1].variant_name,
    )
