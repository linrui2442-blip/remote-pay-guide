from test_database_helper import TEST_DATABASE_PATH, assert_safe_test_database_path
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "os" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from analytics.manager import get_latest_metrics, get_metric_value, save_metric
from analytics.models import AnalyticsMetric


def reset_test_db():
    db = TEST_DATABASE_PATH
    if db.exists():
        db.unlink()


def main():
    reset_test_db()

    saved = save_metric(
        AnalyticsMetric(
            video_id="future-video",
            content_id="future-content",
            platform="tiktok",
            account_id=88,
            source="future-provider",
            period_start="2026-09-01",
            period_end="2026-09-05",
            views=250,
            likes=17,
            metrics={
                "full_video_watched_rate": 0.438,
                "reach": 920,
                "profile_visits": 31,
            },
        )
    )

    assert saved["views"] == 250
    assert saved["metrics"]["views"] == 250
    assert saved["metrics"]["likes"] == 17
    assert saved["metrics"]["full_video_watched_rate"] == 0.438
    assert saved["metrics"]["reach"] == 920
    assert get_metric_value(saved, "profile_visits") == 31
    assert get_metric_value(saved, "views") == 250

    latest = get_latest_metrics()
    assert len(latest) == 1
    assert latest[0]["metrics"]["full_video_watched_rate"] == 0.438

    with sqlite3.connect(TEST_DATABASE_PATH) as conn:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(analytics_metrics)").fetchall()
        }

    assert "metrics_json" in columns
    assert "full_video_watched_rate" not in columns
    assert "reach" not in columns
    assert "profile_visits" not in columns

    print("Generic analytics metric storage smoke test passed")
    print("Common metrics -> indexed compatibility columns")
    print("Provider-specific metrics -> metrics_json without schema changes")


if __name__ == "__main__":
    main()
