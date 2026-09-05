import sqlite3
from datetime import datetime

DB_PATH = "os/database/os.db"


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS video_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT,
            source TEXT,
            status TEXT,
            location TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def create_asset(asset):
    _init_db()
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO video_assets VALUES (NULL,?,?,?,?,?,?)",
        (asset.video_id, asset.source, asset.status, asset.location, now, now),
    )
    conn.commit()
    conn.close()
    return asset


def get_asset(video_id):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT video_id, source, status, location FROM video_assets WHERE video_id=?",
        (video_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {"video_id": row[0], "source": row[1], "status": row[2], "location": row[3]}


def get_assets():
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT video_id, source, status, location FROM video_assets").fetchall()
    conn.close()
    return [{"video_id": r[0], "source": r[1], "status": r[2], "location": r[3]} for r in rows]


def update_status(video_id, status):
    _init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE video_assets SET status=?, updated_at=? WHERE video_id=?",
        (status, datetime.utcnow().isoformat(), video_id),
    )
    conn.commit()
    conn.close()
