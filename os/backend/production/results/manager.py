import json
import sqlite3
from datetime import datetime

from assets.binding import create_asset_from_result

DB_PATH = "os/database/os.db"


def init_results_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS production_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        runtime_job_id INTEGER,
        provider TEXT,
        asset_id INTEGER,
        status TEXT,
        output TEXT,
        error TEXT,
        created_at TEXT,
        updated_at TEXT
    )""")
    conn.commit()
    conn.close()


def create_result(data):
    init_results_table()
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO production_results(runtime_job_id,provider,asset_id,status,output,error,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
        (data['runtime_job_id'], data['provider'], data.get('asset_id'), data.get('status','created'), json.dumps(data.get('output',{})), data.get('error'), now, now)
    )
    conn.commit()
    result = get_result(cur.lastrowid)
    conn.close()

    if result and result.get("status") == "completed":
        binding = create_asset_from_result(result)
        if binding.get("asset_id"):
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "UPDATE production_results SET asset_id=?,updated_at=? WHERE id=?",
                (binding["asset_id"], datetime.utcnow().isoformat(), result["id"]),
            )
            conn.commit()
            conn.close()

    return get_result(cur.lastrowid)


def get_results():
    init_results_table()
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute('SELECT * FROM production_results').fetchall(); conn.close()
    return [dict(r) for r in rows]


def get_result(result_id):
    init_results_table()
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    row = conn.execute('SELECT * FROM production_results WHERE id=?',(result_id,)).fetchone(); conn.close()
    return dict(row) if row else None


def get_result_by_job(runtime_job_id):
    init_results_table()
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    row = conn.execute('SELECT * FROM production_results WHERE runtime_job_id=?',(runtime_job_id,)).fetchone(); conn.close()
    return dict(row) if row else None


def update_result_status(result_id, status):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('UPDATE production_results SET status=?,updated_at=? WHERE id=?',(status,datetime.utcnow().isoformat(),result_id))
    conn.commit(); conn.close()
    result = get_result(result_id)
    if result and status == "completed":
        create_asset_from_result(result)
    return result
