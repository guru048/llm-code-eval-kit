# llm-code-eval-kit

A structured evaluation harness for LLM-generated code. You write a spec YAML describing what a module must do — requirements, test cases, and their links — and the kit runs static analysis, dynamic test execution, requirement tracing, failure classification, and bootstrap confidence intervals, then produces a structured audit report.

The goal: replace ad-hoc "does it run?" checks with rigorous, reproducible quality scoring that can be tracked over time, compared across model outputs, and integrated into CI.

---

## What it measures

| Component | What it computes |
|---|---|
| **Static analysis** | Syntax validity, cyclomatic complexity per function, missing functions, dangerous patterns (`eval`, `exec`, shell injection) |
| **Dynamic execution** | Per-test pass/fail, actual vs expected output, exception type, wall-clock time |
| **Requirement tracing** | Maps test outcomes back to spec requirements → FULLY\_MET / PARTIALLY\_MET / UNMET / UNTESTED |
| **Test Adequacy Score (TAS)** | Fraction of requirements fully met; also priority-weighted (must > should > could) |
| **Failure-mode taxonomy** | Classifies each failure: SYNTAX\_ERROR, MISSING\_FUNCTION, WRONG\_OUTPUT, TYPE\_ERROR, RUNTIME\_EXCEPTION, TIMEOUT, EDGE\_CASE, HALLUCINATION |
| **Bootstrap CI** | 95% confidence intervals on TAS and pass rate (Efron percentile bootstrap, B=10,000) |
| **Sensitivity analysis** | Runs the same spec across N code variants, computes mean TAS, std, Sensitivity Index (CV), and 95% CI on mean TAS |
| **SQLite audit log** | Every run is persisted for trend analysis and variant comparison |

---

## Demo results (real, from `python examples/run_demo.py`)

### Per-variant scores — `string_utils` spec (15 tests, 8 requirements)

| Variant | Description | Overall Score | TAS | Pass Rate | Dominant Failure |
|---|---|---|---|---|---|
| v1 — correct | All functions correct | **100.00 %** | 100.00 % | 100.00 % | — |
| v2 — partial bugs | Missing `.lower()`, counts `y` as vowel | **85.15 %** | 75.00 % | 86.67 % | EDGE\_CASE |
| v3 — hallucinated stubs | Returns inputs unchanged, always returns False | **36.57 %** | 12.50 % | 26.67 % | WRONG\_OUTPUT |

### `data_pipeline` spec (12 tests, 7 requirements)

| Variant | Overall Score | TAS | Pass Rate |
|---|---|---|---|
| v1 — correct | **100.00 %** | 100.00 % | 100.00 % |

### Sensitivity analysis — `string_utils` (3 variants)

| Metric | Value |
|---|---|
| Mean TAS | 0.6250 |
| Std TAS | 0.4507 |
| Sensitivity Index (CV) | **0.7211 — HIGH (unstable)** |
| 95% CI on mean TAS | [0.1250, 1.0000] |
| Best variant | string\_utils\_v1 |
| Worst variant | string\_utils\_v3 |

A Sensitivity Index > 0.20 means the LLM's output quality varies significantly across regenerations — a signal to invest in prompt refinement or ensemble voting.

---

## Project structure

