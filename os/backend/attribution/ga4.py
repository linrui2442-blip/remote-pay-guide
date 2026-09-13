"""Read-only GA4 Data API growth signal ingestion.

This is deliberately a business-signal provider, not a social analytics adapter.
The service is disabled by default and accepts an injectable client for tests.
"""
import hashlib
import os
from datetime import date

from data.growth import record_intent
from data.models import IntentEvent
from publish.manager import get_publish_tasks
from data.tracking import get_tracking_records

MAX_DAYS = 90
EVENTS = {"page_view": "landing_view", "binance_referral_click": "binance_referral_click"}
DIMENSIONS = ("date", "eventName", "customEvent:content_id", "customEvent:src")
METRIC = "eventCount"


def _enabled():
    return os.getenv("OS_GA4_DATA_INGEST_ENABLED", "false").strip().lower() == "true"


def _property_id():
    return os.getenv("OS_GA4_PROPERTY_ID", "").strip() or None


def _credential_available():
    return bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")) or bool(os.getenv("GOOGLE_CLOUD_PROJECT"))


def _parse_date(value, name):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be ISO date YYYY-MM-DD") from None


def _validate_range(start_date, end_date):
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date")
    if start > end:
        raise ValueError("start_date must be on or before end_date")
    if (end - start).days + 1 > MAX_DAYS:
        raise ValueError("GA4 date range cannot exceed 90 days")
    return start.isoformat(), end.isoformat()


def _dimension_names(metadata):
    if isinstance(metadata, dict):
        values = metadata.get("dimensions") or metadata.get("dimensionHeaders") or []
    else:
        values = getattr(metadata, "dimensions", None) or getattr(metadata, "dimension_headers", None) or []
    names = set()
    for item in values:
        if isinstance(item, str): names.add(item)
        elif isinstance(item, dict): names.add(item.get("apiName") or item.get("name"))
        else: names.add(getattr(item, "api_name", None) or getattr(item, "apiName", None))
    return {name for name in names if name}


class GA4DataAPIClient:
    def __init__(self, client=None, property_id=None):
        self.client = client
        self.property_id = property_id or _property_id()

    def _service(self):
        if self.client is not None: return self.client
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        return BetaAnalyticsDataClient()

    def get_metadata(self):
        service = self._service()
        if hasattr(service, "get_metadata"):
            try:
                return service.get_metadata(name=f"properties/{self.property_id}/metadata")
            except TypeError:
                return service.get_metadata(property_id=self.property_id)
        return service.properties().getMetadata(name=f"properties/{self.property_id}").execute()

    def run_report(self, start_date, end_date, limit=1000, offset=0):
        service = self._service()
        request = {
            "property": f"properties/{self.property_id}",
            "date_ranges": [{"start_date": start_date, "end_date": end_date}],
            "dimensions": [{"name": name} for name in DIMENSIONS],
            "metrics": [{"name": METRIC}],
            "dimension_filter": {"filter": {"field_name": "eventName", "in_list_filter": {"values": list(EVENTS)}}},
            "limit": min(max(int(limit), 1), 1000), "offset": max(int(offset), 0),
        }
        if hasattr(service, "run_report"):
            return service.run_report(request=request)
        return service.properties().runReport(property=f"properties/{self.property_id}", body=request).execute()


def readiness(client=None):
    result = {
        "implementation_ready": True, "enabled": _enabled(),
        "property_configured": bool(_property_id()),
        "credential_available": _credential_available() if client is None else True,
        "metadata_verified": False, "content_id_dimension": False,
        "src_dimension": False, "ready": False, "reason": None,
    }
    if not result["property_configured"]:
        result["reason"] = "OS_GA4_PROPERTY_ID is not configured"; return result
    if not result["credential_available"] and client is None:
        result["reason"] = "GA4 Data API credentials are not available"; return result
    try:
        names = _dimension_names(GA4DataAPIClient(client).get_metadata())
        result["metadata_verified"] = True
        result["content_id_dimension"] = "customEvent:content_id" in names
        result["src_dimension"] = "customEvent:src" in names
        result["ready"] = result["content_id_dimension"] and result["src_dimension"]
        if not result["ready"]: result["reason"] = "required GA4 custom event dimensions are not registered"
    except Exception as exc:
        result["reason"] = f"GA4 metadata unavailable: {type(exc).__name__}"
    return result


