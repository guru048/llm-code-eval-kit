"""
Unit and integration tests for llm-code-eval-kit harness.
Run with: pytest tests/ -v
"""

import os, sys
import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE = os.path.dirname(__file__)
SPECS_DIR = os.path.join(BASE, "..", "examples", "specs")
GEN_DIR   = os.path.join(BASE, "..", "examples", "generated")


# ─── spec_loader ──────────────────────────────────────────────────────────────

def test_load_spec_string_utils():
    from harness.spec_loader import load_spec
    spec = load_spec(os.path.join(SPECS_DIR, "string_utils.yaml"))
    assert spec.name == "string_utils"
    assert len(spec.requirements) == 8
    assert len(spec.tests) == 15
    assert spec.test_by_id("T1") is not None
    assert spec.req_by_id("R1") is not None


def test_load_spec_data_pipeline():
    from harness.spec_loader import load_spec
    spec = load_spec(os.path.join(SPECS_DIR, "data_pipeline.yaml"))
    assert spec.name == "data_pipeline"
    assert len(spec.requirements) >= 7


# ─── static_checks ────────────────────────────────────────────────────────────

def test_static_syntax_ok():
    from harness.static_checks import run_static_checks
    source = "def foo(x):\n    return x + 1\n"
    r = run_static_checks(source, ["foo"])
    assert r.syntax_ok
    assert r.syntax_error is None
    assert "foo" in r.functions_found
    assert r.functions_missing == []


def test_static_syntax_error():
    from harness.static_checks import run_static_checks
    source = "def foo(x\n    return x\n"  # missing closing paren
    r = run_static_checks(source, ["foo"])
    assert not r.syntax_ok
    assert r.syntax_error is not None
    assert r.score() == 0.0


def test_static_missing_function():
    from harness.static_checks import run_static_checks
    source = "def foo(x):\n    return x\n"
    r = run_static_checks(source, ["foo", "bar"])
    assert "bar" in r.functions_missing


def test_static_cyclomatic():
    from harness.static_checks import run_static_checks
    source = (
        "def complex_fn(x):\n"
        "    if x > 0:\n"
        "        if x > 10:\n"
        "            return 'big'\n"
        "        return 'small'\n"
        "    elif x == 0:\n"
        "        return 'zero'\n"
        "    else:\n"
        "        return 'negative'\n"
    )
    r = run_static_checks(source, ["complex_fn"])
    assert r.max_cyclomatic >= 3


# ─── dynamic_checks ───────────────────────────────────────────────────────────

def test_dynamic_v1_all_pass():
    from harness.spec_loader import load_spec
    from harness.dynamic_checks import run_dynamic_checks
    spec = load_spec(os.path.join(SPECS_DIR, "string_utils.yaml"))
    report = run_dynamic_checks(os.path.join(GEN_DIR, "string_utils_v1.py"), spec)
    assert report.n_passed == report.n_tests
    assert report.pass_rate == 1.0


def test_dynamic_v2_some_fail():
    from harness.spec_loader import load_spec
    from harness.dynamic_checks import run_dynamic_checks
    spec = load_spec(os.path.join(SPECS_DIR, "string_utils.yaml"))
    report = run_dynamic_checks(os.path.join(GEN_DIR, "string_utils_v2.py"), spec)
    assert report.n_passed < report.n_tests
    assert report.n_failed > 0


def test_dynamic_v3_mostly_fail():
    from harness.spec_loader import load_spec
    from harness.dynamic_checks import run_dynamic_checks
    spec = load_spec(os.path.join(SPECS_DIR, "string_utils.yaml"))
    report = run_dynamic_checks(os.path.join(GEN_DIR, "string_utils_v3.py"), spec)
    assert report.pass_rate < 0.5


def test_dynamic_missing_function():
    from harness.spec_loader import load_spec
    from harness.dynamic_checks import run_dynamic_checks, TestResult
    import tempfile, os
    spec = load_spec(os.path.join(SPECS_DIR, "string_utils.yaml"))
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
        f.write("def irrelevant(): pass\n")
        tmp = f.name
    try:
        report = run_dynamic_checks(tmp, spec)
        assert report.n_passed == 0
    finally:
        os.unlink(tmp)


# ─── requirement_tracer ───────────────────────────────────────────────────────

def test_trace_v1_fully_met():
    from harness.spec_loader import load_spec
    from harness.dynamic_checks import run_dynamic_checks
    from harness.requirement_tracer import trace_requirements, CoverageStatus
    spec   = load_spec(os.path.join(SPECS_DIR, "string_utils.yaml"))
    dyn    = run_dynamic_checks(os.path.join(GEN_DIR, "string_utils_v1.py"), spec)
    trace  = trace_requirements(spec, dyn)
    assert trace.tas == 1.0
    assert all(c.status == CoverageStatus.FULLY_MET for c in trace.requirements)


