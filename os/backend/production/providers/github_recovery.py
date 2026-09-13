from production.results.manager import claim_failed_result_for_recovery, get_result, update_result
from production.providers.github_monitor import GitHubRunMonitor
from assets.github_pages import promote_artifact_to_pages
from integrations.github.client import GitHubClient

def recover_failed_github_result(result_id, job, client=None, recovery_run_id=None, recovery_artifact=None):
    result=get_result(result_id)
    if not result or result.get('status') != 'failed': return result
    if not claim_failed_result_for_recovery(result_id): return get_result(result_id)
    client=client or GitHubClient(); monitor=GitHubRunMonitor(client); out=dict(result.get('output') or {})
    try:
        run=monitor.wait_for_terminal(recovery_run_id,max_attempts=1,poll_interval=0)
        if run.get('conclusion')!='success': raise RuntimeError('Recovery workflow failed')
        artifact=monitor.discover_artifact(recovery_run_id,expected_name=recovery_artifact)
        video_id=str(result.get('video_id') or out.get('content_id') or '').strip()
        if not video_id: raise RuntimeError('Recovery result is missing video identity')
        promotion=promote_artifact_to_pages(source_run_id=recovery_run_id,artifact_name=artifact['name'],asset_path='final-output.mp4',asset_filename=f'{video_id}.mp4',client=client,monitor=monitor,verify_url=True)
        out.update({'recovery_run_id':recovery_run_id,'recovery_artifact_name':artifact['name'], 'recovery_artifact_id':artifact.get('id'), **promotion})
        return update_result(result_id,status='completed',output=out,error='')
    except Exception as exc:
        return update_result(result_id,status='failed',output=out,error=str(exc))
