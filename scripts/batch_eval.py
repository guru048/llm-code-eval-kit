"""
Batch evaluate multiple (spec, code) pairs from a CSV manifest.

Manifest format (batch_manifest.csv):
    spec_path,code_path
    examples/specs/string_utils.yaml,examples/generated/string_utils_v1.py
    examples/specs/string_utils.yaml,examples/generated/string_utils_v2.py

Usage
-----
python scripts/batch_eval.py --manifest batch_manifest.csv --output results/batch/
"""

import argparse, csv, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from harness.spec_loader import load_spec
from harness.static_checks import run_static_checks
from harness.dynamic_checks import run_dynamic_checks
from harness.requirement_tracer import trace_requirements
from harness.failure_taxonomy import classify_failures
from report.audit_report import build_audit_report, save_report_json
from report.formatter import render_markdown
from db.audit_log import log_run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output",   default="results/batch")
    parser.add_argument("--db",       default="results/audit_log.db")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    with open(args.manifest) as fh:
        rows = list(csv.DictReader(fh))

    results = []
    for row in rows:
        spec_path = row["spec_path"].strip()
        code_path = row["code_path"].strip()
        spec      = load_spec(spec_path)
        source    = open(code_path).read()
        req_fns   = list({tc.function for tc in spec.tests})

        static   = run_static_checks(source, req_fns)
        dynamic  = run_dynamic_checks(code_path, spec)
        trace    = trace_requirements(spec, dynamic)
        taxonomy = classify_failures(spec, dynamic)
        report   = build_audit_report(spec, code_path, static, dynamic, trace, taxonomy)

        stem     = os.path.splitext(os.path.basename(code_path))[0]
        json_path= os.path.join(args.output, f"{stem}_report.json")
        md_path  = os.path.join(args.output, f"{stem}_report.md")
        save_report_json(report, json_path)
        open(md_path, "w").write(render_markdown(report))
        log_run(report, args.db)

        print(f"  {spec.name:20s}  {os.path.basename(code_path):30s}  "
              f"score={report.overall_score:.4f}  TAS={trace.tas:.4f}")
        results.append({"spec": spec.name, "code": code_path,
                        "score": report.overall_score, "tas": trace.tas})

    summary_path = os.path.join(args.output, "batch_summary.json")
    with open(summary_path, "w") as fh:
        json.dump(results, fh, indent=2)
    print(f"\nBatch summary saved to {summary_path}")


if __name__ == "__main__":
    main()
