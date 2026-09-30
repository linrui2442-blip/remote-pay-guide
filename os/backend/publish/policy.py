"""g5-v1: server-owned publishing policy on the existing PublishTask lifecycle.

No network, no execution. Decisions are evidence on canonical PublishTasks, not
a second queue/domain. Rejected decisions return safe reason codes to callers.
"""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone

from accounts.manager import get_account
from assets.quality import _binding, _load_source, _quality_row, init_quality_table
from intelligence.autonomy import get_autonomy_settings
from oauth.manager import get_token
from publish import manager
from publish.models import PublishTask
from publish.registry import get_adapter

POLICY_VERSION = 'g5-v1'
CADENCE = {'youtube': (3600, 3), 'instagram': (3600, 3), 'facebook': (3600, 3)}


def now():
    return datetime.now(timezone.utc)


def stamp(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def task_fingerprint(task):
    keys = ('asset_id', 'video_id', 'platform', 'account_id', 'scheduled_time',
            'title', 'description', 'tags', 'privacy_status')
    return hashlib.sha256(json.dumps({k: task.get(k) for k in keys}, sort_keys=True).encode()).hexdigest()


def runtime_signals(platform, account_id):
    """Read local credentials only; never refresh or call a provider here."""
    account = get_account(account_id)
    adapter = get_adapter(platform)
    token = get_token(account_id)
    settings = get_autonomy_settings()
    reasons, unknown = [], []
    if settings['kill_switch_active']:
        reasons.append('KILL_SWITCH_ACTIVE')
    if not settings['autonomy_enabled']:
        unknown.append('AUTONOMY_DISABLED')
    if not account or account.get('platform') != platform:
        reasons.append('ACCOUNT_PLATFORM_MISMATCH')
    elif account.get('status') in {'disconnected', 'inactive', 'disabled', 'error'}:
        reasons.append('ACCOUNT_DISCONNECTED')
    elif account.get('status') not in {'connected', 'active', 'ready'}:
        unknown.append('ACCOUNT_HEALTH_UNKNOWN')
    if not adapter:
        reasons.append('ADAPTER_MISSING')
    else:
        try:
            readiness = adapter.get_status().get('publish_ready')
            if readiness is False:
                reasons.append('ADAPTER_DISABLED')
            elif readiness is not True:
                unknown.append('ADAPTER_READINESS_UNKNOWN')
            checker = getattr(adapter, 'get_account_readiness', None)
            if checker is None:
                unknown.append('ACCOUNT_READINESS_UNKNOWN')
            else:
                account_ready = checker(account_id).get('ready')
                if account_ready is False:
                    reasons.append('ACCOUNT_CREDENTIAL_OR_SCOPE_INVALID')
                elif account_ready is not True:
                    unknown.append('ACCOUNT_READINESS_UNKNOWN')
        except Exception:
            unknown.append('READINESS_UNAVAILABLE')
    if not token or not token.get('access_token'):
        reasons.append('CREDENTIAL_MISSING')
    elif token.get('provider') not in ({'facebook', 'meta'} if platform == 'facebook' else {platform}):
        reasons.append('CREDENTIAL_PROVIDER_MISMATCH')
    elif not token.get('expires_at'):
        unknown.append('CREDENTIAL_EXPIRY_UNKNOWN')
    else:
        try:
            if stamp(token['expires_at']) <= now():
                reasons.append('CREDENTIAL_EXPIRED')
        except (TypeError, ValueError):
            unknown.append('CREDENTIAL_EXPIRY_UNKNOWN')
    return reasons, unknown


def evaluate(conn, payload, signals, *, exclude_task=None):
    """Use caller's transaction for cadence reservations and asset consistency."""
    hard, review = map(list, signals)
    controls = conn.execute('SELECT * FROM intelligence_autonomy_settings WHERE id=1').fetchone()
    if not controls or controls['kill_switch_active']:
        hard.append('KILL_SWITCH_ACTIVE')
    if not controls or not controls['autonomy_enabled']:
        review.append('AUTONOMY_DISABLED')
    platform, account_id, asset_id = payload['platform'], payload['account_id'], payload['asset_id']
    account = conn.execute('SELECT platform,status FROM accounts WHERE id=?', (account_id,)).fetchone()
    if not account or account['platform'] != platform:
        hard.append('ACCOUNT_PLATFORM_MISMATCH')
    elif account['status'] not in {'connected', 'active', 'ready'}:
        review.append('ACCOUNT_NOT_READY')
    if platform not in CADENCE:
        hard.append('PLATFORM_NOT_V1')
    asset = conn.execute('SELECT * FROM video_assets WHERE asset_id=?', (asset_id,)).fetchone()
    fingerprint = None
    if not asset:
        hard.append('ASSET_MISSING')
    elif asset['status'] != 'ready':
        hard.append('ASSET_NOT_READY')
    else:
        try:
            result, output, source_fp = _load_source(conn, int(asset['production_result_id']))
            check = _quality_row(conn, result['id'])
            if not check or check['status'] != 'PASS' or check['source_fingerprint'] != source_fp:
                raise ValueError()
            _binding(conn, result, check)
            if result['asset_id'] != asset_id or not asset['video_id']:
                raise ValueError()
            fingerprint = hashlib.sha256((source_fp + str(check['id']) + asset_id).encode()).hexdigest()
        except (ValueError, TypeError, KeyError):
            hard.append('QUALITY_NOT_PASS_OR_SOURCE_DRIFT')
        except sqlite3.OperationalError:
            review.append('QUALITY_HISTORY_UNAVAILABLE')
    rows = conn.execute('SELECT * FROM publish_tasks WHERE platform=? AND account_id=?', (platform, account_id)).fetchall()
    same = [r for r in rows if r['asset_id'] == asset_id]
    if len(same) > 1:
        hard.append('DUPLICATE_LEGACY_HISTORY')
    elif any(r['id'] != exclude_task for r in same):
        hard.append('DUPLICATE_PUBLISH')
    current = now()
    schedule = payload.get('scheduled_time')
    if schedule:
        try:
            if stamp(schedule) > current:
                review.append('FUTURE_SCHEDULE')
        except (TypeError, ValueError):
            hard.append('INVALID_SCHEDULE')
    interval, daily_max = CADENCE.get(platform, (3600, 3))
    dates = []
    for row in rows:
        if row['id'] == exclude_task:
            continue
        # Reservations, ambiguous writes and published history consume capacity.
        if row['status'] in {'pending', 'publishing', 'published', 'review'} or row['execution_claim']:
            try:
                # Use the last write/completion for executed tasks, not their
                # potentially much older creation or initial download time.
                last_activity = row['updated_at'] if row['execution_claim'] or row['status'] == 'published' else None
                dates.append(stamp(last_activity or row['execution_started_at'] or row['created_at']))
            except (TypeError, ValueError):
                review.append('HISTORY_TIME_UNKNOWN')
    if any((current - d).total_seconds() < interval for d in dates):
        hard.append('MINIMUM_INTERVAL')
    if sum(d.date() == current.date() for d in dates) >= daily_max:
        hard.append('DAILY_MAXIMUM')
    return {'policy_version': POLICY_VERSION, 'stage': 'publish',
            'decision': 'BLOCK' if hard else 'REVIEW' if review else 'AUTO',
            'reason_codes': sorted(set(hard + review)) or ['AUTO_ELIGIBLE'],
            'source_fingerprint': fingerprint, 'evaluated_at': current.isoformat(),
            'minimum_interval_seconds': interval, 'daily_maximum': daily_max}


def prepare_autonomous_publish_task(task):
    """Only AUTO materializes; BEGIN IMMEDIATE serializes cadence + identity."""
    payload = PublishTask(**dict(task)).model_dump()
    payload['platform'] = payload['platform'].strip().lower()
    if not payload.get('asset_id') or payload.get('account_id') is None:
        raise ValueError('Canonical asset_id and account_id required')
    manager._init_db()
    init_quality_table()
    signals = runtime_signals(payload['platform'], payload['account_id'])
    conn = manager._connect()
    try:
        conn.execute('BEGIN IMMEDIATE')
        decision = evaluate(conn, payload, signals)
        if decision['decision'] != 'AUTO':
            return {'created': False, 'task': None, 'policy': decision}
        asset = conn.execute('SELECT video_id FROM video_assets WHERE asset_id=?', (payload['asset_id'],)).fetchone()
        if payload.get('video_id') not in (None, asset['video_id']):
            raise ValueError('Content identity mismatch')
        payload['video_id'] = asset['video_id']
        decision['task_fingerprint'] = task_fingerprint(payload)
        timestamp = now().isoformat()
        row = conn.execute('''INSERT INTO publish_tasks(asset_id,video_id,platform,account_id,status,
            scheduled_time,title,description,tags,privacy_status,created_at,updated_at,
            autonomous_policy_version,policy_evidence) VALUES(?,?,?,?,'pending',?,?,?,?,?,?,?,?,?)''',
            (payload['asset_id'], asset['video_id'], payload['platform'], payload['account_id'],
             payload.get('scheduled_time'), payload.get('title'), payload.get('description') or '',
             json.dumps(payload.get('tags') or []), payload.get('privacy_status') or 'private',
             timestamp, timestamp, POLICY_VERSION, json.dumps(decision)))
        stored = manager._serialize(conn.execute('SELECT * FROM publish_tasks WHERE id=?', (row.lastrowid,)).fetchone())
        conn.commit()
        return {'created': True, 'task': stored, 'policy': decision}
    finally:
        conn.close()
