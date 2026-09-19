"""Autonomy controls and human policy overrides.

This module is deliberately a control-plane only.  It computes an effective
authorization state but never approves, materializes, executes, or publishes
anything downstream.
"""
import json
import sqlite3
import re
from datetime import datetime, timezone

from data.database_path import database_path
from intelligence import policy

_ACTOR = "local_operator"
_DECISIONS = {"AUTO", "REVIEW", "BLOCK"}
_HARD_BLOCK_REASONS = {
    "CONTENT_SAFETY_BLOCK",
    "NOVELTY_BLOCK",
    "PLAN_NOT_ACTIONABLE",
    "ACCOUNT_HARD_FAILURE",
    "PLATFORM_HARD_FAILURE",
    "DUPLICATE_BLOCK",
}
def _sanitize_reason(value):
    text=str(value).strip()
    return re.sub(r'(?i)(access_token|refresh_token|authorization|client_secret)\s*[=:]\s*[^\s,;]+', r'\1=[REDACTED]', text)[:500]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _conn():
    conn = sqlite3.connect(database_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS intelligence_autonomy_settings (
            id INTEGER PRIMARY KEY CHECK (id=1),
            autonomy_enabled INTEGER NOT NULL DEFAULT 0,
            kill_switch_active INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS intelligence_policy_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_plan_id INTEGER NOT NULL,
            content_plan_revision INTEGER NOT NULL,
            policy_decision_id INTEGER NOT NULL,
            original_decision TEXT NOT NULL,
            override_decision TEXT NOT NULL,
            reason TEXT NOT NULL,
            actor TEXT NOT NULL,
            created_at TEXT NOT NULL,
            superseded_at TEXT,
            cleared_at TEXT
        )"""
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_policy_override_current "
        "ON intelligence_policy_overrides(content_plan_id, content_plan_revision) "
        "WHERE superseded_at IS NULL AND cleared_at IS NULL"
    )
    conn.commit()
    return conn


def _bool(value, field):
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return int(value)


def _settings_row(row):
    return {
        "id": row["id"],
        "autonomy_enabled": bool(row["autonomy_enabled"]),
        "kill_switch_active": bool(row["kill_switch_active"]),
        "updated_at": row["updated_at"],
    }


def get_autonomy_settings():
    with _conn() as conn:
        row = conn.execute("SELECT * FROM intelligence_autonomy_settings WHERE id=1").fetchone()
        if row is None:
            now = _now()
            conn.execute(
                "INSERT INTO intelligence_autonomy_settings(id,autonomy_enabled,kill_switch_active,updated_at) VALUES(1,0,1,?)",
                (now,),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM intelligence_autonomy_settings WHERE id=1").fetchone()
        return _settings_row(row)


def update_autonomy_settings(*, autonomy_enabled=None, kill_switch_active=None):
    current = get_autonomy_settings()
    enabled = current["autonomy_enabled"] if autonomy_enabled is None else bool(_bool(autonomy_enabled, "autonomy_enabled"))
    kill = current["kill_switch_active"] if kill_switch_active is None else bool(_bool(kill_switch_active, "kill_switch_active"))
    with _conn() as conn:
        conn.execute(
            "UPDATE intelligence_autonomy_settings SET autonomy_enabled=?,kill_switch_active=?,updated_at=? WHERE id=1",
            (int(enabled), int(kill), _now()),
        )
        conn.commit()
    return get_autonomy_settings()


set_autonomy_settings = update_autonomy_settings


def _override_row(row):
    if not row:
        return None
    out = dict(row)
    return out


def get_current_override(plan_id):
    current = policy.get_current_policy_decision(plan_id)
    if not current:
        return None
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM intelligence_policy_overrides WHERE content_plan_id=? AND content_plan_revision=? AND policy_decision_id=? AND superseded_at IS NULL AND cleared_at IS NULL ORDER BY id DESC LIMIT 1",
            (plan_id, current["content_plan_revision"], current["id"]),
        ).fetchone()
        return _override_row(row)


def list_override_history(plan_id):
    with _conn() as conn:
        return [_override_row(row) for row in conn.execute(
            "SELECT * FROM intelligence_policy_overrides WHERE content_plan_id=? ORDER BY id", (plan_id,)
        ).fetchall()]


def _hard_block(raw):
    return raw.get("decision") == "BLOCK" and bool(set(raw.get("reason_codes") or ()) & _HARD_BLOCK_REASONS)


def set_policy_override(plan_id, override_decision, reason, *, actor=None):
    if override_decision not in _DECISIONS:
        raise ValueError("override_decision must be AUTO, REVIEW, or BLOCK")
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 500:
        raise ValueError("reason must be a non-empty string of at most 500 characters")
    if actor not in (None, _ACTOR):
        raise ValueError("actor is server-controlled")
    raw = policy.get_current_policy_decision(plan_id)
    if not raw:
        raise ValueError("current policy decision required")
    if raw["decision"] == "BLOCK" and override_decision != "BLOCK":
        raise ValueError("BLOCK cannot be overridden without a recovery contract")
    with _conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE intelligence_policy_overrides SET superseded_at=? WHERE content_plan_id=? AND content_plan_revision=? AND superseded_at IS NULL AND cleared_at IS NULL",
            (_now(), plan_id, raw["content_plan_revision"]),
        )
        cur = conn.execute(
            "INSERT INTO intelligence_policy_overrides(content_plan_id,content_plan_revision,policy_decision_id,original_decision,override_decision,reason,actor,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (plan_id, raw["content_plan_revision"], raw["id"], raw["decision"], override_decision, _sanitize_reason(reason), _ACTOR, _now()),
        )
        conn.commit()
        return _override_row(conn.execute("SELECT * FROM intelligence_policy_overrides WHERE id=?", (cur.lastrowid,)).fetchone())


create_policy_override = set_policy_override


def clear_policy_override(plan_id, reason, *, actor=None):
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 500:
        raise ValueError("reason must be a non-empty string of at most 500 characters")
    if actor not in (None, _ACTOR):
        raise ValueError("actor is server-controlled")
    raw = policy.get_current_policy_decision(plan_id)
    if not raw:
        raise ValueError("current policy decision required")
    with _conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE intelligence_policy_overrides SET cleared_at=?, superseded_at=? WHERE content_plan_id=? AND content_plan_revision=? AND superseded_at IS NULL AND cleared_at IS NULL",
            (_now(), _now(), plan_id, raw["content_plan_revision"]),
        )
        conn.commit()
    return get_effective_authorization(plan_id)


def get_effective_authorization(plan_id):
    plan = policy.get_current_policy_decision(plan_id)
    settings = get_autonomy_settings()
    override = get_current_override(plan_id) if plan else None
    raw_decision = plan["decision"] if plan else None
    effective = override["override_decision"] if override else raw_decision
    reasons = []
    if not plan:
        reasons.append("POLICY_UNEVALUATED")
    if override:
        reasons.append("HUMAN_OVERRIDE_ACTIVE")
    if settings["kill_switch_active"]:
        reasons.append("KILL_SWITCH_ACTIVE")
    if not settings["autonomy_enabled"]:
        reasons.append("AUTONOMY_DISABLED")
    allowed = bool(plan and effective == "AUTO" and settings["autonomy_enabled"] and not settings["kill_switch_active"])
    return {
        "plan_id": plan_id,
        "current_revision": plan["content_plan_revision"] if plan else None,
        "raw_decision": raw_decision,
        "raw_policy_decision_id": plan["id"] if plan else None,
        "policy_version": plan.get("policy_version") if plan else None,
        "current_override": override,
        "override_id": override["id"] if override else None,
        "effective_decision": effective,
        "autonomy_enabled": settings["autonomy_enabled"],
        "kill_switch_active": settings["kill_switch_active"],
        "autonomous_continuation_allowed": allowed,
        "control_reason_codes": list(dict.fromkeys(reasons)),
    }


effective_authorization = get_effective_authorization
