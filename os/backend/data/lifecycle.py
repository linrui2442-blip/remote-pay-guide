from assets.manager import get_asset
from analytics.manager import get_video_metrics
from production.manager import get_production_tasks
from production.runtime.manager import get_jobs
from production.results.manager import get_result_by_job
from publish.manager import get_publish_tasks


def get_video_lifecycle(video_id):
    production = next((x for x in get_production_tasks() if x.get('video_id') == video_id), None)
    runtime = next((x for x in get_jobs() if str(x.get('task_id')) == str(production.get('id') if production else '')), None)
    result = get_result_by_job(runtime.get('id')) if runtime else None
    asset = get_asset(video_id)
    publish = next((x for x in get_publish_tasks() if x.get('video_id') == video_id), None)
    performance = get_video_metrics(video_id)
    return {
        'video_id': video_id,
        'production': production,
        'runtime': runtime,
        'result': result,
        'asset': asset,
        'publish': publish,
        'performance': performance,
    }
