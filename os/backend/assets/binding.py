import uuid

from assets.manager import create_asset
from assets.models import VideoAsset


def create_asset_from_result(result):
    """Bind completed production result into the Video Asset Registry."""
    try:
        provider = result.get("provider")
        output = result.get("output") or {}
        if isinstance(output, str):
            import json
            try:
                output = json.loads(output)
            except Exception:
                output = {"url": output}

        if provider == "github":
            source_provider = "github"
            storage_type = "github_pages"
        elif provider == "ai_gateway":
            source_provider = "ai_gateway"
            storage_type = "ai_output"
        else:
            source_provider = "external"
            storage_type = "external"

        asset_url = output.get("url") or output.get("asset_url") or output.get("path")
        asset = VideoAsset(
            video_id=str(result.get("video_id") or result.get("runtime_job_id")),
            source=source_provider,
            status="ready",
            location=asset_url or "",
        )
        created = create_asset(asset)
        return {
            "asset_id": f"asset_{uuid.uuid4().hex[:8]}",
            "source_provider": source_provider,
            "storage_type": storage_type,
            "asset_url": asset_url,
            "video_asset": created,
        }
    except Exception as exc:
        return {
            "asset_id": None,
            "asset_status": "failed",
            "error": str(exc),
        }
