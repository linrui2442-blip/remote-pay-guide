import os
import gc
import sys
import tempfile
import time
import threading
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
    get_scheduler_persistent_summary,
    get_sync_state,
    mark_scheduler_failure,
    mark_scheduler_success,
    try_claim_scheduler_run,
)
from integrations.sync_scheduler import BackgroundAccountSyncScheduler


NOW = datetime(2026, 9, 8, 3, 0, tzinfo=timezone.utc)
DAY = "2026-09-06"
ACCOUNT = {"id": 1, "platform": "youtube", "status": "connected"}


class CountingExecutor:
    def __init__(self):
        self.calls = 0
        self.lock = threading.Lock()

    def __call__(self, account_id, platform, **kwargs):
        with self.lock:
            self.calls += 1
        return {"status": "success", "failures": []}


def main():
    temp_dir = tempfile.mkdtemp(prefix="rpg-scheduler-lease-")
    try:
        sync_state.DB_PATH = Path(temp_dir) / "scheduler.db"
        ensure_sync_state(1, "youtube")

        # Force both scheduler instances to discover the same stale candidate;
        # the SQLite claim, not candidate discovery, must select the winner.
        candidate = {"account": ACCOUNT, "daily_date": DAY, "sync_state": {}}
        original_due_accounts = scheduler_module.due_accounts
        scheduler_module.due_accounts = lambda **kwargs: [candidate]
        executor = CountingExecutor()
        schedulers = [
            BackgroundAccountSyncScheduler(
                interval_seconds=5,
                lease_seconds=60,
                owner_id=f"process-{index}",
                account_source=lambda: [ACCOUNT],
                sync_executor=executor,
                clock=lambda: NOW,
            )
            for index in ("a", "b")
        ]
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda item: item.run_once(), schedulers))
        finally:
            scheduler_module.due_accounts = original_due_accounts

        statuses = [item["status"] for result in results for item in result["outcomes"]]
        assert statuses.count("success") == 1, statuses
        assert statuses.count("not_claimed") == 1, statuses
        assert executor.calls == 1

        # Lease expiry permits recovery, while the stale owner cannot finalize.
        recovery_day = "2026-09-07"
        first = try_claim_scheduler_run(
            1, "youtube", recovery_day, "owner-a", now=NOW, lease_seconds=60
        )
        assert first["claimed"] is True
        blocked = try_claim_scheduler_run(
            1,
            "youtube",
            recovery_day,
            "owner-b",
            now=NOW + timedelta(seconds=59),
            lease_seconds=60,
        )
        assert blocked["claimed"] is False
        reclaimed = try_claim_scheduler_run(
            1,
            "youtube",
            recovery_day,
            "owner-b",
            now=NOW + timedelta(seconds=61),
            lease_seconds=60,
        )
        assert reclaimed["claimed"] is True
        stale = mark_scheduler_success(
            1,
            "youtube",
            recovery_day,
            owner_id="owner-a",
            succeeded_at=(NOW + timedelta(seconds=62)).isoformat(),
        )
        assert stale["applied"] is False
        assert stale["reason"] == "lease_lost"
        assert stale["sync_state"]["scheduler_lease_owner"] == "owner-b"
        released = mark_scheduler_success(
            1,
            "youtube",
            recovery_day,
            owner_id="owner-b",
            succeeded_at=(NOW + timedelta(seconds=63)).isoformat(),
        )
        assert released["applied"] is True
        assert released["sync_state"]["scheduler_lease_owner"] is None
        same_day = try_claim_scheduler_run(
            1,
            "youtube",
            recovery_day,
            "owner-c",
            now=NOW + timedelta(seconds=64),
            lease_seconds=60,
        )
        assert same_day["claimed"] is False

        # Failure and partial both release their lease and retain retry backoff.
        failure_day = "2026-09-08"
        claim = try_claim_scheduler_run(
            1, "youtube", failure_day, "owner-c", now=NOW, lease_seconds=60
        )
        assert claim["claimed"] is True
        failed = mark_scheduler_failure(
            1,
            "youtube",
            "synthetic failure",
            failed_at=NOW.isoformat(),
            backoff_seconds=(30,),
            owner_id="owner-c",
        )
        assert failed["applied"] is True
        assert failed["sync_state"]["scheduler_status"] == "failed"
        assert failed["sync_state"]["scheduler_lease_owner"] is None
        assert try_claim_scheduler_run(
            1,
            "youtube",
            failure_day,
            "owner-d",
            now=NOW + timedelta(seconds=29),
            lease_seconds=60,
        )["claimed"] is False
        assert try_claim_scheduler_run(
            1,
            "youtube",
            failure_day,
            "owner-d",
            now=NOW + timedelta(seconds=30),
            lease_seconds=60,
        )["claimed"] is True
        partial = mark_scheduler_failure(
            1,
            "youtube",
            "synthetic partial",
            failed_at=(NOW + timedelta(seconds=30)).isoformat(),
            backoff_seconds=(30,),
            status="partial",
            owner_id="owner-d",
        )
        assert partial["applied"] is True
        assert partial["sync_state"]["scheduler_status"] == "partial"
        assert partial["sync_state"]["scheduler_lease_owner"] is None

        summary = get_scheduler_persistent_summary(now=NOW + timedelta(seconds=31))
        assert summary["active_leases"] == 0
        assert summary["accounts_in_retry"] == 1

        status = schedulers[0].status()
        assert set(status) >= {
            "enabled",
            "running",
            "instance_id",
            "interval_seconds",
            "lease_seconds",
            "last_check_at",
            "check_count",
            "last_error",
            "persistent",
        }
        assert set(status["persistent"]) >= {
            "due_accounts_count",
            "active_leases",
            "expired_leases",
            "accounts_in_retry",
            "last_success_at",
            "last_failure_at",
        }
        router_source = (BACKEND / "routers" / "accounts.py").read_text(encoding="utf-8")
        assert "@router.get('/accounts/scheduler/status')" in router_source
        # sqlite3 context managers commit/rollback but connection finalization
        # remains GC-driven; release Windows file handles before temp cleanup.
        gc.collect()
    finally:
        gc.collect()
        for path in Path(temp_dir).glob("*"):
            try:
                path.unlink()
            except PermissionError:
                time.sleep(0.1)
                path.unlink(missing_ok=True)
        Path(temp_dir).rmdir()

    print("Scheduler cross-process claim/lease smoke test passed")
    print("competitors=2; claims=1; executions=1; expiry/reclaim/stale-owner=PASS")


if __name__ == "__main__":
    main()
