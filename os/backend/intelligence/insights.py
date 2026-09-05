import json
import sqlite3
from datetime import datetime
from intelligence.models import ContentInsight

DB_PATH = "os/database/os.db"


def init_insights_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS content_insights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT,
            score REAL,
            strengths TEXT,
            weaknesses TEXT,
            recommendations TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


init_insights_db()


def create_insight(insight):
    init_insights_db()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    created_at = datetime.utcnow().isoformat()

    cursor.execute(
        """
        INSERT INTO content_insights
        (video_id, score, strengths, weaknesses, recommendations, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            insight.get("video_id"),
            insight.get("score", 0),
            json.dumps(insight.get("strengths", [])),
            json.dumps(insight.get("weaknesses", [])),
            json.dumps(insight.get("recommendations", [])),
            created_at,
        ),
    )

    conn.commit()
    insight_id = cursor.lastrowid
    conn.close()

    insight["id"] = insight_id
    insight["created_at"] = created_at
    return insight


def get_insights():
    init_insights_db()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM content_insights ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    return [_serialize(row) for row in rows]


def get_video_insight(video_id):
    init_insights_db()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM content_insights WHERE video_id = ? ORDER BY id DESC LIMIT 1",
        (video_id,),
    )
    row = cursor.fetchone()
    conn.close()

    return _serialize(row) if row else None


def _serialize(row):
    return {
        "id": row["id"],
        "video_id": row["video_id"],
        "score": row["score"],
        "strengths": json.loads(row["strengths"] or "[]"),
        "weaknesses": json.loads(row["weaknesses"] or "[]"),
        "recommendations": json.loads(row["recommendations"] or "[]"),
        "created_at": row["created_at"],
    }
