"""
Assembles the full audit report from all sub-reports.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from harness.spec_loader import Spec
from harness.static_checks import StaticReport
from harness.dynamic_checks import DynamicReport
from harness.requirement_tracer import TraceReport
from harness.failure_taxonomy import FailureTaxonomy
from harness.bootstrap_ci import BootstrapCI, compute_pass_rate_ci, compute_tas_ci


@dataclass
class AuditReport:
    spec_name: str
    spec_version: str
    code_path: str
    timestamp: str
    static: StaticReport
    dynamic: DynamicReport
    trace: TraceReport
    taxonomy: FailureTaxonomy
    pass_rate_ci: BootstrapCI
    tas_ci: BootstrapCI
    overall_score: float


def build_audit_report(
    spec: Spec,
    code_path: str,
    static: StaticReport,
    dynamic: DynamicReport,
    trace: TraceReport,
    taxonomy: FailureTaxonomy,
    B: int = 10_000,
) -> AuditReport:
    passed_flags = [r.passed for r in dynamic.results]
    pr_ci  = compute_pass_rate_ci(passed_flags, B=B)
    req_met = [
        c.coverage_score == 1.0
        for c in trace.requirements
    ]
    tas_ci = compute_tas_ci(req_met, B=B)

    # Overall score: weighted combination
    overall = round(
        0.35 * trace.tas
        + 0.35 * dynamic.pass_rate
        + 0.20 * static.score()
        + 0.10 * trace.weighted_tas,
        4,
    )

    return AuditReport(
        spec_name=spec.name,
        spec_version=spec.version,
        code_path=str(code_path),
        timestamp=datetime.now(timezone.utc).isoformat(),
        static=static,
        dynamic=dynamic,
        trace=trace,
        taxonomy=taxonomy,
        pass_rate_ci=pr_ci,
        tas_ci=tas_ci,
        overall_score=overall,
    )


def save_report_json(report: AuditReport, output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    def _default(o):
        if hasattr(o, "__dict__"):
            return o.__dict__
        return str(o)

    with open(output_path, "w") as fh:
        json.dump(report.__dict__, fh, indent=2, default=_default)
