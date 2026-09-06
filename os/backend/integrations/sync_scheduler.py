from analytics.collector import AnalyticsCollector
from analytics.publish_bridge import collect_account_publish_metrics
from integrations.sync_planner import build_account_sync_plan
from integrations.sync_registry import run_content_sync


def execute_account_sync(
    account_id: int,
    platform: str,
    *,
    requested_limit: int = 10,
    sync_mode: str = 'incremental',
    start_date: str | None = None,
    end_date: str | None = None,
    analytics_collector=None,
):
    """Execute a provider-neutral account sync plan in deterministic order.

    The scheduler owns orchestration only. Provider-specific API behavior stays
    behind the content and analytics registries. A later timer/worker can invoke
    this same function without changing platform adapters.
    """
    plan = build_account_sync_plan(
        account_id,
        platform,
        requested_limit=requested_limit,
        sync_mode=sync_mode,
    )
    normalized = plan.get('platform') or ''
    results = []
    failures = []
    collector = analytics_collector or AnalyticsCollector()

    for operation in plan['operations']:
        operation_name = operation['operation']
        try:
            if operation_name == 'content_sync':
                result = run_content_sync(
                    account_id,
                    normalized,
                    max_results=operation['max_results'],
                    sync_mode=operation['sync_mode'],
                )
            elif operation_name == 'analytics_sync':
                result = collect_account_publish_metrics(
                    account_id,
                    platform=normalized,
                    collector=collector,
                    start_date=start_date,
                    end_date=end_date,
                    active_limit=operation['active_limit'],
                )
            else:
                raise RuntimeError(f'unsupported sync operation: {operation_name}')

            results.append(
                {
                    'operation': operation_name,
                    'status': 'success',
                    'result': result,
                }
            )
        except Exception as exc:
            failures.append(
                {
                    'operation': operation_name,
                    'status': 'failed',
                    'error': str(exc),
                }
            )

    if failures and results:
        status = 'partial'
    elif failures:
        status = 'failed'
    else:
        status = 'success'

    return {
        'account_id': account_id,
        'platform': normalized or None,
        'status': status,
        'planned': len(plan['operations']),
        'completed': len(results),
        'failed': len(failures),
        'plan': plan,
        'results': results,
        'failures': failures,
    }
