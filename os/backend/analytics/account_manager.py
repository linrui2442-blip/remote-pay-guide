from data.database_path import database_path
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from analytics.models import AccountAnalyticsMetric


DB_PATH = database_path()


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS account_analytics_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                source TEXT,
                period_start TEXT,
                period_end TEXT,
                metrics_json TEXT NOT NULL DEFAULT '{}',
                collected_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_account_analytics_account_platform "
            "ON account_analytics_metrics(account_id, platform)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_account_analytics_period "
            "ON account_analytics_metrics(period_start, period_end)"
        )
        conn.commit()


def _serialize(row):
    if not row:
        return None
    data = dict(row)
    try:
        data["metrics"] = json.loads(data.get("metrics_json") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        data["metrics"] = {}
    return data


def save_account_metric(metric):
    _ensure_table()
    if not isinstance(metric, AccountAnalyticsMetric):
        metric = AccountAnalyticsMetric(**dict(metric))
    platform = str(metric.platform or "").strip().lower()
    if not platform:
        raise ValueError("platform is required")
    collected_at = metric.collected_at or datetime.now(timezone.utc).isoformat()
    metrics_json = json.dumps(metric.metrics or {}, separators=(",", ":"), sort_keys=True)

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO account_analytics_metrics
            (account_id, platform, source, period_start, period_end,
             metrics_json, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metric.account_id,
                platform,
                metric.source,
                metric.period_start,
                metric.period_end,
                metrics_json,
                collected_at,
            ),
        )
        row_id = cursor.lastrowid
        conn.commit()
        row = conn.execute(
            "SELECT * FROM account_analytics_metrics WHERE id=?",
            (row_id,),
        ).fetchone()
    return _serialize(row)


def get_account_metric_history(account_id, platform=None):
    _ensure_table()
    clauses = ["account_id=?"]
    params = [account_id]
    if platform:
        clauses.append("platform=?")
        params.append(str(platform).strip().lower())
    where = " AND ".join(clauses)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM account_analytics_metrics WHERE {where} ORDER BY id",
            tuple(params),
        ).fetchall()
    return [_serialize(row) for row in rows]


def get_latest_account_metrics(account_id=None, platform=None):
    _ensure_table()
    clauses = []
    params = []
    if account_id is not None:
        clauses.append("account_id=?")
        params.append(account_id)
    if platform:
        clauses.append("platform=?")
        params.append(str(platform).strip().lower())
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT a.*
            FROM account_analytics_metrics a
            JOIN (
                SELECT account_id, platform, MAX(id) AS max_id
                FROM account_analytics_metrics
                {where}
                GROUP BY account_id, platform
            ) latest ON latest.max_id = a.id
            ORDER BY a.id
            """,
            tuple(params),
        ).fetchall()
    return [_serialize(row) for row in rows]
