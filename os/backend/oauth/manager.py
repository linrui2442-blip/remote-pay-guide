import sqlite3

DB_PATH = "os/database/os.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS oauth_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER,
        access_token TEXT,
        refresh_token TEXT,
        expires_at TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)
    return conn


def create_token(data):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO oauth_tokens (account_id, access_token, refresh_token, expires_at, created_at, updated_at) VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))",
        (data.get("account_id"), None, None, data.get("expires_at")),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return get_token(data.get("account_id"))


def get_token(account_id):
    conn = _connect()
    row = conn.execute("SELECT * FROM oauth_tokens WHERE account_id=?", (account_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return dict(zip(["id", "account_id", "access_token", "refresh_token", "expires_at", "created_at", "updated_at"], row))


def update_token(account_id, data):
    conn = _connect()
    conn.execute(
        "UPDATE oauth_tokens SET access_token=?, refresh_token=?, expires_at=?, updated_at=datetime('now') WHERE account_id=?",
        (data.get("access_token"), data.get("refresh_token"), data.get("expires_at"), account_id),
    )
    conn.commit()
    conn.close()
    return get_token(account_id)


def delete_token(account_id):
    conn = _connect()
    conn.execute("DELETE FROM oauth_tokens WHERE account_id=?", (account_id,))
    conn.commit()
    conn.close()
    return {"deleted": True}
