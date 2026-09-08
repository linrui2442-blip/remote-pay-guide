import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from accounts.manager import get_accounts
from analytics.collector import AnalyticsCollector
from analytics.publish_bridge import collect_account_publish_metrics
from analytics.registry import get_analytics_adapter_registration
from data.sync_state import (
    get_scheduler_persistent_summary,
    get_sync_state,
    mark_scheduler_failure,
    mark_scheduler_success,
    mark_sync_failure,
    mark_sync_partial,
    renew_scheduler_lease,
    try_claim_scheduler_run,
)
from integrations.sync_planner import build_account_sync_plan
from integrations.sync_registry import run_content_sync
from intelligence.feedback_bridge import refresh_account_feedback


def execute_account_sync(
    account_id: int,
    platform: str,
    *,
    requested_limit: int = 10,
    sync_mode: str = 'incremental',
    start_date: str | None = None,
    end_date: str | None = None,
    analytics_collector=None,
    intelligence_refresher=None,
    analytics_windows=None,
):
    """Execute a provider-neutral account sync plan in deterministic order.

    The scheduler owns orchestration only. Provider-specific API behavior stays
    behind the content and analytics registries. Once Analytics succeeds, the
    latest Data Center rows flow into Intelligence strategy snapshots without
    automatically executing or publishing a production task.
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
    skipped = []
    collector = analytics_collector or AnalyticsCollector()
    feedback_refresh = intelligence_refresher or refresh_account_feedback

    for operation in plan['operations']:
        operation_name = operation['operation']

        if operation_name == 'intelligence_feedback' and any(
            item.get('operation') == 'analytics_sync' for item in failures
        ):
            skipped.append(
                {
                    'operation': operation_name,
                    'status': 'skipped',
                    'reason': 'analytics_sync failed; intelligence snapshot was not refreshed from stale data',
                }
            )
            continue

        try:
            if operation_name == 'content_sync':
                result = run_content_sync(
                    account_id,
                    normalized,
                    max_results=operation['max_results'],
                    sync_mode=operation['sync_mode'],
                )
            elif operation_name == 'analytics_sync':
                windows = analytics_windows or [(start_date, end_date)]
                window_results = []
                successful_windows = []
                window_errors = []
                for window_start, window_end in windows:
                    try:
                        window_result = collect_account_publish_metrics(
                            account_id,
                            platform=normalized,
                            collector=collector,
                            start_date=window_start,
                            end_date=window_end,
                            active_limit=operation['active_limit'],
                        )
                        window_results.append(window_result)
                        successful_windows.append((window_start, window_end, window_result))
                    except Exception as exc:
                        window_errors.append({
                            'start_date': window_start,
                            'end_date': window_end,
                            'error': str(exc),
                        })
                result = window_results[0] if len(window_results) == 1 else {
                    'windows': window_results,
                    'daily': next((item for start, end, item in successful_windows if start and start == end), None),
                    'period_aggregate': next((item for start, end, item in successful_windows if start is None and end is None), None),
                    'window_errors': window_errors,
                }
                window_statuses = [
                    (item.get('sync_state') or {}).get('analytics_status', 'success')
                    for item in window_results
                ]
                if window_errors or any(status != 'success' for status in window_statuses):
                    combined_status = (
                        'partial'
                        if 'success' in window_statuses or 'partial' in window_statuses
                        else 'failed'
                    )
                    combined_error = 'one or more analytics windows were partial or failed'
                    if combined_status == 'partial':
                        mark_sync_partial(
                            account_id,
                            normalized,
                            'analytics',
                            error=combined_error,
                        )
                    else:
                        mark_sync_failure(
                            account_id,
                            normalized,
                            'analytics',
                            combined_error,
                        )
                    results.append({
                        'operation': operation_name,
                        'status': combined_status,
                        'result': result,
                    })
                    failures.append({
                        'operation': operation_name,
                        'status': combined_status,
                        'error': combined_error,
                    })
                    continue
            elif operation_name == 'intelligence_feedback':
                result = feedback_refresh(
                    account_id,
                    platform=normalized,
                    limit=operation['active_limit'],
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

    if failures and (results or skipped):
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
        'skipped': len(skipped),
        'plan': plan,
        'results': results,
        'failures': failures,
        'skipped_operations': skipped,
    }


def _utc_datetime(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def due_accounts(*, now=None, accounts=None):
    """Return connected accounts whose last successful daily window is stale."""
    current = _utc_datetime(now)
    due = []
    for account in accounts if accounts is not None else get_accounts():
        if str(account.get('status') or '').strip().lower() != 'connected':
            continue
        platform = str(account.get('platform') or '').strip().lower()
        if not platform:
            continue
        registration = get_analytics_adapter_registration(platform)
        reporting_timezone = (
            registration.reporting_timezone if registration else 'UTC'
        )
        provider_now = current.astimezone(ZoneInfo(reporting_timezone))
        target_day = (provider_now.date() - timedelta(days=1)).isoformat()
        state = get_sync_state(account['id'], platform)
        plan = build_account_sync_plan(account['id'], platform)
        if not any(item.get('operation') == 'analytics_sync' for item in plan['operations']):
            continue
        if state.get('scheduler_last_daily_date') == target_day:
            continue
        next_retry = state.get('scheduler_next_retry_at')
        if next_retry and _utc_datetime(next_retry) > current:
            continue
        lease_owner = state.get('scheduler_lease_owner')
        lease_expires = state.get('scheduler_lease_expires_at')
        if lease_owner and lease_expires and _utc_datetime(lease_expires) > current:
            continue
        due.append({
            'account': account,
            'sync_state': state,
            'daily_date': target_day,
        })
    return due


class BackgroundAccountSyncScheduler:
    """Minute-scale in-process scheduler over the existing account sync executor."""

    def __init__(
        self,
        interval_seconds=None,
        *,
        account_source=None,
        sync_executor=None,
        clock=None,
        backoff_seconds=(300, 900, 3600),
        lease_seconds=None,
        heartbeat_seconds=None,
        stuck_warning_seconds=None,
        owner_id=None,
    ):
        configured = (
            interval_seconds
            or os.getenv('ACCOUNT_SYNC_CHECK_INTERVAL_SECONDS')
            or 60
        )
        self.interval_seconds = max(5.0, float(configured))
        self.account_source = account_source or get_accounts
        self.sync_executor = sync_executor or execute_account_sync
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.backoff_seconds = tuple(backoff_seconds)
        configured_lease = (
            lease_seconds
            or os.getenv('ACCOUNT_SYNC_LEASE_SECONDS')
            or 1800
        )
        self.lease_seconds = max(30, int(configured_lease))
        configured_heartbeat = heartbeat_seconds or os.getenv(
            'ACCOUNT_SYNC_LEASE_HEARTBEAT_SECONDS'
        )
        automatic_heartbeat = min(60.0, max(1.0, self.lease_seconds / 3))
        self.heartbeat_seconds = (
            max(0.5, min(float(configured_heartbeat), self.lease_seconds / 2))
            if configured_heartbeat else automatic_heartbeat
        )
        configured_stuck = stuck_warning_seconds or os.getenv(
            'ACCOUNT_SYNC_STUCK_WARNING_SECONDS'
        )
        self.stuck_warning_seconds = max(
            self.heartbeat_seconds * 3,
            float(configured_stuck) if configured_stuck else self.lease_seconds * 2,
        )
        self.owner_id = str(owner_id or uuid.uuid4())
        self.instance_id = self.owner_id.replace('-', '')[:12]
        self._stop_event = threading.Event()
        self._thread = None
        self.last_check_at = None
        self.last_error = None
        self.check_count = 0

    def _start_lease_heartbeat(self, account_id, platform, daily_date):
        stop_event = threading.Event()
        state = {'lease_lost': False, 'renewals': 0, 'last_error': None}

        def heartbeat():
            while not stop_event.wait(self.heartbeat_seconds):
                try:
                    transition = renew_scheduler_lease(
                        account_id,
                        platform,
                        daily_date,
                        self.owner_id,
                        renewed_at=_utc_datetime(self.clock()),
                        lease_seconds=self.lease_seconds,
                    )
                    if not transition['applied']:
                        state['lease_lost'] = True
                        state['last_error'] = transition['reason']
                        return
                    state['renewals'] += 1
                except Exception as exc:
                    state['last_error'] = str(exc)

        thread = threading.Thread(
            target=heartbeat,
            name=f'account-sync-lease-heartbeat-{self.instance_id}',
            daemon=True,
        )
        thread.start()
        return stop_event, thread, state

    def run_once(self):
        now = _utc_datetime(self.clock())
        candidates = due_accounts(now=now, accounts=self.account_source())
        outcomes = []
        for candidate in candidates:
            account = candidate['account']
            platform = str(account.get('platform') or '').strip().lower()
            daily_date = candidate['daily_date']
            attempted_at = now.isoformat()
            claim = try_claim_scheduler_run(
                account['id'],
                platform,
                daily_date,
                self.owner_id,
                now=now,
                lease_seconds=self.lease_seconds,
            )
            if not claim['claimed']:
                outcomes.append({
                    'account_id': account['id'],
                    'platform': platform,
                    'status': 'not_claimed',
                    'lease_status': claim['reason'],
                    'sync_state': claim['sync_state'],
                })
                continue
            heartbeat_stop, heartbeat_thread, heartbeat_state = (
                self._start_lease_heartbeat(account['id'], platform, daily_date)
            )
            started_monotonic = time.monotonic()
            try:
                result = self.sync_executor(
                    account['id'],
                    platform,
                    sync_mode='incremental',
                    analytics_windows=[(daily_date, daily_date), (None, None)],
                )
                finished_at = _utc_datetime(self.clock()).isoformat()
                duration_seconds = max(0.0, time.monotonic() - started_monotonic)
                heartbeat_stop.set()
                heartbeat_thread.join(timeout=min(self.heartbeat_seconds, 2.0))
                if heartbeat_state['lease_lost']:
                    outcomes.append({
                        'account_id': account['id'],
                        'platform': platform,
                        'status': 'lease_lost',
                        'lease_status': 'lease_lost',
                        'heartbeat': heartbeat_state,
                        'result': result,
                        'sync_state': get_sync_state(account['id'], platform),
                    })
                    continue
                result_status = result.get('status')
                if result_status != 'success':
                    errors = result.get('failures') or []
                    error = (
                        errors[0].get('error')
                        if errors
                        else f"account sync returned {result_status}"
                    )
                    transition = mark_scheduler_failure(
                        account['id'], platform, error, failed_at=finished_at,
                        backoff_seconds=self.backoff_seconds, status=result_status,
                        owner_id=self.owner_id,
                        duration_seconds=duration_seconds,
                    )
                    state = transition['sync_state']
                    outcome_status = result_status if transition['applied'] else 'lease_lost'
                    outcomes.append({
                        'account_id': account['id'],
                        'platform': platform,
                        'status': outcome_status,
                        'lease_status': transition['reason'],
                        'heartbeat': heartbeat_state,
                        'error': error,
                        'result': result,
                        'sync_state': state,
                    })
                    continue
                transition = mark_scheduler_success(
                    account['id'], platform, daily_date,
                    owner_id=self.owner_id, succeeded_at=finished_at,
                    duration_seconds=duration_seconds,
                )
                state = transition['sync_state']
                outcomes.append({
                    'account_id': account['id'],
                    'platform': platform,
                    'status': 'success' if transition['applied'] else 'lease_lost',
                    'lease_status': transition['reason'],
                    'heartbeat': heartbeat_state,
                    'result': result,
                    'sync_state': state,
                })
            except Exception as exc:
                finished_at = _utc_datetime(self.clock()).isoformat()
                duration_seconds = max(0.0, time.monotonic() - started_monotonic)
                heartbeat_stop.set()
                heartbeat_thread.join(timeout=min(self.heartbeat_seconds, 2.0))
                if heartbeat_state['lease_lost']:
                    outcomes.append({
                        'account_id': account['id'], 'platform': platform,
                        'status': 'lease_lost', 'lease_status': 'lease_lost',
                        'heartbeat': heartbeat_state, 'error': str(exc),
                        'sync_state': get_sync_state(account['id'], platform),
                    })
                    continue
                transition = mark_scheduler_failure(
                    account['id'],
                    platform,
                    exc,
                    failed_at=finished_at,
                    backoff_seconds=self.backoff_seconds,
                    owner_id=self.owner_id,
                    duration_seconds=duration_seconds,
                )
                state = transition['sync_state']
                outcomes.append({
                    'account_id': account['id'],
                    'platform': platform,
                    'status': 'failed' if transition['applied'] else 'lease_lost',
                    'lease_status': transition['reason'],
                    'heartbeat': heartbeat_state,
                    'error': str(exc),
                    'sync_state': state,
                })
        self.last_check_at = now.isoformat()
        self.check_count += 1
        self.last_error = next(
            (item.get('error') or item.get('lease_status')
             for item in outcomes if item['status'] in {'failed', 'lease_lost'}),
            None,
        )
        return {'checked': len(candidates), 'outcomes': outcomes, 'checked_at': self.last_check_at}

    def _loop(self):
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:
                self.last_error = str(exc)
            self._stop_event.wait(self.interval_seconds)

    def start(self):
        if self._thread and self._thread.is_alive():
            return self.status()
        if str(os.getenv('OS_DISABLE_BACKGROUND_ACCOUNT_SYNC') or '').lower() in {'1', 'true', 'yes'}:
            return self.status()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name='account-sync-scheduler',
            daemon=True,
        )
        self._thread.start()
        return self.status()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=min(self.interval_seconds, 2.0))
        return self.status()

    def status(self):
        disabled = str(os.getenv('OS_DISABLE_BACKGROUND_ACCOUNT_SYNC') or '').lower() in {'1', 'true', 'yes'}
        now = _utc_datetime(self.clock())
        persistent = get_scheduler_persistent_summary(
            now=now, stuck_warning_seconds=self.stuck_warning_seconds
        )
        try:
            due_count = len(due_accounts(now=now, accounts=self.account_source()))
        except Exception:
            due_count = None
        if disabled:
            health = 'disabled'
        elif persistent['stuck_accounts_count']:
            health = 'stuck_suspected'
        elif persistent['active_leases']:
            health = 'running'
        elif persistent['accounts_in_retry']:
            health = 'retrying'
        elif persistent.get('last_failure_at') and (
            not persistent.get('last_success_at')
            or persistent['last_failure_at'] > persistent['last_success_at']
        ):
            health = 'degraded'
        else:
            health = 'healthy'
        remaining = persistent.get('lease_remaining_seconds')
        lease_health = (
            'inactive' if remaining is None else
            'at_risk' if remaining <= self.heartbeat_seconds * 1.5 else
            'renewing'
        )
        return {
            'enabled': not disabled,
            'running': bool(self._thread and self._thread.is_alive()),
            'health': health,
            'lease_health': lease_health,
            'instance_id': self.instance_id,
            'interval_seconds': self.interval_seconds,
            'lease_seconds': self.lease_seconds,
            'heartbeat_seconds': self.heartbeat_seconds,
            'stuck_warning_seconds': self.stuck_warning_seconds,
            'last_check_at': self.last_check_at,
            'last_error': self.last_error,
            'check_count': self.check_count,
            'persistent': {
                'due_accounts_count': due_count,
                **persistent,
            },
        }


account_sync_scheduler = BackgroundAccountSyncScheduler()
