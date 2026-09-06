import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path("os/database/os.db")

DEFAULT_PLATFORMS = (
    {
        "platform_name": "youtube",
        "publish_supported": True,
        "analytics_supported": True,
        "oauth_required": True,
        "metric_types": ["views", "watch_time", "average_view_duration", "retention", "likes", "comments", "shares"],
    },
    {
        "platform_name": "instagram",
        "publish_supported": True,
        "analytics_supported": False,
        "oauth_required": True,
        "metric_types": [],
    },
    {
        "platform_name": "facebook",
        "publish_supported": True,
        "analytics_supported": False,
        "oauth_required": True,
        "metric_types": [],
    },
    {
        "platform_name": "tiktok",
        "publish_supported": True,
        "analytics_supported": False,
        "oauth_required": True,
        "metric_types": [],
    },
)


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS platform_capabilities (
                platform_name TEXT PRIMARY KEY,
                publish_supported INTEGER NOT NULL DEFAULT 0,
                analytics_supported INTEGER NOT NULL DEFAULT 0,
                oauth_required INTEGER NOT NULL DEFAULT 0,
                metric_types TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        now = datetime.now(timezone.utc).isoformat()
        for platform in DEFAULT_PLATFORMS:
            conn.execute(
                """
                INSERT INTO platform_capabilities
                (platform_name, publish_supported, analytics_supported,
                 oauth_required, metric_types, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform_name) DO UPDATE SET
                    publish_supported=excluded.publish_supported,
                    analytics_supported=excluded.analytics_supported,
                    oauth_required=excluded.oauth_required,
                    metric_types=excluded.metric_types,
                    updated_at=excluded.updated_at
                """,
                (
                    platform["platform_name"],
                    int(platform["publish_supported"]),
                    int(platform["analytics_supported"]),
                    int(platform["oauth_required"]),
                    json.dumps(platform["metric_types"]),
                    now,
                    now,
                ),
            )
        conn.commit()


def _serialize(row):
    if row is None:
        return None
    data = dict(row)
    data["publish_supported"] = bool(data["publish_supported"])
    data["analytics_supported"] = bool(data["analytics_supported"])
    data["oauth_required"] = bool(data["oauth_required"])
    try:
        data["metric_types"] = json.loads(data.get("metric_types") or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        data["metric_types"] = []
    return data


def list_platform_capabilities():
    _ensure_table()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM platform_capabilities ORDER BY platform_name"
        ).fetchall()
    return [_serialize(row) for row in rows]


def get_platform_capability(platform_name):
    _ensure_table()
    normalized = (platform_name or "").strip().lower()
    if not normalized:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM platform_capabilities WHERE platform_name=?",
            (normalized,),
        ).fetchone()
    return _serialize(row)


def register_platform_capability(
    platform_name,
    *,
    publish_supported=False,
    analytics_supported=False,
    oauth_required=False,
    metric_types=None,
):
    _ensure_table()
    normalized = (platform_name or "").strip().lower()
    if not normalized:
        raise ValueError("platform_name is required")

    now = datetime.now(timezone.utc).isoformat()
    metrics = sorted(set(metric_types or []))
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO platform_capabilities
            (platform_name, publish_supported, analytics_supported,
             oauth_required, metric_types, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform_name) DO UPDATE SET
                publish_supported=excluded.publish_supported,
                analytics_supported=excluded.analytics_supported,
                oauth_required=excluded.oauth_required,
                metric_types=excluded.metric_types,
                updated_at=excluded.updated_at
            """,
            (
                normalized,
                int(bool(publish_supported)),
                int(bool(analytics_supported)),
                int(bool(oauth_required)),
                json.dumps(metrics),
                now,
                now,
            ),
        )
        conn.commit()
    return get_platform_capability(normalized)


def supports_publish(platform_name):
    capability = get_platform_capability(platform_name)
    return bool(capability and capability["publish_supported"])


def supports_analytics(platform_name):
    capability = get_platform_capability(platform_name)
    return bool(capability and capability["analytics_supported"])


def get_metric_types(platform_name):
    capability = get_platform_capability(platform_name)
    return capability["metric_types"] if capability else []
