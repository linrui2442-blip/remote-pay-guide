"""Network-free D9 GA4 Data API contract and growth ingestion smoke test."""
import os
import sys
import tempfile
from pathlib import Path

DB = Path(tempfile.gettempdir()) / "remote-pay-guide-d9-r44.db"
DB.unlink(missing_ok=True)
os.environ["OS_TESTING"] = "1"
os.environ["OS_DATABASE_PATH"] = str(DB)
os.environ["OS_GA4_PROPERTY_ID"] = "123456"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from attribution import ga4
from data.growth import get_content_funnel, get_intent_events


class FakeClient:
    referral_count = 3
    def get_metadata(self, **_):
        return {"dimensions": [{"apiName": name} for name in ga4.DIMENSIONS]}

    def run_report(self, request=None):
        assert [item["name"] for item in request["dimensions"]] == list(ga4.DIMENSIONS)
        assert [item["name"] for item in request["metrics"]] == [ga4.METRIC]
        assert set(request["dimension_filter"]["filter"]["in_list_filter"]["values"]) == set(ga4.EVENTS)
        return {"rows": [
            {"dimension_values": [{"value": value} for value in ("20260912", "page_view", "short04", "yt_short04")], "metric_values": [{"value": "7"}]},
            {"dimension_values": [{"value": value} for value in ("20260912", "binance_referral_click", "short04", "yt_short04")], "metric_values": [{"value": str(self.referral_count)}]},
            {"dimension_values": [{"value": value} for value in ("20260912", "binance_referral_click", "unknown", "yt_short04")], "metric_values": [{"value": "99"}]},
        ]}


ga4.get_publish_tasks = lambda: [{"video_id": "short04", "platform": "youtube", "account_id": 1, "platform_video_id": "yt-04"}]
assert ga4.readiness(FakeClient())["ready"] is True
assert ga4.readiness(FakeClient())["enabled"] is False
os.environ["OS_GA4_DATA_INGEST_ENABLED"] = "true"
try:
    ga4.sync("20260901", "20261201", client=FakeClient(), dry_run=True)
except ValueError:
    pass
else:
    raise AssertionError("date ranges over 90 days must fail")

first = ga4.sync("2026-09-12", "2026-09-12", client=FakeClient())
assert first["rows_read"] == 3 and first["upserted"] == 2
assert first["skipped_unattributed"] == 1
second = ga4.sync("2026-09-12", "2026-09-12", client=FakeClient())
assert second["upserted"] == 2
rows = get_intent_events("short04", platform="youtube", account_id=1)
assert len(rows) == 2
assert {row["event_count"] for row in rows} == {3, 7}
funnel = get_content_funnel("short04", platform="youtube", account_id=1)
assert funnel["intent"]["total"] == 10
assert funnel["intent"]["by_type"]["binance_referral_click"] == 3
FakeClient.referral_count = 7
ga4.sync("2026-09-12", "2026-09-12", client=FakeClient())
assert get_content_funnel("short04", platform="youtube", account_id=1)["intent"]["by_type"]["binance_referral_click"] == 7
FakeClient.referral_count = 6
ga4.sync("2026-09-12", "2026-09-12", client=FakeClient())
assert get_content_funnel("short04", platform="youtube", account_id=1)["intent"]["by_type"]["binance_referral_click"] == 6
print("GA4 Data Center ingestion contract smoke test passed")
