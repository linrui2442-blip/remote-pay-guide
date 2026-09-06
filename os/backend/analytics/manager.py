import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from analytics.models import AnalyticsMetric


DB_PATH = Path("os/database/os.db")


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT,
                content_id TEXT,
                platform TEXT,
                account_id INTEGER,
                source TEXT,
                impressions INTEGER DEFAULT 0,
                views INTEGER DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                ctr REAL,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                watch_time INTEGER DEFAULT 0,
                average_view_duration REAL,
                retention REAL,
                shares INTEGER DEFAULT 0,
                collected_at TEXT
            )
            """
        )

        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(analytics_metrics)").fetchall()
        }
        migrations = {
            "content_id": "TEXT",
            "account_id": "INTEGER",
            "source": "TEXT",
            "impressions": "INTEGER DEFAULT 0",
            "clicks": "INTEGER DEFAULT 0",
            "ctr": "REAL",
            "average_view_duration": "REAL",
            "retention": "REAL",
        }
        for name, field_type in migrations.items():
            if name not in columns:
                conn.execute(
                    f"ALTER TABLE analytics_metrics ADD COLUMN {name} {field_type}"
                )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_analytics_video ON analytics_metrics(video_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_analytics_content ON analytics_metrics(content_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_analytics_platform ON analytics_metrics(platform)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_analytics_account ON analytics_metrics(account_id)"
        )
        conn.commit()


def _coerce_metric(metric):
    if not isinstance(metric, AnalyticsMetric):
        metric = AnalyticsMetric(**dict(metric))
    if not metric.content_id:
        metric.content_id = metric.video_id
    return metric


def save_metric(metric):
    """Append one analytics snapshot.

    Raw history is intentionally preserved. Data Center funnel calculations use
    the newest snapshot per video/platform/account so periodic collection does
    not double-count cumulative platform metrics.
    """
    _ensure_table()
    metric = _coerce_metric(metric)
    collected_at = metric.collected_at or datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO analytics_metrics
            (video_id, content_id, platform, account_id, source, impressions, views,
             clicks, ctr, likes, comments, watch_time, average_view_duration,
             retention, shares, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metric.video_id,
                metric.content_id,
                metric.platform,
                metric.account_id,
                metric.source,
                metric.impressions,
                metric.views,
                metric.clicks,
                metric.ctr,
                metric.likes,
                metric.comments,
                metric.watch_time,
                metric.average_view_duration,
                metric.retention,
                metric.shares,
                collected_at,
            ),
        )
        row_id = cursor.lastrowid
        conn.commit()
        row = conn.execute(
            "SELECT * FROM analytics_metrics WHERE id=?", (row_id,)
        ).fetchone()
    return _serialize(row)


def _serialize(row):
    return dict(row) if row else None


def get_metrics():
    """Return raw analytics snapshot history."""
    _ensure_table()
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM analytics_metrics ORDER BY id").fetchall()
    return [_serialize(row) for row in rows]


def _latest_query(where_clause="", params=()):
    _ensure_table()
    filter_sql = f"WHERE {where_clause}" if where_clause else ""
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT a.*
            FROM analytics_metrics a
            JOIN (
                SELECT video_id, platform, account_id, MAX(id) AS max_id
                FROM analytics_metrics
                {filter_sql}
                GROUP BY video_id, platform, account_id
            ) latest ON latest.max_id = a.id
            ORDER BY a.id
            """,
            params,
        ).fetchall()
    return [_serialize(row) for row in rows]


def get_latest_metrics():
    """Return the newest snapshot for each video/platform/account tuple."""
    return _latest_query()


def get_video_metrics(video_id):
    _ensure_table()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM analytics_metrics WHERE video_id=? ORDER BY id",
            (video_id,),
        ).fetchall()
    return [_serialize(row) for row in rows]


def get_latest_video_metrics(video_id):
    return _latest_query("video_id=?", (video_id,))


def get_content_metrics(content_id=None):
    _ensure_table()
    if content_id is None:
        return get_metrics()

    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM analytics_metrics WHERE content_id=? ORDER BY id",
            (content_id,),
        ).fetchall()
    return [_serialize(row) for row in rows]


def get_latest_content_metrics(content_id=None):
    if content_id is None:
        return get_latest_metrics()
    return _latest_query("content_id=?", (content_id,))


def get_platform_metrics(platform):
    _ensure_table()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM analytics_metrics WHERE platform=? ORDER BY id",
            (platform,),
        ).fetchall()
    return [_serialize(row) for row in rows]


def get_latest_platform_metrics(platform):
    return _latest_query("platform=?", (platform,))


def get_account_metrics(account_id, platform=None, latest=False):
    _ensure_table()
    clauses = ["account_id=?"]
    params = [account_id]
    if platform:
        clauses.append("platform=?")
        params.append(str(platform).strip().lower())
    where_clause = " AND ".join(clauses)
    if latest:
        return _latest_query(where_clause, tuple(params))

    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM analytics_metrics WHERE {where_clause} ORDER BY id",
            tuple(params),
        ).fetchall()
    return [_serialize(row) for row in rows]
