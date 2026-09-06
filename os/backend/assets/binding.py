import uuid

from assets.manager import create_asset
from assets.models import VideoAsset


def _normalize_output(output):
    if isinstance(output, dict):
        return output
    if isinstance(output, str):
        import json
        try:
            decoded = json.loads(output)
            return decoded if isinstance(decoded, dict) else {"url": output}
        except Exception:
            return {"url": output}
    return {}


def create_asset_from_result(result):
    """Bind a completed Production Result into the Video Asset Registry."""
    try:
        provider = result.get("provider")
        output = _normalize_output(result.get("output") or {})

        asset_url = output.get("url") or output.get("asset_url") or output.get("video_url")
        file_path = output.get("file_path") or output.get("path")
        metadata = {"production_output": output}

        if provider == "github":
            source_provider = "github"
            if asset_url and "github.io/" in asset_url:
                storage_type = "github_pages"
            else:
                storage_type = "artifact"
        elif provider == "ai_gateway":
            # AI Remote Production is intentionally external-only. A completed
            # AI job must expose a remote asset URL; the OS never silently falls
            # back to a local file/GPU/model path.
            if not asset_url:
                return {
                    "asset_id": None,
                    "asset_status": "failed",
                    "error": (
                        "AI Gateway completed without a remote asset URL "
                        "(expected url, asset_url, or video_url)"
                    ),
                }
            source_provider = "ai_gateway"
            storage_type = "ai_output"
            file_path = None
        else:
            source_provider = "external"
            storage_type = "external"

        asset_id = output.get("asset_id") or f"asset_{uuid.uuid4().hex[:8]}"
        video_id = (
            result.get("video_id")
            or output.get("video_id")
            or output.get("content_id")
            or str(result.get("runtime_job_id") or "UNKNOWN")
        )

        status = "ready" if asset_url or file_path else "registered"
        if provider == "github" and storage_type != "github_pages":
            status = "processing"

        asset = VideoAsset(
            asset_id=asset_id,
            video_id=str(video_id),
            production_result_id=str(result.get("id")) if result.get("id") is not None else None,
            source_provider=source_provider,
            storage_type=storage_type,
            asset_url=asset_url,
            file_path=file_path,
            status=status,
            metadata=metadata,
            source=source_provider,
            location=asset_url or file_path or "",
        )
        created = create_asset(asset)
        return {
            "asset_id": created.asset_id,
            "asset_status": created.status,
            "source_provider": created.source_provider,
            "storage_type": created.storage_type,
            "asset_url": created.asset_url,
            "video_asset": created,
        }
    except Exception as exc:
        return {
            "asset_id": None,
            "asset_status": "failed",
            "error": str(exc),
        }
