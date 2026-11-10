"""
Requirement tracing: maps test outcomes back to spec requirements.

For each requirement:
  - Determine which test cases cover it (via requirement_ids in spec).
  - Classify coverage: FULLY_MET, PARTIALLY_MET, UNMET, UNTESTED.
  - Compute a coverage score and a weighted Test Adequacy Score (TAS).
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

from harness.spec_loader import Spec
from harness.dynamic_checks import DynamicReport


class CoverageStatus(str, Enum):
    FULLY_MET   = "FULLY_MET"
    PARTIALLY_MET = "PARTIALLY_MET"
    UNMET       = "UNMET"
    UNTESTED    = "UNTESTED"


@dataclass
class RequirementCoverage:
    req_id: str
    description: str
    priority: str
    status: CoverageStatus
    n_tests: int
    n_passing: int
    coverage_score: float    # passing / total tests for this req
    linked_test_ids: list[str]
    failing_test_ids: list[str]


@dataclass
class TraceReport:
    requirements: list[RequirementCoverage]
    tas: float               # Test Adequacy Score: fraction of reqs fully met
    weighted_tas: float      # Priority-weighted TAS (must > should > could)
    n_fully_met: int
    n_partially_met: int
    n_unmet: int
    n_untested: int


PRIORITY_WEIGHT = {"must": 3, "should": 2, "could": 1}


def trace_requirements(spec: Spec, dyn: DynamicReport) -> TraceReport:
    pass_set = {r.test_id for r in dyn.results if r.passed}
    fail_set = {r.test_id for r in dyn.results if not r.passed}

    coverages = []
    for req in spec.requirements:
        linked = req.test_ids
        if not linked:
            cov = RequirementCoverage(
                req_id=req.id, description=req.description, priority=req.priority,
                status=CoverageStatus.UNTESTED,
                n_tests=0, n_passing=0, coverage_score=0.0,
                linked_test_ids=[], failing_test_ids=[],
            )
        else:
            passing = [t for t in linked if t in pass_set]
            failing = [t for t in linked if t in fail_set]
            n_pass  = len(passing)
            n_total = len(linked)
            score   = n_pass / n_total

            if n_pass == n_total:
                status = CoverageStatus.FULLY_MET
            elif n_pass > 0:
                status = CoverageStatus.PARTIALLY_MET
            else:
                status = CoverageStatus.UNMET

            cov = RequirementCoverage(
                req_id=req.id, description=req.description, priority=req.priority,
                status=status,
                n_tests=n_total, n_passing=n_pass,
                coverage_score=round(score, 4),
                linked_test_ids=linked,
                failing_test_ids=failing,
            )
        coverages.append(cov)

    n_total       = len(coverages)
    n_fully       = sum(1 for c in coverages if c.status == CoverageStatus.FULLY_MET)
    n_partial     = sum(1 for c in coverages if c.status == CoverageStatus.PARTIALLY_MET)
    n_unmet       = sum(1 for c in coverages if c.status == CoverageStatus.UNMET)
    n_untested    = sum(1 for c in coverages if c.status == CoverageStatus.UNTESTED)

    tas = n_fully / max(1, n_total)

    # Weighted TAS
    total_weight   = sum(PRIORITY_WEIGHT.get(c.priority, 1) for c in coverages)
    weighted_score = sum(
        PRIORITY_WEIGHT.get(c.priority, 1) * c.coverage_score
        for c in coverages
    )
    weighted_tas = weighted_score / max(1, total_weight)

    return TraceReport(
        requirements=coverages,
        tas=round(tas, 4),
        weighted_tas=round(weighted_tas, 4),
        n_fully_met=n_fully,
        n_partially_met=n_partial,
        n_unmet=n_unmet,
        n_untested=n_untested,
    )
