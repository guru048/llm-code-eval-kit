"""
llm-code-eval-kit CLI

Usage
-----
# Evaluate one code file against a spec:
python cli.py eval examples/specs/string_utils.yaml examples/generated/string_utils_v1.py

# Sensitivity analysis across N variants:
python cli.py sensitivity examples/specs/string_utils.yaml \
    examples/generated/string_utils_v1.py \
    examples/generated/string_utils_v2.py \
    examples/generated/string_utils_v3.py

# Query the audit log:
python cli.py history --spec string_utils
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from harness.spec_loader import load_spec
from harness.static_checks import run_static_checks
from harness.dynamic_checks import run_dynamic_checks
from harness.requirement_tracer import trace_requirements
from harness.failure_taxonomy import classify_failures
from harness.sensitivity_runner import run_sensitivity_analysis
from report.audit_report import build_audit_report, save_report_json
from report.formatter import render_markdown
from db.audit_log import log_run, query_runs


def cmd_eval(args):
    spec      = load_spec(args.spec)
    code_path = args.code

    source = open(code_path).read()
    required_fns = list({tc.function for tc in spec.tests})

    static  = run_static_checks(source, required_fns)
    dynamic = run_dynamic_checks(code_path, spec)
    trace   = trace_requirements(spec, dynamic)
    taxonomy= classify_failures(spec, dynamic)

    report  = build_audit_report(spec, code_path, static, dynamic, trace, taxonomy)

    md = render_markdown(report)
    print(md)

    if args.output:
        os.makedirs(args.output, exist_ok=True)
        stem = os.path.splitext(os.path.basename(code_path))[0]
        json_path = os.path.join(args.output, f"{stem}_report.json")
        md_path   = os.path.join(args.output, f"{stem}_report.md")
        save_report_json(report, json_path)
        open(md_path, "w").write(md)
        print(f"\nSaved: {json_path}")
        print(f"Saved: {md_path}")

    if not args.no_log:
        run_id = log_run(report, args.db)
        print(f"Logged run id={run_id} to {args.db}")

    return report.overall_score


def cmd_sensitivity(args):
    spec   = load_spec(args.spec)
    report = run_sensitivity_analysis(spec, args.variants, B=args.bootstrap_samples)

    print(f"\n{'='*60}")
    print(f"Sensitivity Analysis — {report.spec_name}")
    print(f"{'='*60}")
    print(f"Variants evaluated : {report.n_variants}")
    print(f"Mean TAS           : {report.mean_tas:.4f}  (95% CI: {report.tas_ci.lower:.4f}–{report.tas_ci.upper:.4f})")
    print(f"Std TAS            : {report.std_tas:.4f}")
    print(f"TAS range          : [{report.min_tas:.4f}, {report.max_tas:.4f}]")
    print(f"Sensitivity Index  : {report.sensitivity_index:.4f}  — {report.si_label}")
    print(f"Best variant       : {report.best_variant}")
    print(f"Worst variant      : {report.worst_variant}")
    print(f"\nVariant rankings:")
    print(f"  {'Rank':<6} {'Variant':<30} {'TAS':>6} {'Pass%':>7} {'Static':>7} {'Dom.Failure'}")
    print(f"  {'-'*4}  {'-'*28}  {'-'*5}  {'-'*5}  {'-'*5}  {'-'*20}")
    for v in report.variant_results:
        df = v.dominant_failure or "—"
        print(f"  {v.rank:<6} {v.variant_name:<30} {v.tas:>6.2%} {v.pass_rate:>7.2%} {v.static_score:>7.2%}  {df}")

    if args.output:
        import json
        os.makedirs(args.output, exist_ok=True)

        def _d(o):
            return o.__dict__ if hasattr(o, "__dict__") else str(o)

        path = os.path.join(args.output, f"{report.spec_name}_sensitivity.json")
        with open(path, "w") as fh:
            json.dump(report.__dict__, fh, indent=2, default=_d)
        print(f"\nSaved: {path}")


def cmd_history(args):
    rows = query_runs(spec_name=args.spec, limit=args.limit, db_path=args.db)
    if not rows:
        print("No runs found.")
        return
    print(f"\n{'ID':<5} {'Spec':<20} {'Code':<35} {'Score':>7} {'TAS':>6} {'Pass%':>6}  Timestamp")
    print(f"{'-'*4}  {'-'*18}  {'-'*33}  {'-'*5}  {'-'*4}  {'-'*4}  {'-'*20}")
    for r in rows:
        code = os.path.basename(r["code_path"])[:33]
        print(f"{r['id']:<5} {r['spec_name']:<20} {code:<35} {r['overall_score']:>7.4f} {r['tas']:>6.4f} {r['pass_rate']:>6.4f}  {r['timestamp'][:19]}")


def main():
    parser = argparse.ArgumentParser(
        description="llm-code-eval-kit: evaluate LLM-generated code against a spec YAML"
    )
    sub = parser.add_subparsers(dest="command")

    # eval
    p_eval = sub.add_parser("eval", help="Evaluate one code file")
    p_eval.add_argument("spec",    help="Path to spec YAML")
    p_eval.add_argument("code",    help="Path to generated Python file")
    p_eval.add_argument("--output", default="results", help="Output directory")
    p_eval.add_argument("--db",    default="results/audit_log.db")
    p_eval.add_argument("--no-log", action="store_true")
    p_eval.add_argument("--bootstrap-samples", type=int, default=10_000)

    # sensitivity
    p_sens = sub.add_parser("sensitivity", help="Sensitivity analysis across variants")
    p_sens.add_argument("spec",        help="Path to spec YAML")
    p_sens.add_argument("variants",    nargs="+", help="Paths to code variants")
    p_sens.add_argument("--output",    default="results")
    p_sens.add_argument("--bootstrap-samples", type=int, default=10_000)

    # history
    p_hist = sub.add_parser("history", help="Query audit log")
    p_hist.add_argument("--spec",  default=None)
    p_hist.add_argument("--limit", type=int, default=20)
    p_hist.add_argument("--db",    default="results/audit_log.db")

    args = parser.parse_args()
    if args.command == "eval":
        cmd_eval(args)
    elif args.command == "sensitivity":
        cmd_sensitivity(args)
    elif args.command == "history":
        cmd_history(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
