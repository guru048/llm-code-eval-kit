"""
data_pipeline v1 — correct implementation.
Simulates a correct LLM output for the data_pipeline spec.
"""

import statistics
from typing import Any


def normalise_records(records: list[dict]) -> list[dict]:
    """Strip whitespace from all string values in each record."""
    return [
        {k: v.strip() if isinstance(v, str) else v for k, v in record.items()}
        for record in records
    ]


def filter_by_field(records: list[dict], field: str, value: Any) -> list[dict]:
    """Return records where record[field] == value."""
    return [r for r in records if r.get(field) == value]


def compute_stats(records: list[dict], field: str) -> dict:
    """Return mean, median, and population std for a numeric field."""
    values = [r[field] for r in records]
    mean   = sum(values) / len(values)
    med    = statistics.median(values)
    std    = statistics.pstdev(values)
    return {"mean": mean, "median": med, "std": std}


def deduplicate(records: list[dict], key: str) -> list[dict]:
    """Remove duplicate records keeping the first occurrence of each key value."""
    seen    = set()
    result  = []
    for record in records:
        k = record.get(key)
        if k not in seen:
            seen.add(k)
            result.append(record)
    return result
