"""
Self-contained end-to-end demo.

Runs the full harness on three string_utils variants and
the data_pipeline spec, prints results, and saves a JSON summary.

Usage
-----
python examples/run_demo.py
"""

import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from harness.spec_loader import load_spec
from harness.static_checks import run_static_checks
from harness.dynamic_checks import run_dynamic_checks
from harness.requirement_tracer import trace_requirements
from harness.failure_taxonomy import classify_failures
from harness.sensitivity_runner import run_sensitivity_analysis
from report.audit_report import build_audit_report, save_report_json
from report.formatter import render_markdown
from db.audit_log import log_run

BASE = os.path.dirname(__file__)
SPECS_DIR = os.path.join(BASE, "specs")
GEN_DIR   = os.path.join(BASE, "generated")
RESULTS   = os.path.join(BASE, "..", "results")
os.makedirs(RESULTS, exist_ok=True)

VARIANTS = [
    os.path.join(GEN_DIR, "string_utils_v1.py"),
    os.path.join(GEN_DIR, "string_utils_v2.py"),
    os.path.join(GEN_DIR, "string_utils_v3.py"),
]

SPECS_AND_CODE = [
    (os.path.join(SPECS_DIR, "string_utils.yaml"),  os.path.join(GEN_DIR, "string_utils_v1.py")),
    (os.path.join(SPECS_DIR, "string_utils.yaml"),  os.path.join(GEN_DIR, "string_utils_v2.py")),
    (os.path.join(SPECS_DIR, "string_utils.yaml"),  os.path.join(GEN_DIR, "string_utils_v3.py")),
    (os.path.join(SPECS_DIR, "data_pipeline.yaml"), os.path.join(GEN_DIR, "data_pipeline_v1.py")),
]

summary = []

print(f"\n{'='*70}")
print(" llm-code-eval-kit  —  Demo Run")
print(f"{'='*70}\n")

for spec_path, code_path in SPECS_AND_CODE:
    t0   = time.time()
    spec = load_spec(spec_path)
    source = open(code_path).read()
    required_fns = list({tc.function for tc in spec.tests})

    static   = run_static_checks(source, required_fns)
    dynamic  = run_dynamic_checks(code_path, spec)
    trace    = trace_requirements(spec, dynamic)
    taxonomy = classify_failures(spec, dynamic)
    report   = build_audit_report(spec, code_path, static, dynamic, trace, taxonomy)

    variant  = os.path.basename(code_path)
    elapsed  = round(time.time() - t0, 2)

    print(f"  {spec.name:20s}  {variant:30s}  score={report.overall_score:.2%}  "
          f"TAS={trace.tas:.2%}  pass={dynamic.pass_rate:.2%}  ({elapsed}s)")

    # Save markdown report
    stem     = os.path.splitext(variant)[0]
    md_path  = os.path.join(RESULTS, f"{stem}_report.md")
    json_path= os.path.join(RESULTS, f"{stem}_report.json")
    open(md_path, "w").write(render_markdown(report))
    save_report_json(report, json_path)
    log_run(report)

    summary.append({
        "spec": spec.name,
        "variant": variant,
        "overall_score": report.overall_score,
        "tas": trace.tas,
        "weighted_tas": trace.weighted_tas,
        "pass_rate": dynamic.pass_rate,
        "static_score": static.score(),
        "n_passed": dynamic.n_passed,
        "n_tests": dynamic.n_tests,
        "dominant_failure": taxonomy.dominant_mode,
        "tas_ci_lower": report.tas_ci.lower,
        "tas_ci_upper": report.tas_ci.upper,
    })

print(f"\n{'─'*70}")
print("  Sensitivity Analysis — string_utils (3 variants)")
print(f"{'─'*70}")

spec = load_spec(os.path.join(SPECS_DIR, "string_utils.yaml"))
sens = run_sensitivity_analysis(spec, VARIANTS)

print(f"  Mean TAS           : {sens.mean_tas:.4f}")
print(f"  Std TAS            : {sens.std_tas:.4f}")
print(f"  Sensitivity Index  : {sens.sensitivity_index:.4f}  — {sens.si_label}")
print(f"  95% CI on mean TAS : [{sens.tas_ci.lower:.4f}, {sens.tas_ci.upper:.4f}]")
print(f"  Best  variant      : {sens.best_variant}")
print(f"  Worst variant      : {sens.worst_variant}")
print()
for v in sens.variant_results:
    df = v.dominant_failure or "—"
    print(f"    #{v.rank}  {v.variant_name:<28}  TAS={v.tas:.2%}  dom_failure={df}")

out = {
    "per_variant": summary,
    "sensitivity": {
        "spec": sens.spec_name,
        "n_variants": sens.n_variants,
        "mean_tas": sens.mean_tas,
        "std_tas": sens.std_tas,
        "min_tas": sens.min_tas,
        "max_tas": sens.max_tas,
        "sensitivity_index": sens.sensitivity_index,
        "si_label": sens.si_label,
        "tas_ci_lower": sens.tas_ci.lower,
        "tas_ci_upper": sens.tas_ci.upper,
        "best_variant": sens.best_variant,
        "worst_variant": sens.worst_variant,
    }
}

out_path = os.path.join(RESULTS, "demo_summary.json")
with open(out_path, "w") as fh:
    json.dump(out, fh, indent=2)
print(f"\nFull results saved to results/")
