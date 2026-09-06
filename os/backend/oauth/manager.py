import os
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = "os/database/os.db"


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS oauth_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            access_token TEXT,
            refresh_token TEXT,
            expires_at TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS oauth_states (
            state TEXT PRIMARY KEY,
            account_id INTEGER,
            provider TEXT,
            expires_at TEXT,
            created_at TEXT
        )
        """
    )
    return conn


def create_token(data):
    """Create or update the credential record for one account."""
    account_id = data.get("account_id")
    if account_id is None:
        raise ValueError("account_id is required")

    conn = _connect()
    existing = conn.execute(
        "SELECT id, refresh_token FROM oauth_tokens "
        "WHERE account_id=? ORDER BY id DESC LIMIT 1",
        (account_id,),
    ).fetchone()

    refresh_token = data.get("refresh_token")
    if existing and not refresh_token:
        refresh_token = existing["refresh_token"]

    if existing:
        conn.execute(
            """
            UPDATE oauth_tokens
            SET access_token=?, refresh_token=?, expires_at=?, updated_at=datetime('now')
            WHERE id=?
            """,
            (
                data.get("access_token"),
                refresh_token,
                data.get("expires_at"),
                existing["id"],
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO oauth_tokens
            (account_id, access_token, refresh_token, expires_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                account_id,
                data.get("access_token"),
                refresh_token,
                data.get("expires_at"),
            ),
        )

    conn.commit()
    conn.close()
    return get_token(account_id)


def get_token(account_id):
    conn = _connect()
    row = conn.execute(
        "SELECT id, account_id, access_token, refresh_token, expires_at, created_at, updated_at "
        "FROM oauth_tokens WHERE account_id=? ORDER BY id DESC LIMIT 1",
        (account_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_token(account_id, data):
    return create_token({"account_id": account_id, **data})


def delete_token(account_id):
    conn = _connect()
    conn.execute("DELETE FROM oauth_tokens WHERE account_id=?", (account_id,))
    conn.commit()
    conn.close()
    return {"deleted": True}


def create_oauth_state(account_id, state, provider="youtube", ttl_minutes=10):
    if not state:
        raise ValueError("OAuth state is required")
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=ttl_minutes)

    conn = _connect()
    conn.execute(
        "DELETE FROM oauth_states WHERE expires_at < ?",
        (now.isoformat(),),
    )
    conn.execute(
        """
        INSERT OR REPLACE INTO oauth_states
        (state, account_id, provider, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            state,
            account_id,
            provider,
            expires_at.isoformat(),
            now.isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return state


def consume_oauth_state(account_id, state, provider="youtube"):
    now = datetime.now(timezone.utc)
    conn = _connect()
    row = conn.execute(
        """
        SELECT state, account_id, provider, expires_at
        FROM oauth_states
        WHERE state=? AND account_id=? AND provider=?
        """,
        (state, account_id, provider),
    ).fetchone()

    valid = False
    if row:
        try:
            expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            valid = expires_at >= now
        except (TypeError, ValueError):
            valid = False

    if row:
        conn.execute("DELETE FROM oauth_states WHERE state=?", (state,))
        conn.commit()
    conn.close()
    return valid
