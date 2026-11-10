"""
Spec loader and validator.

A spec YAML defines the contract an LLM-generated module must satisfy:
  - requirements  : what the code must do (R-prefixed IDs)
  - tests         : executable test cases linked to requirements (T-prefixed IDs)
  - metadata      : name, version, description, timeout

Schema
------
name: str
version: str
description: str
timeout_seconds: float   (default 5.0)
requirements:
  - id: R1
    description: str
    test_ids: [T1, T2]
tests:
  - id: T1
    description: str
    function: str           # function name in generated module
    args: [...]             # positional args
    kwargs: {key: val}      # keyword args
    expected: any           # expected return value (None = only checks no exception)
    expected_type: str      # optional type check ("int", "list", etc.)
    requirement_ids: [R1]
"""

from __future__ import annotations
import yaml
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TestCase:
    id: str
    description: str
    function: str
    args: list = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)
    expected: object = None
    expected_type: str | None = None
    requirement_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class Requirement:
    id: str
    description: str
    test_ids: list[str] = field(default_factory=list)
    priority: str = "must"   # must | should | could


@dataclass
class Spec:
    name: str
    version: str
    description: str
    requirements: list[Requirement]
    tests: list[TestCase]
    timeout_seconds: float = 5.0
    tags: list[str] = field(default_factory=list)

    def test_by_id(self, tid: str) -> TestCase | None:
        return next((t for t in self.tests if t.id == tid), None)

    def req_by_id(self, rid: str) -> Requirement | None:
        return next((r for r in self.requirements if r.id == rid), None)


def load_spec(path: str | Path) -> Spec:
    with open(path) as fh:
        raw = yaml.safe_load(fh)

    reqs = [
        Requirement(
            id=r["id"],
            description=r["description"],
            test_ids=r.get("test_ids", []),
            priority=r.get("priority", "must"),
        )
        for r in raw.get("requirements", [])
    ]

    tests = [
        TestCase(
            id=t["id"],
            description=t["description"],
            function=t["function"],
            args=t.get("args", []),
            kwargs=t.get("kwargs", {}),
            expected=t.get("expected"),
            expected_type=t.get("expected_type"),
            requirement_ids=t.get("requirement_ids", []),
            tags=t.get("tags", []),
        )
        for t in raw.get("tests", [])
    ]

    return Spec(
        name=raw["name"],
        version=str(raw.get("version", "1.0")),
        description=raw.get("description", ""),
        requirements=reqs,
        tests=tests,
        timeout_seconds=float(raw.get("timeout_seconds", 5.0)),
        tags=raw.get("tags", []),
    )
