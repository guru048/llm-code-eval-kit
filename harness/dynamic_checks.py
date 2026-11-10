"""
Dynamic execution of spec test cases against generated code.

For each test case:
  1. Import the generated module in an isolated namespace.
  2. Call the target function with the spec-defined args/kwargs.
  3. Compare the return value to `expected` (exact match or type check).
  4. Record pass/fail, actual output, exception info, and wall-clock time.

The module is imported once per evaluation run; test cases share the import.
A per-call timeout guard prevents infinite loops from hanging the harness.
"""

from __future__ import annotations
import importlib.util
import sys
import time
import traceback
import signal
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.spec_loader import Spec, TestCase


class TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise TimeoutError("execution timed out")


@dataclass
class TestResult:
    test_id: str
    passed: bool
    actual: Any
    expected: Any
    exception: str | None
    elapsed_ms: float
    failure_reason: str | None     # human-readable, fed to taxonomy


@dataclass
class DynamicReport:
    n_tests: int
    n_passed: int
    n_failed: int
    n_errored: int
    results: list[TestResult] = field(default_factory=list)
    import_error: str | None = None

    @property
    def pass_rate(self) -> float:
        return self.n_passed / max(1, self.n_tests)

    def failed_results(self) -> list[TestResult]:
        return [r for r in self.results if not r.passed]


def _load_module(path: str):
    spec = importlib.util.spec_from_file_location("_eval_module", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _values_equal(actual: Any, expected: Any) -> bool:
    if isinstance(expected, float):
        return abs(actual - expected) < 1e-6
    if isinstance(expected, list):
        return list(actual) == expected
    return actual == expected


def run_dynamic_checks(code_path: str, spec: Spec) -> DynamicReport:
    # Import once
    try:
        mod = _load_module(code_path)
    except Exception as e:
        return DynamicReport(
            n_tests=len(spec.tests),
            n_passed=0,
            n_failed=len(spec.tests),
            n_errored=len(spec.tests),
            import_error=f"{type(e).__name__}: {e}",
        )

    results = []
    n_passed = n_failed = n_errored = 0

    for tc in spec.tests:
        result = _run_one(mod, tc, spec.timeout_seconds)
        results.append(result)
        if result.passed:
            n_passed += 1
        elif result.exception:
            n_errored += 1
            n_failed  += 1
        else:
            n_failed += 1

    return DynamicReport(
        n_tests=len(spec.tests),
        n_passed=n_passed,
        n_failed=n_failed,
        n_errored=n_errored,
        results=results,
    )


def _run_one(mod, tc: TestCase, timeout: float) -> TestResult:
    fn = getattr(mod, tc.function, None)
    if fn is None:
        return TestResult(
            test_id=tc.id,
            passed=False,
            actual=None,
            expected=tc.expected,
            exception=f"AttributeError: function '{tc.function}' not found",
            elapsed_ms=0.0,
            failure_reason=f"function '{tc.function}' missing from module",
        )

    # Set up alarm-based timeout (Unix only)
    use_alarm = hasattr(signal, "SIGALRM")
    if use_alarm:
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(max(1, int(timeout)))

    t0 = time.perf_counter()
    try:
        actual = fn(*tc.args, **tc.kwargs)
        elapsed = (time.perf_counter() - t0) * 1000

        if use_alarm:
            signal.alarm(0)

        # Type check if requested
        if tc.expected_type:
            type_map = {"int": int, "float": float, "str": str,
                        "list": list, "dict": dict, "bool": bool, "tuple": tuple}
            expected_cls = type_map.get(tc.expected_type)
            if expected_cls and not isinstance(actual, expected_cls):
                return TestResult(
                    test_id=tc.id, passed=False, actual=actual,
                    expected=f"<type {tc.expected_type}>", exception=None,
                    elapsed_ms=elapsed,
                    failure_reason=f"wrong return type: got {type(actual).__name__}, expected {tc.expected_type}",
                )

        if tc.expected is None:
            # Only checking no exception
            passed = True
            reason = None
        elif not _values_equal(actual, tc.expected):
            passed = False
            reason = f"expected {tc.expected!r}, got {actual!r}"
        else:
            passed = True
            reason = None

        return TestResult(
            test_id=tc.id, passed=passed, actual=actual,
            expected=tc.expected, exception=None,
            elapsed_ms=round(elapsed, 3),
            failure_reason=reason,
        )

    except TimeoutError:
        if use_alarm:
            signal.alarm(0)
        elapsed = (time.perf_counter() - t0) * 1000
        return TestResult(
            test_id=tc.id, passed=False, actual=None, expected=tc.expected,
            exception="TimeoutError",
            elapsed_ms=round(elapsed, 3),
            failure_reason="execution exceeded timeout",
        )
    except Exception as e:
        if use_alarm:
            signal.alarm(0)
        elapsed = (time.perf_counter() - t0) * 1000
        tb = traceback.format_exc(limit=3)
        return TestResult(
            test_id=tc.id, passed=False, actual=None, expected=tc.expected,
            exception=f"{type(e).__name__}: {e}",
            elapsed_ms=round(elapsed, 3),
            failure_reason=tb.strip().splitlines()[-1],
        )
