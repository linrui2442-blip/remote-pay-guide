import sqlite3
import json
from datetime import datetime

DB_PATH = "os/database/os.db"


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
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
    """)
    conn.commit()
    conn.close()


def create_video_asset(asset):
    _init_db()
    now = datetime.utcnow().isoformat()
    metadata = json.dumps(asset.metadata or {})
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT OR REPLACE INTO video_assets
        VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            asset.asset_id,
            asset.video_id,
            asset.production_result_id,
            asset.source_provider,
            asset.storage_type,
            asset.asset_url,
            asset.file_path,
            asset.status,
            metadata,
            now,
            now,
            asset.source,
            asset.location,
        ),
    )
    conn.commit()
    conn.close()
    return asset


def create_asset(asset):
    return create_video_asset(asset)


def get_asset(video_id):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT asset_id, video_id, production_result_id, source_provider, storage_type, asset_url, file_path, status FROM video_assets WHERE video_id=?",
        (video_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "asset_id": row[0],
        "video_id": row[1],
        "production_result_id": row[2],
        "source_provider": row[3],
        "storage_type": row[4],
        "asset_url": row[5],
        "file_path": row[6],
        "status": row[7],
    }


def get_assets():
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT asset_id, video_id, source_provider, storage_type, asset_url, status FROM video_assets").fetchall()
    conn.close()
    return [
        {
            "asset_id": r[0],
            "video_id": r[1],
            "source_provider": r[2],
            "storage_type": r[3],
            "asset_url": r[4],
            "status": r[5],
        }
        for r in rows
    ]


def update_status(video_id, status):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE video_assets SET status=?, updated_at=? WHERE video_id=?",
        (status, datetime.utcnow().isoformat(), video_id),
    )
    conn.commit()
    conn.close()
