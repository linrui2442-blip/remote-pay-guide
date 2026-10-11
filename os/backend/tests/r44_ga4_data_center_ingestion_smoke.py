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
from intelligence.feedback import analyze_feedback
from intelligence.policy_signals import _business


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
            {"dimension_values": [{"value": value} for value in ("20260912", "payment_type_select", "short04", "yt_short04")], "metric_values": [{"value": "5"}]},
            {"dimension_values": [{"value": value} for value in ("20260912", "payer_type_select", "short04", "yt_short04")], "metric_values": [{"value": "4"}]},
            {"dimension_values": [{"value": value} for value in ("20260912", "exchange_status_select", "short04", "yt_short04")], "metric_values": [{"value": "2"}]},
            {"dimension_values": [{"value": value} for value in ("20260912", "new_to_exchange_identified", "short04", "yt_short04")], "metric_values": [{"value": "2"}]},
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
assert first["rows_read"] == 7 and first["upserted"] == 6
assert first["skipped_unattributed"] == 1
assert first["landing_rows"] == 1 and first["referral_rows"] == 2
assert set(first["event_rows_by_type"]) == set(ga4.EVENTS.values())
second = ga4.sync("2026-09-12", "2026-09-12", client=FakeClient())
assert second["upserted"] == 6
rows = get_intent_events("short04", platform="youtube", account_id=1)
assert len(rows) == 6
funnel = get_content_funnel("short04", platform="youtube", account_id=1)
assert funnel["intent"]["total"] == 23
assert funnel["intent"]["qualified_total"] == 5
assert funnel["intent"]["qualified_by_type"] == {"new_to_exchange_identified": 2, "binance_referral_click": 3}
assert funnel["intent"]["by_type"]["binance_referral_click"] == 3
feedback = analyze_feedback({"video_id":"short04", "performance":{}, "funnel":funnel})
assert feedback.intent_events == 5 and feedback.referral_clicks == 3
assert _business({"feedback":feedback.__dict__}) == ("PASS", "QUALIFIED_REFERRAL_INTENT_PRESENT")
engagement_only={"intent":{"total":27,"by_type":{"landing_view":7,"payment_type_select":10,"payer_type_select":6,"exchange_status_select":4}},"conversion":{}}
engagement_feedback=analyze_feedback({"video_id":"engagement", "performance":{"views":100}, "funnel":engagement_only})
assert engagement_feedback.intent_events == 0
assert _business({"feedback":engagement_feedback.__dict__})[0] == "WARN"
assert get_content_funnel("short04", "2026-09-13", "2026-09-13", platform="youtube", account_id=1)["intent"]["total"] == 0
assert get_content_funnel("short04", platform="facebook", account_id=1)["intent"]["total"] == 0
assert get_content_funnel("short04", platform="youtube", account_id=2)["intent"]["total"] == 0
FakeClient.referral_count = 7
ga4.sync("2026-09-12", "2026-09-12", client=FakeClient())
assert get_content_funnel("short04", platform="youtube", account_id=1)["intent"]["by_type"]["binance_referral_click"] == 7
FakeClient.referral_count = 6
ga4.sync("2026-09-12", "2026-09-12", client=FakeClient())
assert get_content_funnel("short04", platform="youtube", account_id=1)["intent"]["by_type"]["binance_referral_click"] == 6
assert len(get_intent_events("short04", platform="youtube", account_id=1)) == 6
print("GA4 Data Center ingestion contract smoke test passed")
