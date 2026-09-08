from data.database_path import database_path
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


DB_PATH = database_path()


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table():
    with _connect() as conn:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS ai_gateway_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                video_url TEXT,
                updated_at TEXT NOT NULL
            )
            '''
        )
        conn.commit()


def _normalize_url(value):
    value = str(value or '').strip()
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValueError('AI Gateway video URL must be an absolute http(s) URL')
    return value.rstrip('/')


def get_ai_gateway_settings():
    """Return non-secret AI Remote Production settings.

    The endpoint may be persisted in OS SQLite. The API key remains process
    environment only and is never stored or returned.
    """
    _ensure_table()
    with _connect() as conn:
        row = conn.execute(
            'SELECT video_url, updated_at FROM ai_gateway_settings WHERE id=1'
        ).fetchone()

    persisted_url = row['video_url'] if row else None
    env_url = str(os.getenv('AI_GATEWAY_VIDEO_URL') or '').strip() or None
    video_url = persisted_url or env_url
    source = 'os_settings' if persisted_url else ('environment' if env_url else 'none')
    return {
        'video_url': video_url,
        'source': source,
        'updated_at': row['updated_at'] if row else None,
        'configured': bool(video_url),
        'api_key_configured': bool(os.getenv('AI_GATEWAY_API_KEY')),
        'local_inference': False,
    }


def save_ai_gateway_settings(video_url=None):
    normalized_url = _normalize_url(video_url)
    _ensure_table()
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            '''
            INSERT INTO ai_gateway_settings (id, video_url, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                video_url=excluded.video_url,
                updated_at=excluded.updated_at
            ''',
            (normalized_url, now),
        )
        conn.commit()
    return get_ai_gateway_settings()
