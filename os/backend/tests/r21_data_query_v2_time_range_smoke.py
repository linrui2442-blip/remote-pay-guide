import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "os" / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from analytics.manager import save_metric
from analytics.models import AnalyticsMetric
from data.models import ConversionRecord, IntentEvent
from data.query import query_data_center
from data.growth import record_conversion, record_intent


def reset_test_db():
    path = Path("os/database/os.db")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)


def metric(start, end, views, collected_at, likes=0):
    return save_metric(
        AnalyticsMetric(
            video_id="v2-video",
            content_id="v2-content",
            platform="youtube",
            account_id=42,
            source="test",
            period_start=start,
            period_end=end,
            views=views,
            likes=likes,
            collected_at=collected_at,
        )
    )


def main():
    reset_test_db()

    # V1 has no new required fields and continues to select only the latest snapshot.
    metric("2026-08-01", "2026-08-28", 100, "2026-08-29T00:00:00+00:00")
    metric("2026-08-01", "2026-08-28", 120, "2026-08-30T00:00:00+00:00")
    v1 = query_data_center(account_id=42, platform="youtube")
    assert "query_version" not in v1
    assert v1["summary"]["total_views"] == 120

    # Exact 28-day windows use the latest collection, never SUM overlapping copies.
    ranged = query_data_center(
        account_id=42,
        platform="youtube",
        date_range="28d",
        end_date="2026-08-28",
    )
    assert ranged["query_version"] == "v2"
    assert ranged["period"]["start_date"] == "2026-08-01"
    assert ranged["summary"]["total_views"] == 120
    assert ranged["rows"][0]["snapshot_selection"] == "exact_window_latest"
    assert ranged["time_series"]["available"] is False

    # Daily snapshots are independently de-duplicated and can form a real trend.
    metric("2026-07-30", "2026-07-30", 3, "2026-07-31T00:00:00+00:00")
    metric("2026-07-31", "2026-07-31", 7, "2026-08-01T00:00:00+00:00")
    metric("2026-08-01", "2026-08-01", 4, "2026-08-02T00:00:00+00:00")
    metric("2026-08-01", "2026-08-01", 5, "2026-08-03T00:00:00+00:00")
    metric("2026-08-02", "2026-08-02", 10, "2026-08-03T00:00:00+00:00")
    record_intent(IntentEvent(content_id="v2-content", event_type="binance_referral_click", occurred_at="2026-08-01T12:00:00+00:00"))
    record_intent(IntentEvent(content_id="v2-content", event_type="binance_referral_click", occurred_at="2026-07-31T12:00:00+00:00"))
    record_conversion(ConversionRecord(content_id="v2-content", conversion_type="sale", value=25, occurred_at="2026-08-02T12:00:00+00:00"))

    custom = query_data_center(
        account_id=42,
        platform="youtube",
        date_range="custom",
        start_date="2026-08-01",
        end_date="2026-08-02",
        compare_previous_period=True,
        interval="daily",
    )
    assert custom["summary"]["total_views"] == 15
    assert custom["summary"]["referral_clicks"] == 1
    assert custom["summary"]["conversions"] == 1
    assert custom["summary"]["conversion_value"] == 25
    assert [point["metric_values"]["views"] for point in custom["time_series"]["points"]] == [5, 10]
    assert custom["comparison"]["period"]["start_date"] == "2026-07-30"
    assert custom["comparison"]["period"]["end_date"] == "2026-07-31"
    assert custom["comparison"]["summary"]["total_views"] == 10
    assert custom["comparison"]["summary"]["referral_clicks"] == 1
    assert custom["comparison"]["metrics"]["views"]["change"] == 5

    # A partially overlapping multi-day snapshot is never added to daily values.
    metric("2026-07-31", "2026-08-02", 999, "2026-08-04T00:00:00+00:00")
    repeated = query_data_center(
        account_id=42,
        platform="youtube",
        date_range="custom",
        start_date="2026-08-01",
        end_date="2026-08-02",
        interval="daily",
    )
    assert repeated["summary"]["total_views"] == 15
    assert repeated["snapshot_semantics"]["overlapping_windows_summed"] is False

    print("Data Center Query V2 time range smoke test passed")
    print("V1 compatibility; 28d/custom; previous period; daily trend; overlap de-dup")


if __name__ == "__main__":
    main()
