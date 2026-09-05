import sqlite3
from datetime import datetime
from .state import JOB_CREATED

DB_PATH = "os/database/os.db"


def init_runtime_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS runtime_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        job_type TEXT,
        provider TEXT,
        status TEXT,
        input TEXT,
        output TEXT,
        error TEXT,
        created_at TEXT,
        updated_at TEXT
    )""")
    conn.commit()
    conn.close()


def create_job(data):
    init_runtime_table()
    now=datetime.utcnow().isoformat()
    conn=sqlite3.connect(DB_PATH)
    cur=conn.execute("INSERT INTO runtime_jobs(task_id,job_type,provider,status,input,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",(data['task_id'],data['job_type'],data['provider'],JOB_CREATED,data.get('input','{}'),now,now))
    conn.commit()
    job=get_job(cur.lastrowid)
    conn.close()
    return job


def get_jobs():
    init_runtime_table()
    conn=sqlite3.connect(DB_PATH); conn.row_factory=sqlite3.Row
    rows=conn.execute('SELECT * FROM runtime_jobs').fetchall(); conn.close()
    return [dict(r) for r in rows]


def get_job(job_id):
    init_runtime_table()
    conn=sqlite3.connect(DB_PATH); conn.row_factory=sqlite3.Row
    row=conn.execute('SELECT * FROM runtime_jobs WHERE id=?',(job_id,)).fetchone(); conn.close()
    return dict(row) if row else None


def update_job_status(job_id,status):
    conn=sqlite3.connect(DB_PATH)
    conn.execute('UPDATE runtime_jobs SET status=?,updated_at=? WHERE id=?',(status,datetime.utcnow().isoformat(),job_id))
    conn.commit(); conn.close()


def update_job_result(job_id,output=None,error=None):
    conn=sqlite3.connect(DB_PATH)
    conn.execute('UPDATE runtime_jobs SET output=?,error=?,updated_at=? WHERE id=?',(output,error,datetime.utcnow().isoformat(),job_id))
    conn.commit(); conn.close()
    return get_job(job_id)