def test_trace_v3_mostly_unmet():
    from harness.spec_loader import load_spec
    from harness.dynamic_checks import run_dynamic_checks
    from harness.requirement_tracer import trace_requirements, CoverageStatus
    spec   = load_spec(os.path.join(SPECS_DIR, "string_utils.yaml"))
    dyn    = run_dynamic_checks(os.path.join(GEN_DIR, "string_utils_v3.py"), spec)
    trace  = trace_requirements(spec, dyn)
    assert trace.tas < 0.5


# ─── failure_taxonomy ─────────────────────────────────────────────────────────

def test_taxonomy_no_failures():
    from harness.spec_loader import load_spec
    from harness.dynamic_checks import run_dynamic_checks
    from harness.failure_taxonomy import classify_failures
    spec = load_spec(os.path.join(SPECS_DIR, "string_utils.yaml"))
    dyn  = run_dynamic_checks(os.path.join(GEN_DIR, "string_utils_v1.py"), spec)
    tax  = classify_failures(spec, dyn)
    assert tax.total_failures == 0
    assert tax.dominant_mode is None


def test_taxonomy_has_wrong_output():
    from harness.spec_loader import load_spec
    from harness.dynamic_checks import run_dynamic_checks
    from harness.failure_taxonomy import classify_failures, FailureMode
    spec = load_spec(os.path.join(SPECS_DIR, "string_utils.yaml"))
    dyn  = run_dynamic_checks(os.path.join(GEN_DIR, "string_utils_v3.py"), spec)
    tax  = classify_failures(spec, dyn)
    assert tax.total_failures > 0
    assert FailureMode.WRONG_OUTPUT.value in tax.counts or FailureMode.HALLUCINATION.value in tax.counts


# ─── bootstrap_ci ─────────────────────────────────────────────────────────────

def test_bootstrap_pass_rate_perfect():
    from harness.bootstrap_ci import compute_pass_rate_ci
    ci = compute_pass_rate_ci([True] * 20, B=1000)
    assert ci.observed == 1.0
    assert ci.lower >= 0.9
    assert ci.upper == 1.0


def test_bootstrap_tas_half():
    from harness.bootstrap_ci import compute_tas_ci
    flags = [True] * 5 + [False] * 5
    ci = compute_tas_ci(flags, B=1000)
    assert abs(ci.observed - 0.5) < 0.01
    assert ci.lower < 0.5 < ci.upper


def test_bootstrap_sensitivity():
    from harness.bootstrap_ci import compute_sensitivity_ci
    scores = [1.0, 0.75, 0.25]
    ci, si = compute_sensitivity_ci(scores, B=1000)
    assert ci.lower < ci.observed < ci.upper or ci.lower == ci.observed
    assert si > 0.0


# ─── sensitivity_runner ───────────────────────────────────────────────────────

def test_sensitivity_ranking():
    from harness.spec_loader import load_spec
    from harness.sensitivity_runner import run_sensitivity_analysis
    spec = load_spec(os.path.join(SPECS_DIR, "string_utils.yaml"))
    paths = [
        os.path.join(GEN_DIR, "string_utils_v1.py"),
        os.path.join(GEN_DIR, "string_utils_v2.py"),
        os.path.join(GEN_DIR, "string_utils_v3.py"),
    ]
    report = run_sensitivity_analysis(spec, paths, B=1000)
    assert report.n_variants == 3
    assert report.best_variant == "string_utils_v1"
    assert report.worst_variant == "string_utils_v3"
    # v1 should be strictly better than v3
    scores = {v.variant_name: v.tas for v in report.variant_results}
    assert scores["string_utils_v1"] > scores["string_utils_v3"]


# ─── end-to-end ───────────────────────────────────────────────────────────────

def test_full_pipeline_v1():
    from harness.spec_loader import load_spec
    from harness.static_checks import run_static_checks
    from harness.dynamic_checks import run_dynamic_checks
    from harness.requirement_tracer import trace_requirements
    from harness.failure_taxonomy import classify_failures
    from report.audit_report import build_audit_report
    from report.formatter import render_markdown

    spec_path = os.path.join(SPECS_DIR, "string_utils.yaml")
    code_path = os.path.join(GEN_DIR, "string_utils_v1.py")

    spec     = load_spec(spec_path)
    source   = open(code_path).read()
    req_fns  = list({tc.function for tc in spec.tests})
    static   = run_static_checks(source, req_fns)
    dynamic  = run_dynamic_checks(code_path, spec)
    trace    = trace_requirements(spec, dynamic)
    taxonomy = classify_failures(spec, dynamic)
    report   = build_audit_report(spec, code_path, static, dynamic, trace, taxonomy, B=1000)

    assert report.overall_score > 0.9
    md = render_markdown(report)
    assert "string_utils" in md
    assert "FULLY_MET" in md
