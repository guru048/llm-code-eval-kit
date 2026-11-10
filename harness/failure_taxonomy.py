"""
Failure-mode taxonomy for LLM-generated code.

Classifies each test failure into one of seven categories specific to
the failure patterns that LLMs exhibit:

  SYNTAX_ERROR      – code could not be parsed or imported
  MISSING_FUNCTION  – required function absent from module
  WRONG_OUTPUT      – function ran but returned wrong value
  TYPE_ERROR        – wrong return type
  RUNTIME_EXCEPTION – function threw an unexpected exception
  TIMEOUT           – function did not terminate within limit
  EDGE_CASE         – failure on a boundary / empty / extreme input
  HALLUCINATION     – function exists but behaviour bears no relation to spec

The taxonomy is determined from test metadata (tags) and error messages.
"""

from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from enum import Enum

from harness.dynamic_checks import DynamicReport, TestResult
from harness.spec_loader import Spec


class FailureMode(str, Enum):
    SYNTAX_ERROR       = "SYNTAX_ERROR"
    MISSING_FUNCTION   = "MISSING_FUNCTION"
    WRONG_OUTPUT       = "WRONG_OUTPUT"
    TYPE_ERROR         = "TYPE_ERROR"
    RUNTIME_EXCEPTION  = "RUNTIME_EXCEPTION"
    TIMEOUT            = "TIMEOUT"
    EDGE_CASE          = "EDGE_CASE"
    HALLUCINATION      = "HALLUCINATION"


EDGE_CASE_TAGS = {"edge", "boundary", "empty", "null", "zero", "negative", "overflow"}


@dataclass
class FailureTaxonomy:
    counts: dict[str, int]
    distribution: dict[str, float]   # fraction of total failures
    dominant_mode: str | None
    total_failures: int
    classified: list[dict]           # per-failure detail


def _classify_one(result: TestResult, spec: Spec) -> FailureMode:
    if result.exception:
        if "TimeoutError" in result.exception:
            return FailureMode.TIMEOUT
        if "AttributeError" in result.exception and "not found" in (result.failure_reason or ""):
            return FailureMode.MISSING_FUNCTION
        if "TypeError" in result.exception:
            return FailureMode.TYPE_ERROR
        return FailureMode.RUNTIME_EXCEPTION

    # Wrong output — check if it's an edge-case test
    tc = spec.test_by_id(result.test_id)
    if tc:
        if any(tag in EDGE_CASE_TAGS for tag in tc.tags):
            return FailureMode.EDGE_CASE
        # Heuristic: if actual value is not None and completely unrelated in type/value
        if result.actual is not None and result.expected is not None:
            if type(result.actual) != type(result.expected):
                return FailureMode.TYPE_ERROR
            # If the actual output looks like a default/stub (None, 0, "", [])
            if result.actual in (None, 0, "", [], {}, False) and result.expected not in (None, 0, "", [], {}, False):
                return FailureMode.HALLUCINATION

    return FailureMode.WRONG_OUTPUT


def classify_failures(spec: Spec, dyn: DynamicReport) -> FailureTaxonomy:
    # Import error — all tests fail with SYNTAX_ERROR
    if dyn.import_error:
        counts = {FailureMode.SYNTAX_ERROR: dyn.n_tests}
        dist   = {FailureMode.SYNTAX_ERROR: 1.0}
        classified = [
            {"test_id": f"ALL ({dyn.n_tests})", "mode": FailureMode.SYNTAX_ERROR,
             "reason": dyn.import_error}
        ]
        return FailureTaxonomy(
            counts={k.value: v for k, v in counts.items()},
            distribution={k.value: v for k, v in dist.items()},
            dominant_mode=FailureMode.SYNTAX_ERROR.value,
            total_failures=dyn.n_tests,
            classified=classified,
        )

    failures = dyn.failed_results()
    if not failures:
        return FailureTaxonomy(
            counts={}, distribution={}, dominant_mode=None,
            total_failures=0, classified=[],
        )

    classified = []
    raw_counts: Counter = Counter()
    for r in failures:
        mode = _classify_one(r, spec)
        raw_counts[mode] += 1
        classified.append({
            "test_id": r.test_id,
            "mode": mode.value,
            "reason": r.failure_reason or r.exception or "unknown",
            "actual": str(r.actual)[:80],
            "expected": str(r.expected)[:80],
        })

    total = len(failures)
    dist  = {k.value: round(v / total, 4) for k, v in raw_counts.items()}
    dominant = raw_counts.most_common(1)[0][0].value if raw_counts else None

    return FailureTaxonomy(
        counts={k.value: v for k, v in raw_counts.items()},
        distribution=dist,
        dominant_mode=dominant,
        total_failures=total,
        classified=classified,
    )
