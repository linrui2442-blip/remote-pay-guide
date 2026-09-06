import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "os" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from analytics.manager import save_metric
from analytics.models import AnalyticsMetric
from data.query import query_data_center


def reset_test_db():
    Path("os/database").mkdir(parents=True, exist_ok=True)
    db = Path("os/database/os.db")
    if db.exists():
        db.unlink()


def add_metric(video_id, rate, views):
    save_metric(
        AnalyticsMetric(
            video_id=video_id,
            content_id=video_id,
            platform="tiktok",
            account_id=901,
            source="future-provider",
            views=views,
            metrics={
                "full_video_watched_rate": rate,
                "reach": views * 3,
            },
        )
    )


def main():
    reset_test_db()
    add_metric("tiktok-a", 0.42, 100)
    add_metric("tiktok-b", 0.73, 80)

    result = query_data_center(
        account_id=901,
        platform="tiktok",
        scope="active",
        metrics="views,full_video_watched_rate,reach",
        sort_by="full_video_watched_rate",
        sort_direction="desc",
    )

    assert result["returned"] == 2
    assert result["filters"]["metrics"] == [
        "views",
        "full_video_watched_rate",
        "reach",
    ]
    assert "full_video_watched_rate" in result["metric_catalog"]
    assert "reach" in result["metric_catalog"]
    assert result["rows"][0]["video_id"] == "tiktok-b"
    assert result["rows"][0]["metric_values"]["full_video_watched_rate"] == 0.73
    assert result["rows"][0]["metric_values"]["reach"] == 240
    assert result["rows"][1]["metric_values"]["views"] == 100

    try:
        query_data_center(metrics="views,bad metric")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid metric names must be rejected")

    print("Generic Data Center query smoke test passed")
    print("Metric selection -> provider-neutral metric_values")
    print("Custom provider metric -> sortable without schema changes")


if __name__ == "__main__":
    main()
