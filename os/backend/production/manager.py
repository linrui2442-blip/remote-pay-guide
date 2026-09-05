import sqlite3
from datetime import datetime

DB_PATH = "os/database/os.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS production_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_type TEXT,
        provider TEXT,
        status TEXT,
        workflow TEXT,
        branch TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)
    conn.commit()
    conn.close()


def create_production_task(task):
    init_db()
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO production_tasks(task_type,provider,status,workflow,branch,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (task.task_type, task.provider, task.status, task.workflow, task.branch, now, now))
    conn.commit()
    task_id = cur.lastrowid
    conn.close()
    return get_production_task(task_id)


def get_production_tasks():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT * FROM production_tasks").fetchall()
    conn.close()
    return [dict(zip(["id","task_type","provider","status","workflow","branch","created_at","updated_at"], r)) for r in rows]


def get_production_task(task_id):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT * FROM production_tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return dict(zip(["id","task_type","provider","status","workflow","branch","created_at","updated_at"], row))


def update_production_status(task_id, status):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE production_tasks SET status=?, updated_at=? WHERE id=?", (status, datetime.utcnow().isoformat(), task_id))
    conn.commit()
    conn.close()
