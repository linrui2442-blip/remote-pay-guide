from data.database_path import database_path
import sqlite3

def _conn():
    conn = sqlite3.connect(database_path()); conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS account_platform_bindings (account_id INTEGER PRIMARY KEY, platform TEXT NOT NULL, page_id TEXT NOT NULL, instagram_user_id TEXT, external_display_name TEXT, external_username TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit(); return conn

def get_binding(account_id):
    conn=_conn(); row=conn.execute("SELECT account_id,platform,page_id,instagram_user_id,external_display_name,external_username,created_at,updated_at FROM account_platform_bindings WHERE account_id=?",(account_id,)).fetchone(); conn.close(); return dict(row) if row else None

def save_binding(account_id, platform, page_id, instagram_user_id=None, external_display_name=None, external_username=None):
    if platform == "instagram" and not instagram_user_id: raise ValueError("instagram_user_id is required")
    conn=_conn(); conn.execute("INSERT INTO account_platform_bindings(account_id,platform,page_id,instagram_user_id,external_display_name,external_username) VALUES(?,?,?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET platform=excluded.platform,page_id=excluded.page_id,instagram_user_id=excluded.instagram_user_id,external_display_name=excluded.external_display_name,external_username=excluded.external_username,updated_at=CURRENT_TIMESTAMP",(account_id,platform,page_id,instagram_user_id,external_display_name,external_username)); conn.commit(); row=conn.execute("SELECT account_id,platform,page_id,instagram_user_id,external_display_name,external_username,created_at,updated_at FROM account_platform_bindings WHERE account_id=?",(account_id,)).fetchone(); conn.close(); return dict(row)
