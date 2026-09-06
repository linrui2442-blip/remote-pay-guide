from analytics.manager import get_video_metrics
from assets.manager import get_asset
from data.content_registry import get_content
from production.manager import get_production_tasks
from production.results.manager import get_result_by_job
from production.runtime.manager import get_jobs
from publish.manager import get_publish_tasks


def _task_matches_content(task, content_id):
    parameters = task.get("parameters") or {}
    candidates = (
        task.get("video_id"),
        task.get("content_id"),
        parameters.get("video_id") if isinstance(parameters, dict) else None,
        parameters.get("content_id") if isinstance(parameters, dict) else None,
    )
    return any(
        value is not None and str(value) == str(content_id)
        for value in candidates
    )


def get_video_lifecycle(video_id):
    production = next(
        (x for x in get_production_tasks() if _task_matches_content(x, video_id)),
        None,
    )
    runtime = next(
        (
            x
            for x in get_jobs()
            if str(x.get("task_id")) == str(production.get("id") if production else "")
        ),
        None,
    )
    result = get_result_by_job(runtime.get("id")) if runtime else None
    asset = get_asset(video_id)
    publish = next(
        (
            x
            for x in get_publish_tasks()
            if str(x.get("video_id") or "") == str(video_id)
        ),
        None,
    )
    performance = get_video_metrics(video_id)
    content_metadata = get_content(video_id)

    return {
        "video_id": video_id,
        "content_metadata": content_metadata,
        "production": production,
        "runtime": runtime,
        "result": result,
        "asset": asset,
        "publish": publish,
        "performance": performance,
    }
