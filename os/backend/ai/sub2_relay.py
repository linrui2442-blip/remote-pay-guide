"""Durable, localhost-only adapter from canonical G4-C to Sub2 video tasks."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests

from data.database_path import database_path
from integrations.github.client import GitHubClient
from production.providers.github_monitor import GitHubRunMonitor


WORKFLOW = "promote-local-g4c-video.yml"
REQUEST_RE = re.compile(r"^g4c-runtime-job-[1-9][0-9]{0,18}$")
FILE_RE = re.compile(r"^[A-Za-z0-9._-]+\.mp4$")
ACTIVE = {"INTENT", "DISPATCH_UNKNOWN", "SUBMITTED", "RUNNING", "CONTENT_READY",
          "STAGED", "GITHUB_INTENT", "GITHUB_SUBMITTED", "GITHUB_RUNNING"}
TERMINAL = {"COMPLETED", "FAILED"}
SAFE_ERRORS = {
    "CONFIGURATION_REQUIRED", "REQUEST_DRIFT", "UNSUPPORTED_REQUEST", "SUB2_REJECTED",
    "SUB2_TASK_FAILED", "SUB2_TASK_MISSING", "SUB2_STATUS_UNAVAILABLE", "CONTENT_NOT_READY",
    "INVALID_CONTENT", "CONTENT_TOO_LARGE", "STAGING_FAILED", "GITHUB_FAILED",
    "GITHUB_DISPATCH_UNKNOWN", "PUBLIC_ASSET_UNAVAILABLE",
}
_locks_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _lock(request_id):
    with _locks_guard:
        return _locks.setdefault(request_id, threading.Lock())


def _connect():
    conn = sqlite3.connect(database_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS g4c_sub2_relay_requests (
                request_id TEXT PRIMARY KEY,
                request_fingerprint TEXT NOT NULL,
                content_id TEXT,
                state TEXT NOT NULL,
                sub2_task_id TEXT,
                sub2_model TEXT NOT NULL,
                video_sha256 TEXT,
                video_size INTEGER,
                staged_filename TEXT,
                github_ingest_run_id TEXT,
                github_pre_run_ids TEXT,
                github_dispatched_at TEXT,
                public_asset_url TEXT,
                safe_error_code TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def _config():
    base = (os.getenv("SUB2_VIDEO_BASE_URL") or "").strip().rstrip("/")
    model = (os.getenv("SUB2_VIDEO_MODEL") or "").strip()
    sub2_key = os.getenv("SUB2_VIDEO_API_KEY") or ""
    relay_key = os.getenv("G4C_SUB2_RELAY_API_KEY") or ""
    root = (os.getenv("G4C_SUB2_STAGING_ROOT") or "").strip()
    try:
        limit = int(os.getenv("G4C_SUB2_MAX_VIDEO_BYTES") or 100 * 1024 * 1024)
    except ValueError:
        limit = 0
    parsed = urlsplit(base)
    if (not relay_key or not sub2_key or not model or not root or limit <= 0
            or parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise RuntimeError("CONFIGURATION_REQUIRED")
    return {"base": base, "model": model, "sub2_key": sub2_key,
            "relay_key": relay_key, "root": Path(root).resolve(), "limit": limit}


def relay_key_matches(value):
    import hmac
    expected = os.getenv("G4C_SUB2_RELAY_API_KEY") or ""
    return bool(expected) and hmac.compare_digest(value or "", expected)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint(payload):
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _row(request_id):
    init_db()
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM g4c_sub2_relay_requests WHERE request_id=?",
                           (request_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _update(request_id, state, **values):
    if state not in ACTIVE | TERMINAL:
        raise ValueError("invalid relay state")
    if values.get("safe_error_code") and values["safe_error_code"] not in SAFE_ERRORS:
        raise ValueError("unsafe relay error")
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute("SELECT state FROM g4c_sub2_relay_requests WHERE request_id=?",
                               (request_id,)).fetchone()
        if not current:
            raise ValueError("relay request missing")
        if current["state"] in TERMINAL and current["state"] != state:
            raise ValueError("terminal relay state is immutable")
        fields = {"state": state, "updated_at": _now(), **values}
        sql = ",".join(f"{name}=?" for name in fields)
        conn.execute(f"UPDATE g4c_sub2_relay_requests SET {sql} WHERE request_id=?",
                     (*fields.values(), request_id))
        conn.commit()
    finally:
        conn.close()
    return _row(request_id)


def _response(row):
    state = row["state"]
    result = {"status": "running", "job_id": row["request_id"],
              "provider_constraints": {"aspect_ratio": "not_enforced_by_sub2"}}
    if state == "SUBMITTED":
        result["status"] = "submitted"
    elif state == "COMPLETED":
        return {"status": "completed", "job_id": row["request_id"],
                "asset_url": row["public_asset_url"],
                "provider_constraints": {"aspect_ratio": "not_enforced_by_sub2"}}
    elif state == "FAILED":
        return {"status": "failed", "job_id": row["request_id"],
                "error": row["safe_error_code"] or "SUB2_TASK_FAILED",
                "provider_constraints": {"aspect_ratio": "not_enforced_by_sub2"}}
    result["status_url"] = f"/internal/g4c/sub2/videos/{row['request_id']}"
    if state in {"DISPATCH_UNKNOWN", "GITHUB_INTENT"}:
        result["manual_reconciliation_required"] = True
    return result


class Sub2RelayService:
    def __init__(self, session=None, github=None, monitor=None, public_verifier=None):
        self.http = session or requests.Session()
        self.github = github or GitHubClient()
        self.monitor = monitor or GitHubRunMonitor(self.github)
        self.public_verifier = public_verifier

    @staticmethod
    def _headers(config):
        return {"Authorization": f"Bearer {config['sub2_key']}",
                "Accept": "application/json", "Content-Type": "application/json"}

    def create(self, request_id, payload):
        config = _config()
        if not REQUEST_RE.fullmatch(request_id or ""):
            raise ValueError("invalid Idempotency-Key")
        if not isinstance(payload, dict) or payload.get("task_type") != "video_generation":
            raise ValueError("unsupported canonical request")
        if payload.get("model") not in {None, "", "auto"}:
            raise ValueError("unsupported canonical model")
        if not isinstance(payload.get("prompt"), str) or not payload["prompt"].strip():
            raise ValueError("prompt is required")
        options = payload.get("options") or {}
        if not isinstance(options, dict) or set(options) - {"aspect_ratio"}:
            raise ValueError("unsupported canonical options")
        if options.get("aspect_ratio") not in (None, "9:16"):
            raise ValueError("unsupported canonical aspect ratio")
        request_input = payload.get("input") or {}
        allowed_input = {"content_id", "topic", "script", "visual_direction", "title", "description"}
        if (not isinstance(request_input, dict) or set(request_input) - allowed_input
                or len(_canonical(request_input).encode("utf-8")) > 16384
                or any(value is not None and not isinstance(value, str) for value in request_input.values())):
            raise ValueError("unsupported canonical input")
        content_id = str(request_input.get("content_id") or "")[:256]
        fingerprint = _fingerprint(payload)
        with _lock(request_id):
            init_db()
            conn = _connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                existing = conn.execute(
                    "SELECT * FROM g4c_sub2_relay_requests WHERE request_id=?", (request_id,)
                ).fetchone()
                if existing:
                    conn.commit()
                    if existing["request_fingerprint"] != fingerprint:
                        raise ValueError("REQUEST_DRIFT")
                    return _response(dict(existing))
                now = _now()
                conn.execute("""INSERT INTO g4c_sub2_relay_requests
                    (request_id,request_fingerprint,content_id,state,sub2_model,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?)""",
                    (request_id, fingerprint, content_id, "INTENT", config["model"], now, now))
                # Crossing the POST boundary from this state is intentionally non-replayable.
                conn.execute("UPDATE g4c_sub2_relay_requests SET state='DISPATCH_UNKNOWN' WHERE request_id=?",
                             (request_id,))
                conn.commit()
            finally:
                conn.close()
            try:
                response = self.http.post(
                    config["base"] + "/v1/videos",
                    json={"model": config["model"], "prompt": payload["prompt"]},
                    headers=self._headers(config), timeout=120, allow_redirects=False,
                )
            except requests.RequestException:
                return _response(_row(request_id))
            if response.status_code != 202:
                return _response(_update(request_id, "FAILED", safe_error_code="SUB2_REJECTED"))
            try:
                data = response.json()
            except ValueError:
                return _response(_row(request_id))
            task_id = data.get("id") if isinstance(data, dict) else None
            if not isinstance(task_id, str) or not task_id.startswith("video_") or len(task_id) > 256:
                return _response(_row(request_id))
            mapped = "RUNNING" if data.get("status") == "processing" else "SUBMITTED"
            return _response(_update(request_id, mapped, sub2_task_id=task_id))

    def status(self, request_id):
        if not REQUEST_RE.fullmatch(request_id or ""):
            raise ValueError("invalid request id")
        with _lock(request_id):
            row = _row(request_id)
            if not row:
                raise KeyError(request_id)
            if row["state"] in TERMINAL | {"DISPATCH_UNKNOWN"}:
                return _response(row)
            if row["state"] == "GITHUB_INTENT":
                return self._discover_after_ambiguous(row)
            if row["state"] in {"SUBMITTED", "RUNNING"}:
                return self._poll_sub2(row)
            if row["state"] in {"CONTENT_READY", "STAGED"}:
                return self._dispatch_github(row)
            if row["state"] in {"GITHUB_SUBMITTED", "GITHUB_RUNNING"}:
                return self._poll_github(row)
            return _response(row)

    def _poll_sub2(self, row):
        config = _config()
        try:
            response = self.http.get(
                config["base"] + "/v1/videos/" + row["sub2_task_id"],
                headers=self._headers(config), timeout=30, allow_redirects=False,
            )
        except requests.RequestException:
            return _response(row)
        if response.status_code == 404:
            return _response(_update(row["request_id"], "DISPATCH_UNKNOWN",
                                     safe_error_code="SUB2_TASK_MISSING"))
        if response.status_code != 200:
            return _response(row)
        try:
            data = response.json()
        except ValueError:
            return _response(row)
        state = data.get("status")
        if state == "queued":
            return _response(_update(row["request_id"], "SUBMITTED"))
        if state == "processing":
            return _response(_update(row["request_id"], "RUNNING"))
        if state == "failed":
            return _response(_update(row["request_id"], "FAILED", safe_error_code="SUB2_TASK_FAILED"))
        if state != "completed":
            return _response(row)
        return self._retrieve_content(_update(row["request_id"], "CONTENT_READY"), config)

    def _stage_path(self, config, request_id, filename):
        if not REQUEST_RE.fullmatch(request_id) or not FILE_RE.fullmatch(filename):
            raise ValueError("invalid staging identity")
        root = config["root"]
        directory = (root / request_id).resolve()
        path = (directory / filename).resolve()
        if root not in directory.parents and directory != root:
            raise ValueError("staging path escapes root")
        if directory not in path.parents or path.is_symlink():
            raise ValueError("staging path escapes request directory")
        return directory, path

    def _retrieve_content(self, row, config):
        try:
            response = self.http.get(
                config["base"] + "/v1/videos/" + row["sub2_task_id"] + "/content",
                headers=self._headers(config), timeout=120, allow_redirects=False, stream=True,
            )
        except requests.RequestException:
            return _response(row)
        if response.status_code == 202:
            return _response(_update(row["request_id"], "RUNNING"))
        mime = (response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
        if response.status_code != 200 or not mime.startswith("video/"):
            return _response(_update(row["request_id"], "FAILED", safe_error_code="INVALID_CONTENT"))
        filename = f"{row['request_id']}.mp4"
        try:
            directory, path = self._stage_path(config, row["request_id"], filename)
            directory.mkdir(parents=True, exist_ok=True)
            if path.exists():
                raise ValueError("staging collision")
            temporary = path.with_suffix(".tmp")
            digest, size = hashlib.sha256(), 0
            with open(temporary, "xb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > config["limit"]:
                        raise OverflowError("content limit")
                    digest.update(chunk)
                    output.write(chunk)
            if size == 0:
                raise ValueError("empty content")
            temporary.replace(path)
        except OverflowError:
            if 'temporary' in locals() and temporary.exists(): temporary.unlink()
            return _response(_update(row["request_id"], "FAILED", safe_error_code="CONTENT_TOO_LARGE"))
        except (OSError, ValueError):
            if 'temporary' in locals() and temporary.exists(): temporary.unlink()
            return _response(_update(row["request_id"], "FAILED", safe_error_code="STAGING_FAILED"))
        staged = _update(row["request_id"], "STAGED", video_sha256=digest.hexdigest(),
                         video_size=size, staged_filename=filename)
        return self._dispatch_github(staged)

    def _dispatch_github(self, row):
        if row["state"] == "CONTENT_READY":
            return _response(row)
        pre_ids = sorted(self.monitor.snapshot_run_ids(WORKFLOW, "main"))
        submitted = _now()
        intent = _update(row["request_id"], "GITHUB_INTENT",
                         github_pre_run_ids=json.dumps(pre_ids), github_dispatched_at=submitted)
        try:
            self.github.trigger_workflow(WORKFLOW, "main", inputs={
                "request_id": row["request_id"], "asset_filename": row["staged_filename"],
                "expected_sha256": row["video_sha256"],
            })
        except requests.RequestException:
            return self._discover_after_ambiguous(intent)
        try:
            run = self.monitor.discover_run(WORKFLOW, "main", pre_ids, submitted,
                                            max_attempts=1, poll_interval=0)
        except (TimeoutError, RuntimeError):
            return _response(intent)
        return _response(_update(row["request_id"], "GITHUB_SUBMITTED",
                                 github_ingest_run_id=str(run["id"])))

    def _discover_after_ambiguous(self, row):
        try:
            run = self.monitor.discover_run(
                WORKFLOW, "main", json.loads(row["github_pre_run_ids"]),
                row["github_dispatched_at"], max_attempts=1, poll_interval=0)
        except (TimeoutError, RuntimeError):
            return _response(row)
        return _response(_update(row["request_id"], "GITHUB_SUBMITTED",
                                 github_ingest_run_id=str(run["id"])))

    def _poll_github(self, row):
        run = self.github.get_workflow_run(int(row["github_ingest_run_id"]))
        if run.get("status") != "completed":
            return _response(_update(row["request_id"], "GITHUB_RUNNING"))
        if run.get("conclusion") != "success":
            return _response(_update(row["request_id"], "FAILED", safe_error_code="GITHUB_FAILED"))
        url = f"https://{self.github.owner}.github.io/{self.github.repo}/media/{row['staged_filename']}"
        if self.public_verifier and not self.public_verifier(url):
            return _response(_update(row["request_id"], "FAILED",
                                     safe_error_code="PUBLIC_ASSET_UNAVAILABLE"))
        return _response(_update(row["request_id"], "COMPLETED", public_asset_url=url))