def _value(item):
    if isinstance(item, dict): return item.get("value", "")
    return getattr(item, "value", "")


def _rows(response):
    rows = response.get("rows", []) if isinstance(response, dict) else getattr(response, "rows", [])
    for row in rows:
        dims = row.get("dimension_values", []) if isinstance(row, dict) else getattr(row, "dimension_values", [])
        mets = row.get("metric_values", []) if isinstance(row, dict) else getattr(row, "metric_values", [])
        values = [_value(item) for item in dims]
        metric = _value(mets[0]) if mets else "0"
        try: count = int(metric)
        except (TypeError, ValueError): raise ValueError("GA4 eventCount is invalid") from None
        if count < 0: raise ValueError("GA4 eventCount cannot be negative")
        if len(values) < 4: raise ValueError("GA4 row is missing dimensions")
        yield {"date": values[0], "event_name": values[1], "content_id": values[2], "src": values[3], "event_count": count}


def _resolve(content_id, src):
    prefix = (src or "").split("_", 1)[0].lower()
    platform = {"yt": "youtube", "ig": "instagram", "fb": "facebook"}.get(prefix)
    tasks = get_publish_tasks()
    candidates = [task for task in tasks if (task.get("video_id") or task.get("content_id")) == content_id]
    if platform: candidates = [task for task in candidates if str(task.get("platform") or "").lower() == platform]
    if not platform and len({str(task.get("platform") or "").lower() for task in candidates}) != 1:
        return None
    if len(candidates) != 1: return None
    task = candidates[0]
    return {"platform": str(task.get("platform") or platform or "").lower(), "account_id": task.get("account_id"), "platform_video_id": task.get("platform_video_id")}


def sync(start_date, end_date, *, client=None, dry_run=False, limit=1000):
    start_date, end_date = _validate_range(start_date, end_date)
    if not dry_run and not _enabled(): raise RuntimeError("GA4 ingestion is disabled")
    ready = readiness(client)
    if not ready["ready"]: raise RuntimeError(ready["reason"] or "GA4 metadata contract is unavailable")
    api = GA4DataAPIClient(client)
    response = api.run_report(start_date, end_date, limit=min(limit, 1000), offset=0)
    result = {"rows_read": 0, "landing_rows": 0, "referral_rows": 0, "resolved": 0, "skipped_unattributed": 0, "skipped_ambiguous": 0, "would_upsert": 0, "upserted": 0}
    for row in _rows(response):
        result["rows_read"] += 1
        event_type = EVENTS.get(row["event_name"])
        if not event_type: continue
        result["landing_rows" if event_type == "landing_view" else "referral_rows"] += 1
        if not row["content_id"] or row["content_id"] == "unknown": result["skipped_unattributed"] += 1; continue
        identity = _resolve(row["content_id"], row["src"])
        if not identity: result["skipped_ambiguous"] += 1; continue
        result["resolved"] += 1
        event_id = "ga4:" + hashlib.sha256(f"{_property_id()}:{row['date']}:{row['event_name']}:{row['content_id']}:{row['src']}".encode()).hexdigest()
        event = IntentEvent(content_id=row["content_id"], event_type=event_type, event_id=event_id, source="ga4_data_api", account_id=identity["account_id"], platform=identity["platform"], platform_video_id=identity["platform_video_id"], event_count=row["event_count"], occurred_at=row["date"], metadata={"ga4_event_name": row["event_name"], "reporting_date": row["date"], "raw_src": row["src"]})
        if dry_run: result["would_upsert"] += 1
        else: record_intent(event); result["upserted"] += 1
    return result
