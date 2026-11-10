"""
Static analysis of LLM-generated code.

Checks performed
----------------
1. Syntax validity (AST parse)
2. Cyclomatic complexity per function
3. Required functions present in module
4. Dangerous patterns: exec/eval, os.system, shell injection
5. Undefined name references (simple)
6. Docstring presence per function
7. Line count and blank-line ratio
"""

from __future__ import annotations
import ast
import re
from dataclasses import dataclass, field
from pathlib import Path


DANGEROUS_CALLS = {"exec", "eval", "compile", "__import__", "os.system",
                   "subprocess.call", "subprocess.Popen"}
DANGEROUS_PATTERNS = [
    r"os\.system\s*\(",
    r"subprocess\.(call|Popen|run)\s*\(.*shell\s*=\s*True",
    r"\beval\s*\(",
    r"\bexec\s*\(",
]


@dataclass
class FunctionStats:
    name: str
    cyclomatic_complexity: int
    has_docstring: bool
    line_count: int
    arg_count: int


@dataclass
class StaticReport:
    syntax_ok: bool
    syntax_error: str | None
    functions_found: list[str]
    functions_missing: list[str]
    function_stats: list[FunctionStats]
    dangerous_patterns: list[str]
    total_lines: int
    code_lines: int
    blank_lines: int
    comment_lines: int
    avg_cyclomatic: float
    max_cyclomatic: int
    undefined_names: list[str]

    def score(self) -> float:
        """0–1 static quality score."""
        if not self.syntax_ok:
            return 0.0
        s = 1.0
        s -= 0.3 * len(self.functions_missing) / max(1, len(self.functions_found) + len(self.functions_missing))
        s -= 0.1 * min(1.0, len(self.dangerous_patterns) * 0.25)
        complexity_penalty = max(0, (self.avg_cyclomatic - 5) / 20)
        s -= 0.2 * complexity_penalty
        return max(0.0, round(s, 4))


def _cyclomatic(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """McCabe cyclomatic complexity = 1 + number of branching nodes."""
    count = 1
    for child in ast.walk(node):
        if isinstance(child, (
            ast.If, ast.While, ast.For, ast.ExceptHandler,
            ast.With, ast.Assert, ast.comprehension,
        )):
            count += 1
        elif isinstance(child, ast.BoolOp):
            count += len(child.values) - 1
    return count


def _count_lines(source: str) -> tuple[int, int, int]:
    lines = source.splitlines()
    total = len(lines)
    blank = sum(1 for l in lines if not l.strip())
    comment = sum(1 for l in lines if l.strip().startswith("#"))
    return total, total - blank - comment, blank


def run_static_checks(source: str, required_functions: list[str]) -> StaticReport:
    # 1. Syntax check
    try:
        tree = ast.parse(source)
        syntax_ok = True
        syntax_error = None
    except SyntaxError as e:
        return StaticReport(
            syntax_ok=False,
            syntax_error=str(e),
            functions_found=[],
            functions_missing=list(required_functions),
            function_stats=[],
            dangerous_patterns=[],
            total_lines=source.count("\n"),
            code_lines=0,
            blank_lines=0,
            comment_lines=0,
            avg_cyclomatic=0.0,
            max_cyclomatic=0,
            undefined_names=[],
        )

    # 2. Function inventory
    func_nodes = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    found   = list(func_nodes.keys())
    missing = [f for f in required_functions if f not in func_nodes]

    # 3. Per-function stats
    stats = []
    for name, node in func_nodes.items():
        has_doc = (
            isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ) if node.body else False
        stats.append(FunctionStats(
            name=name,
            cyclomatic_complexity=_cyclomatic(node),
            has_docstring=has_doc,
            line_count=node.end_lineno - node.lineno + 1,
            arg_count=len(node.args.args),
        ))

    complexities = [s.cyclomatic_complexity for s in stats] or [0]

    # 4. Dangerous patterns
    dangers = []
    for pat in DANGEROUS_PATTERNS:
        if re.search(pat, source):
            dangers.append(pat)

    # 5. Undefined names (best-effort: names used but never assigned/imported)
    assigned = set()
    used     = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in getattr(node, "names", []):
                assigned.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store):
                assigned.add(node.id)
            elif isinstance(node.ctx, ast.Load):
                used.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assigned.add(node.name)
            for arg in node.args.args:
                assigned.add(arg.arg)
        elif isinstance(node, ast.ClassDef):
            assigned.add(node.name)
    builtins = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set(dir(__builtins__))
    undefined = sorted(used - assigned - builtins - {"self", "cls"})

    total, code, blank = _count_lines(source)

    return StaticReport(
        syntax_ok=syntax_ok,
        syntax_error=syntax_error,
        functions_found=found,
        functions_missing=missing,
        function_stats=stats,
        dangerous_patterns=dangers,
        total_lines=total,
        code_lines=code,
        blank_lines=blank,
        comment_lines=total - code - blank,
        avg_cyclomatic=round(sum(complexities) / len(complexities), 2),
        max_cyclomatic=max(complexities),
        undefined_names=undefined[:10],
    )
