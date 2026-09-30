"""Read-only operational projection over canonical tables; no new job engine."""
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from data.database_path import database_path


def _stale(value, now, seconds):
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return (now - stamp).total_seconds() >= seconds
    except (ValueError, TypeError, AttributeError):
        return True


def runtime_health(*, now=None, stale_seconds=900):
    """No credential reads, schema migration, provider probes or error strings.

    Missing tables are explicitly unknown, never a fake healthy empty system.
    Review items preserve the existing entity IDs and do not requeue writes.
    """
    now = now or datetime.now(timezone.utc)
    path = database_path()
    if not path.exists():
        return {'status': 'not_initialized', 'ready': False, 'review_queue': [], 'kill_switch_active': True}
    queue, counts, duplicates = [], {}, {}
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        def rows(table):
            return [dict(r) for r in conn.execute(f'SELECT * FROM {table}')] if table in tables else []
        settings = rows('intelligence_autonomy_settings')
        kill = not settings or bool(settings[0]['kill_switch_active'])
        enabled = bool(settings and settings[0]['autonomy_enabled'])
        specs = {
            'runtime_jobs': ('status', {'created', 'running'}, ('task_id',)),
            'production_results': ('status', {'running'}, ('runtime_job_id',)),
            'asset_quality_checks': ('status', {'REVIEW'}, ('production_result_id',)),
            'publish_tasks': ('status', {'pending', 'publishing', 'review'}, ('asset_id', 'platform', 'account_id')),
            'intelligence_feedback_snapshots': ('learning_state', {'generating', 'policy_pending', 'review'}, ()),
        }
        for table, (field, active, identity) in specs.items():
            records = rows(table)
            counts[table] = len(records) if table in tables else None
            grouped = {}
            for r in records:
                state = r.get(field)
                stamp = r.get('learning_updated_at') if field == 'learning_state' else r.get('updated_at')
                if state in active and (state in {'REVIEW', 'review'} or _stale(stamp, now, stale_seconds)):
                    queue.append({'entity': table, 'id': r['id'], 'reason_code': 'REVIEW_REQUIRED' if state in {'REVIEW', 'review'} else 'STALE_ENTITY'})
                if identity:
                    key = tuple(r.get(k) for k in identity)
                    if all(v is not None for v in key):
                        grouped[key] = grouped.get(key, 0) + 1
            duplicates[table] = sum(n > 1 for n in grouped.values())
        sync = rows('platform_sync_state')
        accounts = [dict(r) for r in conn.execute('SELECT id,status FROM accounts')] if 'accounts' in tables else []
        feedback = rows('intelligence_feedback_snapshots')
        completed = [r for r in feedback if r.get('learning_state') == 'completed']
        policy = rows('intelligence_policy_decisions')
        policies = {s: sum(r.get('decision') == s and not r.get('superseded_at') for r in policy) for s in ('AUTO', 'REVIEW', 'BLOCK')}
        quality = rows('asset_quality_checks')
        qualities = {s: sum(r.get('status') == s for r in quality) for s in ('PASS', 'REVIEW', 'BLOCK')}
        required = set(specs) | {'accounts', 'platform_sync_state', 'intelligence_policy_decisions'}
        missing = sorted(required - tables)
        return {'status': 'review' if queue or any(duplicates.values()) or missing else 'observed',
                'ready': not queue and not any(duplicates.values()) and not missing,
                'missing_tables': missing, 'kill_switch_active': kill,
                'autonomous_execution_allowed': enabled and not kill,
                'review_queue': queue, 'entity_counts': counts, 'duplicate_groups': duplicates,
                'policy_outcomes': policies, 'quality_outcomes': qualities,
                'publish_intent_count': len(rows('publish_write_intents')),
                'data_sync_healthy': bool(sync) and all(r.get('last_success_at') and r.get('analytics_status') != 'failed' and r.get('content_status') != 'failed' and not _stale(r.get('last_success_at'), now, 172800) for r in sync),
                'ai_text_configured': bool(os.getenv('AI_TEXT_API_KEY')),
                'github_configured': bool(os.getenv('GITHUB_TOKEN')),
                'accounts_connected': sum(r.get('status') in {'connected', 'active', 'ready'} for r in accounts),
                'account_credential_readiness': 'NOT_CHECKED',
                'provider_live_readiness': 'NOT_CHECKED',
                'last_feedback_cycle_id': max((r['id'] for r in completed), default=None)}


def reconcile_local_evidence():
    """Delegate to canonical local-only reconcilers, never call provider polling.

    Stale production jobs/results remain visible for authorized canonical
    recovery. We never infer success from elapsed time or reassign write owners.
    """
    before = runtime_health()
    recovered, review = [], []
    for item in before['review_queue']:
        entity, ident = item['entity'], item['id']
        if before.get('duplicate_groups', {}).get(entity):
            review.append(item)
            continue
        try:
            if entity == 'publish_tasks':
                from publish.manager import get_publish_task
                from publish.execution import reconcile_autonomous_publish_task
                task = get_publish_task(ident)
                if task.get('autonomous_policy_version') != 'g5-v1':
                    review.append(item)
                    continue
                result = reconcile_autonomous_publish_task(ident)
                if result['status'] == 'published':
                    recovered.append(item)
                else:
                    review.append(item)
            elif entity == 'intelligence_feedback_snapshots':
                from intelligence.learning import recover_feedback_policy
                result = recover_feedback_policy(ident)
                (recovered if result['learning_state'] == 'completed' else review).append(item)
            else:
                review.append(item)
        except Exception:
            review.append(dict(item, reason_code='CANONICAL_RECONCILIATION_REJECTED'))
    return {'recovered': recovered, 'review': review, 'external_requests': 0}
