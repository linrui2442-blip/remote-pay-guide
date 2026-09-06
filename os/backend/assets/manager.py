import json
import sqlite3
import uuid
from datetime import datetime

from assets.models import VideoAsset

DB_PATH = "os/database/os.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS video_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT UNIQUE,
            video_id TEXT,
            production_result_id TEXT,
            source_provider TEXT,
            storage_type TEXT,
            asset_url TEXT,
            file_path TEXT,
            status TEXT,
            metadata TEXT,
            created_at TEXT,
            updated_at TEXT,
            source TEXT,
            location TEXT
        )
        """
    )
    columns = {row["name"] for row in cursor.execute("PRAGMA table_info(video_assets)").fetchall()}
    migrations = {
        "asset_id": "TEXT",
        "video_id": "TEXT",
        "production_result_id": "TEXT",
        "source_provider": "TEXT",
        "storage_type": "TEXT",
        "asset_url": "TEXT",
        "file_path": "TEXT",
        "status": "TEXT",
        "metadata": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT",
        "source": "TEXT",
        "location": "TEXT",
    }
    for name, field_type in migrations.items():
        if name not in columns:
            cursor.execute(f"ALTER TABLE video_assets ADD COLUMN {name} {field_type}")
    conn.commit()
    conn.close()


def _coerce_asset(asset):
    if isinstance(asset, VideoAsset):
        return asset

    data = dict(asset)
    source_provider = data.get("source_provider") or data.get("source") or "external"
    location = data.get("asset_url") or data.get("location") or data.get("file_path")
    storage_type = data.get("storage_type")
    if not storage_type:
        if source_provider == "github" and isinstance(location, str) and "github.io/" in location:
            storage_type = "github_pages"
        elif source_provider == "github":
            storage_type = "artifact"
        elif source_provider == "ai_gateway":
            storage_type = "ai_output"
        else:
            storage_type = "external"

    return VideoAsset(
        asset_id=data.get("asset_id") or f"asset_{uuid.uuid4().hex[:8]}",
        video_id=str(data.get("video_id") or "UNKNOWN"),
        production_result_id=data.get("production_result_id"),
        source_provider=source_provider,
        storage_type=storage_type,
        asset_url=data.get("asset_url") or (location if isinstance(location, str) and location.startswith(("http://", "https://")) else None),
        file_path=data.get("file_path"),
        status=data.get("status", "registered"),
        metadata=data.get("metadata") or {},
        source=data.get("source") or source_provider,
        location=data.get("location") or location,
    )


def create_video_asset(asset):
    _init_db()
    asset = _coerce_asset(asset)
    if not asset.asset_id:
        asset.asset_id = f"asset_{uuid.uuid4().hex[:8]}"

    now = datetime.utcnow().isoformat()
    metadata = json.dumps(asset.metadata or {}, ensure_ascii=False)
    conn = _connect()
    conn.execute(
        """
        INSERT OR REPLACE INTO video_assets
        (id, asset_id, video_id, production_result_id, source_provider,
         storage_type, asset_url, file_path, status, metadata, created_at,
         updated_at, source, location)
        VALUES (
            (SELECT id FROM video_assets WHERE asset_id=?),
            ?,?,?,?,?,?,?,?,?,?,?,?,?
        )
        """,
        (
            asset.asset_id,
            asset.asset_id,
            asset.video_id,
            asset.production_result_id,
            asset.source_provider,
            asset.storage_type,
            asset.asset_url,
            asset.file_path,
            asset.status,
            metadata,
            asset.created_at or now,
            now,
            asset.source,
            asset.location,
        ),
    )
    conn.commit()
    conn.close()

    asset.created_at = asset.created_at or now
    asset.updated_at = now
    return asset


def create_asset(asset):
    return create_video_asset(asset)


def _serialize(row):
    if not row:
        return None
    data = dict(row)
    try:
        data["metadata"] = json.loads(data.get("metadata") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        data["metadata"] = {}
    return data


def get_asset(video_id):
    _init_db()
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM video_assets WHERE video_id=? ORDER BY id DESC LIMIT 1",
        (video_id,),
    ).fetchone()
    conn.close()
    return _serialize(row)


def get_asset_by_asset_id(asset_id):
    _init_db()
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM video_assets WHERE asset_id=? LIMIT 1",
        (asset_id,),
    ).fetchone()
    conn.close()
    return _serialize(row)


def get_assets():
    _init_db()
    conn = _connect()
    rows = conn.execute("SELECT * FROM video_assets ORDER BY id").fetchall()
    conn.close()
    return [_serialize(row) for row in rows]


def update_status(video_id, status):
    _init_db()
    conn = _connect()
    conn.execute(
        "UPDATE video_assets SET status=?, updated_at=? WHERE video_id=?",
        (status, datetime.utcnow().isoformat(), video_id),
    )
    conn.commit()
    conn.close()