```
llm-code-eval-kit/
├── cli.py                          # eval / sensitivity / history commands
├── harness/
│   ├── spec_loader.py              # YAML spec → typed dataclasses
│   ├── static_checks.py            # AST analysis, complexity, dangerous patterns
│   ├── dynamic_checks.py           # Test execution with timeout guard
│   ├── requirement_tracer.py       # Test outcomes → requirement coverage
│   ├── failure_taxonomy.py         # 8-class failure classifier
│   ├── bootstrap_ci.py             # Percentile bootstrap (Efron 1979)
│   └── sensitivity_runner.py       # Cross-variant stability analysis
├── report/
│   ├── audit_report.py             # Assembles full AuditReport
│   └── formatter.py                # Markdown renderer
├── db/
│   └── audit_log.py                # SQLite persistence
├── examples/
│   ├── specs/
│   │   ├── string_utils.yaml       # 15 tests, 8 requirements
│   │   └── data_pipeline.yaml      # 12 tests, 7 requirements
│   ├── generated/
│   │   ├── string_utils_v1.py      # Correct implementation
│   │   ├── string_utils_v2.py      # Partial bugs (edge cases fail)
│   │   ├── string_utils_v3.py      # Hallucinated stubs
│   │   └── data_pipeline_v1.py     # Correct implementation
│   └── run_demo.py                 # Self-contained demo
├── scripts/
│   └── batch_eval.py               # CSV-manifest batch evaluation
├── tests/
│   └── test_harness.py             # 20 unit + integration tests (pytest)
├── requirements.txt
└── setup.py
```

---

## Quick start

```bash
git clone https://github.com/Ritikk048/llm-code-eval-kit.git
cd llm-code-eval-kit
pip install -r requirements.txt
python examples/run_demo.py
```

### Evaluate one file

```bash
python cli.py eval examples/specs/string_utils.yaml examples/generated/string_utils_v2.py
```

Prints a full Markdown audit report to stdout and saves JSON + Markdown to `results/`.

### Sensitivity analysis across variants

```bash
python cli.py sensitivity examples/specs/string_utils.yaml \
    examples/generated/string_utils_v1.py \
    examples/generated/string_utils_v2.py \
    examples/generated/string_utils_v3.py
```

### Query audit history

```bash
python cli.py history --spec string_utils
```

### Batch evaluation from a CSV manifest

```bash
python scripts/batch_eval.py --manifest batch_manifest.csv --output results/batch/
```

### Run tests

```bash
pip install pytest
pytest tests/ -v
```

---

## Spec YAML format

```yaml
name: my_module
version: "1.0"
description: "What this module should do"
timeout_seconds: 3.0

requirements:
  - id: R1
    description: "foo(x) doubles x for positive integers"
    priority: must         # must | should | could
    test_ids: [T1, T2]

tests:
  - id: T1
    description: "foo(2) == 4"
    function: foo
    args: [2]
    expected: 4
    requirement_ids: [R1]
    tags: []               # edge, boundary, empty, etc.

  - id: T2
    description: "foo(0) == 0"
    function: foo
    args: [0]
    expected: 0
    requirement_ids: [R1]
    tags: [edge]
```

---

## Overall score formula

```
Score = 0.35 × TAS  +  0.35 × pass_rate  +  0.20 × static_score  +  0.10 × weighted_TAS
```

| Grade | Score |
|---|---|
| A+ | ≥ 95 % |
| A | ≥ 90 % |
| B | ≥ 80 % |
| C | ≥ 70 % |
| D | ≥ 60 % |
| F | < 60 % |

---

## Failure-mode taxonomy

| Mode | Triggered when |
|---|---|
| `SYNTAX_ERROR` | Module cannot be parsed or imported |
| `MISSING_FUNCTION` | Required function absent from module |
| `WRONG_OUTPUT` | Function ran but returned wrong value |
| `TYPE_ERROR` | Wrong return type |
| `RUNTIME_EXCEPTION` | Function threw an unexpected exception |
| `TIMEOUT` | Execution exceeded `timeout_seconds` |
| `EDGE_CASE` | Failure on a test tagged `edge`, `boundary`, `empty`, etc. |
| `HALLUCINATION` | Function returns a default/stub value unrelated to the spec |

---

## Sensitivity Index interpretation

| SI | Label | Meaning |
|---|---|---|
| < 0.05 | LOW | LLM is consistent — few regenerations needed |
| 0.05 – 0.20 | MEDIUM | Moderate spread — regenerate and select best |
| > 0.20 | HIGH | Unstable — refine the prompt or use ensemble voting |

---

## License

MIT © Guru
