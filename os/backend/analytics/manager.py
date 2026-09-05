import sqlite3
from datetime import datetime

DB_PATH = "os/database/os.db"


def _connect():
    return sqlite3.connect(DB_PATH)


def _ensure_table():
    with _connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS analytics_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT,
            platform TEXT,
            views INTEGER,
            likes INTEGER,
            comments INTEGER,
            watch_time INTEGER,
            shares INTEGER,
            collected_at TEXT
        )
        """)


def save_metric(metric):
    _ensure_table()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO analytics_metrics (video_id, platform, views, likes, comments, watch_time, shares, collected_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (metric.video_id, metric.platform, metric.views, metric.likes, metric.comments, metric.watch_time, metric.shares, metric.collected_at or datetime.utcnow().isoformat())
        )
    return metric


def get_metrics():
    _ensure_table()
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM analytics_metrics").fetchall()
    return rows


def get_video_metrics(video_id):
    _ensure_table()
    with _connect() as conn:
        return conn.execute("SELECT * FROM analytics_metrics WHERE video_id=?", (video_id,)).fetchall()


def get_platform_metrics(platform):
    _ensure_table()
    with _connect() as conn:
        return conn.execute("SELECT * FROM analytics_metrics WHERE platform=?", (platform,)).fetchall()
