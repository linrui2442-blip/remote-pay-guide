"""Publish event adapters for Remote Pay Guide OS.

Keeps publish domain logic separate from OS event recording.
"""

from events.manager import EventManager


def emit_publish_completed(task, result, event_manager=None):
    manager = event_manager or EventManager()
    manager.emit(
        event_type="publish.completed",
        source="publish",
        entity_type="video",
        entity_id=task.get("video_id") or task.get("asset_id"),
        payload={
            "platform": task.get("platform"),
            "platform_video_id": result.get("video_id"),
            "published_url": result.get("url"),
        },
    )


def emit_publish_failed(task, error, event_manager=None):
    manager = event_manager or EventManager()
    manager.emit(
        event_type="publish.failed",
        source="publish",
        entity_type="video",
        entity_id=task.get("video_id") or task.get("asset_id"),
        payload={"error": error},
    )
