"""
SQLite audit log for all evaluation runs.

Schema
------
runs:
  id            INTEGER PK
  spec_name     TEXT
  spec_version  TEXT
  code_path     TEXT
  timestamp     TEXT
  overall_score REAL
  tas           REAL
  weighted_tas  REAL
  pass_rate     REAL
  static_score  REAL
  n_tests       INTEGER
  n_passed      INTEGER
  n_failed      INTEGER
  dominant_failure_mode TEXT
  report_json   TEXT

Useful SQL queries are shown at the bottom of this module.
"""

from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from report.audit_report import AuditReport


DEFAULT_DB = "results/audit_log.db"


def init_db(db_path: str = DEFAULT_DB) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            spec_name            TEXT,
            spec_version         TEXT,
            code_path            TEXT,
            timestamp            TEXT,
            overall_score        REAL,
            tas                  REAL,
            weighted_tas         REAL,
            pass_rate            REAL,
            static_score         REAL,
            n_tests              INTEGER,
            n_passed             INTEGER,
            n_failed             INTEGER,
            dominant_failure_mode TEXT,
            report_json          TEXT
        )
    """)
    conn.commit()
    return conn


def log_run(report: AuditReport, db_path: str = DEFAULT_DB) -> int:
    conn = init_db(db_path)

    def _default(o):
        if hasattr(o, "__dict__"):
            return o.__dict__
        return str(o)

    report_json = json.dumps(report.__dict__, default=_default)

    cur = conn.execute("""
        INSERT INTO runs
          (spec_name, spec_version, code_path, timestamp,
           overall_score, tas, weighted_tas, pass_rate, static_score,
           n_tests, n_passed, n_failed, dominant_failure_mode, report_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        report.spec_name,
        report.spec_version,
        report.code_path,
        report.timestamp,
        report.overall_score,
        report.trace.tas,
        report.trace.weighted_tas,
        report.dynamic.pass_rate,
        report.static.score(),
        report.dynamic.n_tests,
        report.dynamic.n_passed,
        report.dynamic.n_failed,
        report.taxonomy.dominant_mode,
        report_json,
    ))
    conn.commit()
    run_id = cur.lastrowid
    conn.close()
    return run_id


def query_runs(
    spec_name: str | None = None,
    limit: int = 50,
    db_path: str = DEFAULT_DB,
) -> list[dict]:
    if not Path(db_path).exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    q = "SELECT id, spec_name, code_path, timestamp, overall_score, tas, pass_rate FROM runs"
    params: list = []
    if spec_name:
        q += " WHERE spec_name = ?"
        params.append(spec_name)
    q += f" ORDER BY timestamp DESC LIMIT {limit}"
    rows = [dict(r) for r in conn.execute(q, params).fetchall()]
    conn.close()
    return rows


"""
Useful SQL queries
------------------
-- Best variant per spec:
SELECT spec_name, code_path, MAX(overall_score) as best_score
FROM runs GROUP BY spec_name;

-- Trend over time:
SELECT date(timestamp) as day, AVG(overall_score) as avg_score
FROM runs WHERE spec_name = 'string_utils'
GROUP BY day ORDER BY day;

-- Failure-mode breakdown:
SELECT dominant_failure_mode, COUNT(*) as cnt
FROM runs GROUP BY dominant_failure_mode ORDER BY cnt DESC;
"""
