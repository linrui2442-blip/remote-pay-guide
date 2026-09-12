import gc
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "os" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

import data.sync_state as sync_state
import integrations.sync_scheduler as scheduler_module
from data.sync_state import (
    ensure_sync_state,
    list_runtime_health_events,
    list_runtime_operation_history,
    mark_scheduler_failure,
    mark_scheduler_success,
    renew_scheduler_lease,
    sanitize_operational_error,
    try_claim_scheduler_run,
)
from integrations.sync_scheduler import BackgroundAccountSyncScheduler
from routers.accounts import scheduler_events, scheduler_history


def _configure(db_path):
    sync_state.DB_PATH = Path(db_path)


def _scheduler(account, owner, executor, *, lease=30, heartbeat=5):
    return BackgroundAccountSyncScheduler(
        interval_seconds=5, lease_seconds=lease, heartbeat_seconds=heartbeat,
        owner_id=owner, account_source=lambda: [account], sync_executor=executor,
    )


def worker(db_path, account_id, day, owner, gate_path, output_path, sleep_seconds=1):
    _configure(db_path)
    account = {"id": int(account_id), "platform": "youtube", "status": "connected"}
    ensure_sync_state(account["id"], "youtube")
    original_due = scheduler_module.due_accounts
    scheduler_module.due_accounts = lambda **kwargs: [
        {"account": account, "daily_date": day, "sync_state": {}}
    ]
    try:
        deadline = time.time() + 15
        while not Path(gate_path).exists() and time.time() < deadline:
            time.sleep(0.02)

        def execute(*args, **kwargs):
            with open(str(output_path) + ".executions", "a", encoding="utf-8") as handle:
                handle.write(owner + "\n")
            time.sleep(float(sleep_seconds))
            return {"status": "success", "failures": []}

        result = _scheduler(account, owner, execute).run_once()
        Path(output_path).write_text(json.dumps(result), encoding="utf-8")
    finally:
        scheduler_module.due_accounts = original_due


def reader(db_path, output_path):
    _configure(db_path)
    payload = {
        "runs": list_runtime_operation_history(limit=200),
        "events": list_runtime_health_events(limit=200),
    }
    Path(output_path).write_text(json.dumps(payload), encoding="utf-8")


def _launch(*args):
    return subprocess.Popen([sys.executable, str(Path(__file__).resolve()), *map(str, args)])


