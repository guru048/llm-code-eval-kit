"""
Renders an AuditReport as a human-readable Markdown audit report.
"""

from __future__ import annotations
from report.audit_report import AuditReport
from harness.requirement_tracer import CoverageStatus


STATUS_ICON = {
    CoverageStatus.FULLY_MET:    "✅",
    CoverageStatus.PARTIALLY_MET:"⚠️",
    CoverageStatus.UNMET:        "❌",
    CoverageStatus.UNTESTED:     "⬜",
}


def render_markdown(report: AuditReport) -> str:
    r  = report
    d  = r.dynamic
    t  = r.trace
    s  = r.static
    tx = r.taxonomy

    grade = _grade(r.overall_score)

    lines = [
        f"# Audit Report — `{r.spec_name}` v{r.spec_version}",
        f"",
        f"**Code:** `{r.code_path}`  ",
        f"**Timestamp:** {r.timestamp}  ",
        f"**Overall Score:** {r.overall_score:.2%}  ({grade})",
        f"",
        f"---",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Test pass rate | {d.pass_rate:.2%} ({d.n_passed}/{d.n_tests}) |",
        f"| Test Adequacy Score (TAS) | {t.tas:.2%} ({t.n_fully_met}/{len(t.requirements)} requirements fully met) |",
        f"| Weighted TAS | {t.weighted_tas:.2%} |",
        f"| Static quality score | {s.score():.2%} |",
        f"| Overall score | **{r.overall_score:.2%}** |",
        f"",
        f"### Bootstrap Confidence Intervals (95%, B=10,000)",
        f"",
        f"| Metric | Observed | Lower | Upper | SE |",
        f"|---|---|---|---|---|",
        f"| Pass rate | {r.pass_rate_ci.observed:.4f} | {r.pass_rate_ci.lower:.4f} | {r.pass_rate_ci.upper:.4f} | {r.pass_rate_ci.std_error:.4f} |",
        f"| TAS | {r.tas_ci.observed:.4f} | {r.tas_ci.lower:.4f} | {r.tas_ci.upper:.4f} | {r.tas_ci.std_error:.4f} |",
        f"",
        f"---",
        f"",
        f"## Static Analysis",
        f"",
        f"| Property | Value |",
        f"|---|---|",
        f"| Syntax OK | {'Yes' if s.syntax_ok else 'No — ' + str(s.syntax_error)} |",
        f"| Total lines | {s.total_lines} |",
        f"| Code lines | {s.code_lines} |",
        f"| Avg cyclomatic complexity | {s.avg_cyclomatic} |",
        f"| Max cyclomatic complexity | {s.max_cyclomatic} |",
        f"| Missing functions | {', '.join(s.functions_missing) or 'none'} |",
        f"| Dangerous patterns | {len(s.dangerous_patterns)} |",
        f"",
    ]

    if s.function_stats:
        lines += [
            f"### Function-level stats",
            f"",
            f"| Function | Complexity | Docstring | Lines | Args |",
            f"|---|---|---|---|---|",
        ]
        for fs in s.function_stats:
            lines.append(
                f"| `{fs.name}` | {fs.cyclomatic_complexity} | "
                f"{'Yes' if fs.has_docstring else 'No'} | {fs.line_count} | {fs.arg_count} |"
            )
        lines.append("")

    lines += [
        f"---",
        f"",
        f"## Requirement Tracing",
        f"",
        f"| ID | Priority | Status | Coverage | Description |",
        f"|---|---|---|---|---|",
    ]
    for c in t.requirements:
        icon = STATUS_ICON.get(c.status, "?")
        lines.append(
            f"| {c.req_id} | {c.priority} | {icon} {c.status.value} | "
            f"{c.coverage_score:.0%} ({c.n_passing}/{c.n_tests}) | {c.description} |"
        )

    lines += [
        f"",
        f"---",
        f"",
        f"## Failure-Mode Taxonomy",
        f"",
    ]

    if tx.total_failures == 0:
        lines.append("No failures. All tests passed.")
    else:
        lines += [
            f"**Total failures:** {tx.total_failures}  ",
            f"**Dominant mode:** `{tx.dominant_mode}`",
            f"",
            f"| Failure Mode | Count | % |",
            f"|---|---|---|",
        ]
        for mode, count in sorted(tx.counts.items(), key=lambda x: -x[1]):
            pct = tx.distribution.get(mode, 0)
            lines.append(f"| `{mode}` | {count} | {pct:.0%} |")

        lines += [
            f"",
            f"### Individual failures",
            f"",
            f"| Test ID | Mode | Reason |",
            f"|---|---|---|",
        ]
        for f in tx.classified:
            reason = str(f.get("reason", ""))[:80].replace("|", "\\|")
            lines.append(f"| {f['test_id']} | `{f['mode']}` | {reason} |")

    lines += [f"", f"---", f""]
    return "\n".join(lines)


def _grade(score: float) -> str:
    if score >= 0.95: return "A+"
    if score >= 0.90: return "A"
    if score >= 0.80: return "B"
    if score >= 0.70: return "C"
    if score >= 0.60: return "D"
    return "F"
