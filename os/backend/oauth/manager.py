from data.database_path import database_path
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = database_path()


def _connect():
    database_path().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS oauth_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            provider TEXT,
            access_token TEXT,
            refresh_token TEXT,
            expires_at TEXT,
            scopes TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    token_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(oauth_tokens)").fetchall()
    }
    if "provider" not in token_columns:
        conn.execute("ALTER TABLE oauth_tokens ADD COLUMN provider TEXT")
    if "scopes" not in token_columns:
        conn.execute("ALTER TABLE oauth_tokens ADD COLUMN scopes TEXT")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS oauth_states (
            state TEXT PRIMARY KEY,
            account_id INTEGER,
            provider TEXT,
            scope_profile TEXT,
            code_verifier TEXT,
            expires_at TEXT,
            created_at TEXT
        )
        """
    )
    state_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(oauth_states)").fetchall()
    }
    if "scope_profile" not in state_columns:
        conn.execute("ALTER TABLE oauth_states ADD COLUMN scope_profile TEXT")
    if "code_verifier" not in state_columns:
        conn.execute("ALTER TABLE oauth_states ADD COLUMN code_verifier TEXT")

    conn.commit()
    return conn


def _normalize_scopes(value):
    if value is None:
        return None
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            if isinstance(decoded, list):
                return json.dumps(sorted(set(decoded)))
        except (TypeError, ValueError, json.JSONDecodeError):
            return json.dumps([value])
    return json.dumps(sorted(set(value)))


def _serialize_token(row):
    if not row:
        return None
    data = dict(row)
    raw_scopes = data.get("scopes")
    if raw_scopes:
        try:
            data["scopes"] = json.loads(raw_scopes)
        except (TypeError, ValueError, json.JSONDecodeError):
            data["scopes"] = [raw_scopes]
    else:
        data["scopes"] = []
    return data


def create_token(data):
    """Create or update the credential record for one account."""
    account_id = data.get("account_id")
    if account_id is None:
        raise ValueError("account_id is required")

    conn = _connect()
    existing = conn.execute(
        "SELECT id, refresh_token, provider, scopes FROM oauth_tokens "
        "WHERE account_id=? ORDER BY id DESC LIMIT 1",
        (account_id,),
    ).fetchone()

    refresh_token = data.get("refresh_token")
    if existing and not refresh_token:
        refresh_token = existing["refresh_token"]

    provider = data.get("provider") or (existing["provider"] if existing else None)
    scopes = data.get("scopes")
    if scopes is None and existing:
        scopes_json = existing["scopes"]
    else:
        scopes_json = _normalize_scopes(scopes)

    if existing:
        conn.execute(
            """
            UPDATE oauth_tokens
            SET provider=?, access_token=?, refresh_token=?, expires_at=?, scopes=?,
                updated_at=datetime('now')
            WHERE id=?
            """,
            (
                provider,
                data.get("access_token"),
                refresh_token,
                data.get("expires_at"),
                scopes_json,
                existing["id"],
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO oauth_tokens
            (account_id, provider, access_token, refresh_token, expires_at, scopes,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                account_id,
                provider,
                data.get("access_token"),
                refresh_token,
                data.get("expires_at"),
                scopes_json,
            ),
        )

    conn.commit()
    conn.close()
    return get_token(account_id)


def get_token(account_id):
    conn = _connect()
    row = conn.execute(
        "SELECT id, account_id, provider, access_token, refresh_token, expires_at, scopes, "
        "created_at, updated_at FROM oauth_tokens "
        "WHERE account_id=? ORDER BY id DESC LIMIT 1",
        (account_id,),
    ).fetchone()
    conn.close()
    return _serialize_token(row)


def update_token(account_id, data):
    return create_token({"account_id": account_id, **data})


def delete_token(account_id):
    conn = _connect()
    conn.execute("DELETE FROM oauth_tokens WHERE account_id=?", (account_id,))
    conn.commit()
    conn.close()
    return {"deleted": True}


def create_oauth_state(
    account_id,
    state,
    provider="youtube",
    ttl_minutes=10,
    scope_profile="publish",
    code_verifier=None,
):
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
        (state, account_id, provider, scope_profile, code_verifier, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            state,
            account_id,
            provider,
            scope_profile,
            code_verifier,
            expires_at.isoformat(),
            now.isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return state


def _state_record_if_valid(row, now):
    if not row:
        return None
    try:
        expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return dict(row) if expires_at >= now else None


def consume_oauth_state(
    account_id,
    state,
    provider="youtube",
    *,
    return_record=False,
):
    now = datetime.now(timezone.utc)
    conn = _connect()
    row = conn.execute(
        """
        SELECT state, account_id, provider, scope_profile, code_verifier, expires_at
        FROM oauth_states
        WHERE state=? AND account_id=? AND provider=?
        """,
        (state, account_id, provider),
    ).fetchone()

    record = _state_record_if_valid(row, now)
    if row:
        conn.execute("DELETE FROM oauth_states WHERE state=?", (state,))
        conn.commit()
    conn.close()

    if return_record:
        return record
    return bool(record)


def consume_oauth_state_by_state(state, provider="youtube", expected_scope_profile=None):
    """Resolve account/scope/PKCE metadata from the opaque one-time state."""
    if not state:
        return None

    now = datetime.now(timezone.utc)
    conn = _connect()
    row = conn.execute(
        """
        SELECT state, account_id, provider, scope_profile, code_verifier, expires_at
        FROM oauth_states
        WHERE state=? AND provider=?
        """,
        (state, provider),
    ).fetchone()

    record = _state_record_if_valid(row, now)
    if record and expected_scope_profile:
        expected = {str(item).strip().lower() for item in (expected_scope_profile if isinstance(expected_scope_profile, (list, tuple, set)) else [expected_scope_profile])}
        actual = str(record.get("scope_profile") or "").strip().lower()
        if actual not in expected:
            conn.close()
            return None
    if row:
        conn.execute("DELETE FROM oauth_states WHERE state=?", (state,))
        conn.commit()
    conn.close()
    return record