def parent():
    temp_dir = Path(tempfile.mkdtemp(prefix="rpg-runtime-history-"))
    db_path = temp_dir / "history.db"
    _configure(db_path)
    try:
        # Terminal states remain durable, use sanitized errors, and are readable after restart.
        base = datetime.now(timezone.utc)
        for account_id, status in ((1, "success"), (2, "failed"), (3, "partial")):
            ensure_sync_state(account_id, "youtube")
            claim = try_claim_scheduler_run(
                account_id, "youtube", f"2026-09-0{account_id}", f"owner-{account_id}",
                now=base + timedelta(seconds=account_id), lease_seconds=30,
            )
            assert claim["claimed"] and claim["run_id"]
            if status == "success":
                assert mark_scheduler_success(
                    account_id, "youtube", "2026-09-01", owner_id=f"owner-{account_id}",
                    succeeded_at=(base + timedelta(seconds=4)).isoformat(), duration_seconds=3,
                )["applied"]
            else:
                secret_error = (
                    "request failed?access_token=top-secret "
                    "Authorization: Bearer bearer-secret client_secret=client-secret"
                )
                assert mark_scheduler_failure(
                    account_id, "youtube", secret_error, owner_id=f"owner-{account_id}",
                    failed_at=(base + timedelta(seconds=5 + account_id)).isoformat(),
                    status=status, duration_seconds=4, backoff_seconds=(30,),
                )["applied"]
        rows = list_runtime_operation_history(limit=20)
        assert {row["status"] for row in rows} == {"success", "failed", "partial"}
        assert all("top-secret" not in (row["sanitized_error"] or "") for row in rows)
        assert len(scheduler_history(limit=2)["items"]) == 2
        assert scheduler_events(limit=2)["items"]
        sanitized = sanitize_operational_error(
            "https://x.test?a=1&refresh_token=refresh-value client_secret=client-value"
        )
        assert "refresh-value" not in sanitized and "client-value" not in sanitized

        # Row caps retain active runs and newest terminal/event records.
        retention_db = temp_dir / "retention.db"
        _configure(retention_db)
        ensure_sync_state(99, "youtube")
        os.environ["RUNTIME_HISTORY_MAX_ROWS"] = "100"
        os.environ["RUNTIME_HEALTH_EVENTS_MAX_ROWS"] = "100"
        with sync_state._connect() as conn:
            for index in range(105):
                stamp = (base + timedelta(seconds=index)).isoformat()
                conn.execute(
                    "INSERT INTO runtime_operation_history "
                    "(run_id,component,operation_type,status,started_at,finished_at,created_at,updated_at) "
                    "VALUES (?,?,?,'success',?,?,?,?)",
                    (f"terminal-{index}", sync_state.RUNTIME_COMPONENT,
                     sync_state.RUNTIME_OPERATION, stamp, stamp, stamp, stamp),
                )
                conn.execute(
                    "INSERT INTO runtime_health_events "
                    "(component,event_type,health_state,severity,observed_at) "
                    "VALUES (?,'test','healthy','info',?)",
                    (sync_state.RUNTIME_COMPONENT, stamp),
                )
            conn.execute(
                "INSERT INTO runtime_operation_history "
                "(run_id,component,operation_type,status,started_at,created_at,updated_at) "
                "VALUES ('active-retained',?,?,'running',?,?,?)",
                (sync_state.RUNTIME_COMPONENT, sync_state.RUNTIME_OPERATION,
                 base.isoformat(), base.isoformat(), base.isoformat()),
            )
            sync_state._prune_runtime_history(conn, (base + timedelta(seconds=200)).isoformat())
            conn.commit()
            assert conn.execute("SELECT COUNT(*) FROM runtime_operation_history").fetchone()[0] == 101
            assert conn.execute(
                "SELECT COUNT(*) FROM runtime_operation_history WHERE run_id='active-retained'"
            ).fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM runtime_health_events").fetchone()[0] == 100
        os.environ.pop("RUNTIME_HISTORY_MAX_ROWS", None)
        os.environ.pop("RUNTIME_HEALTH_EVENTS_MAX_ROWS", None)

        _configure(db_path)

        restart_output = temp_dir / "restart.json"
        restarted = _launch("--read", db_path, restart_output)
        assert restarted.wait(20) == 0
        restart_payload = json.loads(restart_output.read_text(encoding="utf-8"))
        assert len(restart_payload["runs"]) == 3
        assert restart_payload["events"]

        # Two independent Python processes compete; loser creates no run row.
        competition_db = temp_dir / "competition.db"
        _configure(competition_db)
        ensure_sync_state(10, "youtube")
        gate = temp_dir / "competition.go"
        out_a = temp_dir / "competition-a.json"
        out_b = temp_dir / "competition-b.json"
        process_a = _launch("--worker", competition_db, 10, "2026-09-07", "process-a", gate, out_a, 2)
        process_b = _launch("--worker", competition_db, 10, "2026-09-07", "process-b", gate, out_b, 2)
        time.sleep(0.5)
        gate.touch()
        assert process_a.wait(20) == 0 and process_b.wait(20) == 0
        _configure(competition_db)
        competition_rows = list_runtime_operation_history(limit=20)
        assert len(competition_rows) == 1
        assert competition_rows[0]["status"] == "success"

        # Real crash: heartbeat extends the lease; a second process reclaims only after expiry.
        crash_db = temp_dir / "crash.db"
        _configure(crash_db)
        ensure_sync_state(20, "youtube")
        crash_gate = temp_dir / "crash.go"
        crash_out = temp_dir / "crash-a.json"
        crash_a = _launch("--worker", crash_db, 20, "2026-09-07", "crashed-owner", crash_gate, crash_out, 90)
        crash_gate.touch()
        execution_file = Path(str(crash_out) + ".executions")
        deadline = time.time() + 10
        while not execution_file.exists() and time.time() < deadline:
            time.sleep(0.05)
        assert execution_file.exists()
        time.sleep(6)
        crash_a.kill()
        crash_a.wait(10)
        _configure(crash_db)
        old_run = list_runtime_operation_history(limit=10)[0]
        assert old_run["status"] == "running"
        assert old_run["last_heartbeat_at"] > old_run["started_at"]
        assert not try_claim_scheduler_run(
            20, "youtube", "2026-09-07", "too-early",
            now=datetime.now(timezone.utc), lease_seconds=30,
        )["claimed"]
        state = sync_state.get_sync_state(20, "youtube")
        expiry = datetime.fromisoformat(state["scheduler_lease_expires_at"])
        wait_seconds = max(0, (expiry - datetime.now(timezone.utc)).total_seconds()) + 0.5
        time.sleep(wait_seconds)
        reclaim_gate = temp_dir / "reclaim.go"
        reclaim_gate.touch()
        reclaim_out = temp_dir / "reclaim-b.json"
        crash_b = _launch("--worker", crash_db, 20, "2026-09-07", "recovery-owner", reclaim_gate, reclaim_out, 1)
        assert crash_b.wait(20) == 0
        _configure(crash_db)
        crash_rows = list_runtime_operation_history(limit=10)
        assert len(crash_rows) == 2
        recovered = next(row for row in crash_rows if row["status"] == "success")
        expired = next(row for row in crash_rows if row["status"] == "lease_expired")
        assert recovered["recovery_of_run_id"] == expired["run_id"]
        assert renew_scheduler_lease(20, "youtube", "2026-09-07", "crashed-owner")["reason"] == "lease_lost"
        assert mark_scheduler_success(20, "youtube", "2026-09-07", owner_id="crashed-owner")["reason"] == "lease_lost"
        assert mark_scheduler_failure(20, "youtube", "stale", owner_id="crashed-owner")["reason"] == "lease_lost"
        crash_rows_after = list_runtime_operation_history(limit=10)
        assert [(row["run_id"], row["status"]) for row in crash_rows_after] == [
            (recovered["run_id"], "success"), (expired["run_id"], "lease_expired")
        ]
        event_types = [row["event_type"] for row in list_runtime_health_events(limit=20)]
        assert event_types.count("lease_expired") == 1
        assert event_types.count("lease_reclaimed") == 1
        assert event_types.count("run_succeeded") == 1

        print("Scheduler runtime history smoke test passed")
        print("terminal=3; restart=persistent; competition=1/1; crash=lineage; stale-owner=blocked")
    finally:
        os.environ.pop("RUNTIME_HISTORY_MAX_ROWS", None)
        os.environ.pop("RUNTIME_HEALTH_EVENTS_MAX_ROWS", None)
        gc.collect()
        for path in sorted(temp_dir.glob("*"), reverse=True):
            try:
                path.unlink(missing_ok=True)
            except PermissionError:
                pass
        try:
            temp_dir.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker(*sys.argv[2:])
    elif len(sys.argv) > 1 and sys.argv[1] == "--read":
        reader(*sys.argv[2:])
    else:
        parent()
