from data.database_path import database_path
import json
import sqlite3
import uuid
from datetime import datetime

from assets.models import VideoAsset

DB_PATH = database_path()


def _connect():
    conn = sqlite3.connect(database_path())
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
    duplicates = cursor.execute('SELECT production_result_id FROM video_assets WHERE production_result_id IS NOT NULL GROUP BY production_result_id HAVING COUNT(*) > 1').fetchall()
    if not duplicates:
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS uq_video_assets_production_result ON video_assets(production_result_id) WHERE production_result_id IS NOT NULL')
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
    conn.execute('BEGIN IMMEDIATE')
    try:
        existing = conn.execute('SELECT * FROM video_assets WHERE asset_id=?', (asset.asset_id,)).fetchone()
        if existing and (json.loads(existing['metadata'] or '{}')).get('quality_policy_version'):
            raise ValueError('Quality-gated assets cannot be overwritten by the legacy registry')
        if asset.production_result_id is not None:
            linked = conn.execute('SELECT asset_id FROM video_assets WHERE production_result_id=?', (str(asset.production_result_id),)).fetchall()
            if len(linked) > 1 or (linked and linked[0]['asset_id'] != asset.asset_id):
                raise ValueError('ProductionResult already has an asset or duplicate legacy history')
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='production_results'").fetchone():
                result = conn.execute('SELECT output FROM production_results WHERE id=?', (asset.production_result_id,)).fetchone()
                output = json.loads(result['output'] or '{}') if result else {}
                if isinstance(output, dict) and (output.get('defer_asset_binding') or output.get('g4b_no_asset_binding')):
                    raise ValueError('Deferred ProductionResult requires the unified quality gate')
    except Exception:
        conn.rollback()
        conn.close()
        raise
    try:
        conn.execute(
            """INSERT INTO video_assets
            (asset_id,video_id,production_result_id,source_provider,storage_type,
             asset_url,file_path,status,metadata,created_at,updated_at,source,location)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(asset_id) DO UPDATE SET
                video_id=excluded.video_id, production_result_id=excluded.production_result_id,
                source_provider=excluded.source_provider, storage_type=excluded.storage_type,
                asset_url=excluded.asset_url, file_path=excluded.file_path, status=excluded.status,
                metadata=excluded.metadata, updated_at=excluded.updated_at,
                source=excluded.source, location=excluded.location""",
            (asset.asset_id, asset.video_id, asset.production_result_id, asset.source_provider,
             asset.storage_type, asset.asset_url, asset.file_path, asset.status, metadata,
             asset.created_at or now, now, asset.source, asset.location),
        )
        conn.commit()
    finally:
        # Closing also rolls back on uniqueness or other persistence failures.
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
