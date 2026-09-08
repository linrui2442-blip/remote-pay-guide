import gc
import os
import sys
import tempfile
import threading
import time
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
    get_sync_state,
    mark_scheduler_failure,
    mark_scheduler_success,
    renew_scheduler_lease,
    try_claim_scheduler_run,
)
from integrations.sync_scheduler import BackgroundAccountSyncScheduler


ACCOUNT = {"id": 900001, "platform": "youtube", "status": "connected"}
DAY = "2026-09-07"


def scheduler(executor, **kwargs):
    return BackgroundAccountSyncScheduler(
        interval_seconds=5,
        lease_seconds=30,
        heartbeat_seconds=5,
        account_source=lambda: [ACCOUNT],
        sync_executor=executor,
        **kwargs,
    )


def main():
    temp_dir = tempfile.mkdtemp(prefix="rpg-scheduler-heartbeat-")
    original_due = scheduler_module.due_accounts
    try:
        sync_state.DB_PATH = Path(temp_dir) / "scheduler.db"
        ensure_sync_state(ACCOUNT["id"], ACCOUNT["platform"])
        candidate = {"account": ACCOUNT, "daily_date": DAY, "sync_state": {}}
        scheduler_module.due_accounts = lambda **kwargs: [candidate]

        started = threading.Event()
        calls = []

        def long_executor(*args, **kwargs):
            calls.append(time.monotonic())
            started.set()
            time.sleep(40)
            return {"status": "success", "failures": []}

        owner = scheduler(long_executor, owner_id="long-owner")
        result_box = {}
        thread = threading.Thread(
            target=lambda: result_box.setdefault("result", owner.run_once()), daemon=True
        )
        thread.start()
        assert started.wait(5)
        initial = get_sync_state(ACCOUNT["id"], "youtube")
        original_expiry = datetime.fromisoformat(initial["scheduler_lease_expires_at"])
        competitor_results = []
        elapsed = 0
        for checkpoint in (10, 25, 35):
            time.sleep(checkpoint - elapsed)
            elapsed = checkpoint
            competitor_results.append(
                try_claim_scheduler_run(
                    ACCOUNT["id"], "youtube", DAY, "competitor",
                    now=datetime.now(timezone.utc), lease_seconds=30,
                )["claimed"]
            )
        state_during = get_sync_state(ACCOUNT["id"], "youtube")
        assert competitor_results == [False, False, False]
        assert datetime.fromisoformat(state_during["scheduler_lease_expires_at"]) > original_expiry
        assert state_during["scheduler_lease_last_renewed_at"] is not None
        thread.join(12)
        assert not thread.is_alive()
        outcome = result_box["result"]["outcomes"][0]
        assert outcome["status"] == "success"
        assert outcome["heartbeat"]["renewals"] >= 7
        final = get_sync_state(ACCOUNT["id"], "youtube")
        assert len(calls) == 1
        assert final["scheduler_lease_owner"] is None
        assert final["scheduler_last_daily_date"] == DAY
        assert datetime.fromisoformat(final["scheduler_last_success_at"]) > datetime.fromisoformat(final["scheduler_last_attempt_at"])
        assert 39 <= final["scheduler_last_duration_seconds"] <= 45

        # Stale owners cannot renew or finalize after a reclaim.
        next_day = "2026-09-08"
        old_now = datetime.now(timezone.utc)
        assert try_claim_scheduler_run(900001, "youtube", next_day, "old", now=old_now, lease_seconds=30)["claimed"]
        assert try_claim_scheduler_run(900001, "youtube", next_day, "new", now=old_now + timedelta(seconds=31), lease_seconds=30)["claimed"]
        assert renew_scheduler_lease(900001, "youtube", next_day, "old", renewed_at=old_now + timedelta(seconds=32), lease_seconds=30)["reason"] == "lease_lost"
        assert mark_scheduler_success(900001, "youtube", next_day, owner_id="old")["reason"] == "lease_lost"
        assert mark_scheduler_failure(900001, "youtube", "stale", owner_id="old")["reason"] == "lease_lost"
        assert mark_scheduler_success(900001, "youtube", next_day, owner_id="new")["applied"]

        # A heartbeat that observes a replaced owner stops and the old executor
        # cannot persist its eventual success.
        lost_day = "2026-09-09"
        scheduler_module.due_accounts = lambda **kwargs: [{"account": ACCOUNT, "daily_date": lost_day, "sync_state": {}}]
        lost_started = threading.Event()
        def lost_executor(*args, **kwargs):
            lost_started.set()
            time.sleep(6)
            return {"status": "success", "failures": []}
        lost_scheduler = scheduler(lost_executor, owner_id="losing-owner")
        lost_box = {}
        lost_thread = threading.Thread(target=lambda: lost_box.setdefault("result", lost_scheduler.run_once()), daemon=True)
        lost_thread.start(); assert lost_started.wait(3)
        with sync_state._connect() as conn:
            conn.execute("UPDATE platform_sync_state SET scheduler_lease_owner='replacement-owner' WHERE account_id=900001")
            conn.commit()
        lost_thread.join(10); assert not lost_thread.is_alive()
        assert lost_box["result"]["outcomes"][0]["status"] == "lease_lost"
        assert get_sync_state(900001, "youtube")["scheduler_lease_owner"] == "replacement-owner"
        assert mark_scheduler_failure(900001, "youtube", "cleanup", owner_id="replacement-owner", backoff_seconds=(1,))["applied"]
        with sync_state._connect() as conn:
            conn.execute("UPDATE platform_sync_state SET scheduler_next_retry_at=NULL WHERE account_id=900001")
            conn.commit()

        # Real completion timing for a shorter run.
        timing_day = "2026-09-10"
        scheduler_module.due_accounts = lambda **kwargs: [{"account": ACCOUNT, "daily_date": timing_day, "sync_state": {}}]
        timed = scheduler(lambda *a, **k: (time.sleep(2) or {"status": "success", "failures": []}), owner_id="timed")
        timed.run_once()
        timing = get_sync_state(900001, "youtube")
        assert datetime.fromisoformat(timing["scheduler_last_success_at"]) > datetime.fromisoformat(timing["scheduler_last_attempt_at"])
        assert 1.8 <= timing["scheduler_last_duration_seconds"] <= 3.5

        # Deterministic health classifications.
        healthy = scheduler(lambda *a, **k: {}, owner_id="health")
        scheduler_module.due_accounts = lambda **kwargs: []
        assert healthy.status()["health"] == "healthy"
        now = datetime.now(timezone.utc)
        assert try_claim_scheduler_run(900001, "youtube", "2026-09-11", "health", now=now, lease_seconds=30)["claimed"]
        assert healthy.status()["health"] == "running"
        with sync_state._connect() as conn:
            conn.execute("UPDATE platform_sync_state SET scheduler_lease_expires_at=? WHERE account_id=900001", ((datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat(),))
            conn.commit()
        assert healthy.status()["lease_health"] == "at_risk"
        with sync_state._connect() as conn:
            conn.execute("UPDATE platform_sync_state SET scheduler_lease_acquired_at=?, scheduler_lease_expires_at=? WHERE account_id=900001", ((now - timedelta(seconds=100)).isoformat(), (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()))
            conn.commit()
        stuck = scheduler(lambda *a, **k: {}, owner_id="health", stuck_warning_seconds=15)
        assert stuck.status()["health"] == "stuck_suspected"
        assert mark_scheduler_failure(900001, "youtube", "failure", owner_id="health", backoff_seconds=(300,))["applied"]
        assert healthy.status()["health"] == "retrying"
        with sync_state._connect() as conn:
            conn.execute("UPDATE platform_sync_state SET scheduler_next_retry_at=NULL WHERE account_id=900001")
            conn.commit()
        assert healthy.status()["health"] == "degraded"

        failure_day = "2026-09-13"
        scheduler_module.due_accounts = lambda **kwargs: [{"account": ACCOUNT, "daily_date": failure_day, "sync_state": {}}]
        def delayed_failure(*args, **kwargs):
            time.sleep(2)
            raise RuntimeError("timed failure")
        failed_run = scheduler(delayed_failure, owner_id="timed-failure")
        failed_run.run_once()
        failure_timing = get_sync_state(900001, "youtube")
        assert datetime.fromisoformat(failure_timing["scheduler_last_finished_at"]) > datetime.fromisoformat(failure_timing["scheduler_last_attempt_at"])
        assert 1.8 <= failure_timing["scheduler_last_duration_seconds"] <= 3.5
        os.environ["OS_DISABLE_BACKGROUND_ACCOUNT_SYNC"] = "1"
        assert healthy.status()["health"] == "disabled"
        os.environ.pop("OS_DISABLE_BACKGROUND_ACCOUNT_SYNC", None)
    finally:
        scheduler_module.due_accounts = original_due
        os.environ.pop("OS_DISABLE_BACKGROUND_ACCOUNT_SYNC", None)
        gc.collect()

    print("Scheduler long-running lease heartbeat smoke test passed")
    print("ttl=30s; executor=40s; heartbeat=5s; competitor attempts=3; duplicate=0")


if __name__ == "__main__":
    main()
