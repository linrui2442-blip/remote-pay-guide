from data.database_path import database_path
import os
import sqlite3
from datetime import datetime

DB_PATH = database_path()


def _connect():
    database_path().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT,
            account_name TEXT,
            status TEXT,
            access_token TEXT,
            refresh_token TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def create_account(account):
    _init_db()
    now = datetime.utcnow().isoformat()
    conn = _connect()
    cursor = conn.execute(
        """
        INSERT INTO accounts
        (platform, account_name, status, access_token, refresh_token, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            account.platform,
            account.account_name,
            account.status,
            None,
            None,
            now,
            now,
        ),
    )
    conn.commit()
    account_id = cursor.lastrowid
    conn.close()
    return get_account(account_id)


def get_accounts():
    _init_db()
    conn = _connect()
    rows = conn.execute(
        "SELECT id, platform, account_name, status FROM accounts"
    ).fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "platform": row["platform"],
            "account_name": row["account_name"],
            "status": row["status"],
        }
        for row in rows
    ]


def get_account(account_id):
    _init_db()
    conn = _connect()
    row = conn.execute(
        "SELECT id, platform, account_name, status FROM accounts WHERE id=?",
        (account_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_account_status(account_id, status):
    _init_db()
    conn = _connect()
    conn.execute(
        "UPDATE accounts SET status=?, updated_at=? WHERE id=?",
        (status, datetime.utcnow().isoformat(), account_id),
    )
    conn.commit()
    conn.close()
    return get_account(account_id)
