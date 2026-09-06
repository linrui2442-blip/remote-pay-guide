import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from analytics.manager import get_latest_content_metrics
from data.models import ConversionRecord, IntentEvent


DB_PATH = Path("os/database/os.db")


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS intent_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id TEXT NOT NULL,
                video_id TEXT,
                session_id TEXT,
                source TEXT,
                event_type TEXT NOT NULL,
                event_value TEXT,
                metadata TEXT,
                occurred_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversion_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id TEXT NOT NULL,
                video_id TEXT,
                session_id TEXT,
                source TEXT,
                conversion_type TEXT NOT NULL,
                value REAL NOT NULL DEFAULT 1,
                currency TEXT,
                intent_event_id INTEGER,
                metadata TEXT,
                occurred_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_intent_content ON intent_events(content_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_intent_type ON intent_events(event_type)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversion_content ON conversion_records(content_id)"
        )
        conn.commit()


def _json_dump(value):
    return json.dumps(value, ensure_ascii=False) if value is not None else None


def _json_load(value, fallback):
    if value in (None, ""):
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _serialize_intent(row):
    if not row:
        return None
    data = dict(row)
    data["event_value"] = _json_load(data.get("event_value"), data.get("event_value"))
    data["metadata"] = _json_load(data.get("metadata"), {})
    return data


def _serialize_conversion(row):
    if not row:
        return None
    data = dict(row)
    data["metadata"] = _json_load(data.get("metadata"), {})
    return data


def record_intent(event):
    _ensure_tables()
    if not isinstance(event, IntentEvent):
        event = IntentEvent(**dict(event))

    occurred_at = event.occurred_at or datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO intent_events
            (content_id, video_id, session_id, source, event_type,
             event_value, metadata, occurred_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.content_id,
                event.video_id,
                event.session_id,
                event.source,
                event.event_type,
                _json_dump(event.event_value),
                _json_dump(event.metadata or {}),
                occurred_at,
            ),
        )
        event_id = cursor.lastrowid
        conn.commit()
        row = conn.execute("SELECT * FROM intent_events WHERE id=?", (event_id,)).fetchone()
    return _serialize_intent(row)


def record_conversion(record):
    _ensure_tables()
    if not isinstance(record, ConversionRecord):
        record = ConversionRecord(**dict(record))

    occurred_at = record.occurred_at or datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO conversion_records
            (content_id, video_id, session_id, source, conversion_type,
             value, currency, intent_event_id, metadata, occurred_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.content_id,
                record.video_id,
                record.session_id,
                record.source,
                record.conversion_type,
                record.value,
                record.currency,
                record.intent_event_id,
                _json_dump(record.metadata or {}),
                occurred_at,
            ),
        )
        record_id = cursor.lastrowid
        conn.commit()
        row = conn.execute(
            "SELECT * FROM conversion_records WHERE id=?", (record_id,)
        ).fetchone()
    return _serialize_conversion(row)


def get_intent_events(content_id=None):
    _ensure_tables()
    with _connect() as conn:
        if content_id is None:
            rows = conn.execute("SELECT * FROM intent_events ORDER BY id").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM intent_events WHERE content_id=? ORDER BY id",
                (content_id,),
            ).fetchall()
    return [_serialize_intent(row) for row in rows]


def get_conversions(content_id=None):
    _ensure_tables()
    with _connect() as conn:
        if content_id is None:
            rows = conn.execute("SELECT * FROM conversion_records ORDER BY id").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM conversion_records WHERE content_id=? ORDER BY id",
                (content_id,),
            ).fetchall()
    return [_serialize_conversion(row) for row in rows]


def _sum_metric(metrics, key):
    return sum((item.get(key) or 0) for item in metrics)


def _feedback_samples(intent, limit=10):
    samples = []
    for event in reversed(intent):
        if event.get("event_type") != "content_feedback":
            continue
        value = event.get("event_value")
        text = value.get("text") if isinstance(value, dict) else value
        text = str(text or "").strip()
        if not text:
            continue
        samples.append(
            {
                "text": text[:1000],
                "source": event.get("source"),
                "occurred_at": event.get("occurred_at"),
                "metadata": event.get("metadata") or {},
            }
        )
        if len(samples) >= limit:
            break
    return samples


def get_content_funnel(content_id):
    # Platform APIs usually return cumulative snapshots. Use the newest
    # snapshot per video/platform so scheduled collection does not inflate the
    # growth funnel by summing the same traffic repeatedly.
    traffic = get_latest_content_metrics(content_id)
    intent = get_intent_events(content_id)
    conversions = get_conversions(content_id)

    intent_by_type = {}
    for event in intent:
        event_type = event.get("event_type") or "unknown"
        intent_by_type[event_type] = intent_by_type.get(event_type, 0) + 1

    conversion_by_type = {}
    for record in conversions:
        conversion_type = record.get("conversion_type") or "unknown"
        conversion_by_type[conversion_type] = conversion_by_type.get(conversion_type, 0) + 1

    return {
        "content_id": content_id,
        "traffic": {
            "records": len(traffic),
            "impressions": _sum_metric(traffic, "impressions"),
            "views": _sum_metric(traffic, "views"),
            "clicks": _sum_metric(traffic, "clicks"),
            "watch_time": _sum_metric(traffic, "watch_time"),
            "likes": _sum_metric(traffic, "likes"),
            "comments": _sum_metric(traffic, "comments"),
            "shares": _sum_metric(traffic, "shares"),
        },
        "intent": {
            "total": len(intent),
            "by_type": intent_by_type,
            "recent_feedback": _feedback_samples(intent),
        },
        "conversion": {
            "total": len(conversions),
            "value": sum((item.get("value") or 0) for item in conversions),
            "by_type": conversion_by_type,
        },
    }


def get_funnel_summary():
    _ensure_tables()
    traffic = get_latest_content_metrics(None)
    intent = get_intent_events()
    conversions = get_conversions()

    return {
        "traffic_records": len(traffic),
        "impressions": _sum_metric(traffic, "impressions"),
        "views": _sum_metric(traffic, "views"),
        "clicks": _sum_metric(traffic, "clicks"),
        "intent_events": len(intent),
        "content_feedback": len(
            [item for item in intent if item.get("event_type") == "content_feedback"]
        ),
        "referral_clicks": len(
            [item for item in intent if item.get("event_type") == "binance_referral_click"]
        ),
        "conversions": len(conversions),
        "conversion_value": sum((item.get("value") or 0) for item in conversions),
    }
