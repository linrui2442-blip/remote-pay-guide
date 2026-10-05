"""Durable G5 execution owner; no SQLite transaction crosses provider I/O.

An interrupted owner is never reassigned. Recovery is read-only or REVIEW.
Stage intents survive even when a POST response/correlation cannot be saved.
"""
import json
import hashlib
import re
import uuid
from contextlib import ExitStack
from datetime import timedelta
from types import SimpleNamespace

from publish import manager, policy
from publish.registry import get_adapter


def _human_identity(conn, task):
    """Validate the existing G4-D binding and fingerprint its immutable source."""
    from assets.quality import _binding, _load_source, _quality_row, POLICY_VERSION

    asset = conn.execute('SELECT * FROM video_assets WHERE asset_id=?', (task['asset_id'],)).fetchone()
    if not asset or asset['status'] != 'ready' or asset['video_id'] != task['video_id']:
        raise ValueError('HUMAN_ASSET_NOT_READY')
    result, _, source = _load_source(conn, int(asset['production_result_id']))
    quality = _quality_row(conn, result['id'])
    if (not quality or quality['status'] != 'PASS' or quality['policy_version'] != POLICY_VERSION
            or quality['source_fingerprint'] != source):
        raise ValueError('HUMAN_QUALITY_NOT_PASS_OR_SOURCE_DRIFT')
    _binding(conn, result, quality)
    if result['asset_id'] != asset['asset_id']:
        raise ValueError('HUMAN_ASSET_BINDING_DRIFT')
    fields = (asset['asset_id'], asset['video_id'], asset['source_provider'],
              asset['storage_type'], asset['asset_url'], asset['status'],
              asset['production_result_id'], source, quality['id'])
    return hashlib.sha256(json.dumps(fields, separators=(',', ':')).encode()).hexdigest()


def _human_current(conn, task_id, owner, task_fingerprint, source_fingerprint):
    current = manager._serialize(conn.execute('SELECT * FROM publish_tasks WHERE id=?', (task_id,)).fetchone())
    evidence = json.loads(current.get('policy_evidence') or '{}') if current else {}
    if (not current or current['execution_claim'] != owner or current['status'] != 'publishing'
            or current.get('autonomous_policy_version') is not None
            or policy.task_fingerprint(current) != task_fingerprint
            or evidence.get('human_task_fingerprint') != task_fingerprint
            or evidence.get('human_source_fingerprint') != source_fingerprint
            or _human_identity(conn, current) != source_fingerprint):
        raise ValueError('HUMAN_OWNER_OR_SOURCE_CHANGED')
    return current


def _human_finalize(conn, current, owner, source_fingerprint):
    task_id = current['id']
    evidence = json.loads(current.get('policy_evidence') or '{}')
    if (evidence.get('human_task_fingerprint') != policy.task_fingerprint(current)
            or evidence.get('human_source_fingerprint') != source_fingerprint):
        raise ValueError('HUMAN_CLAIM_IDENTITY_DRIFT')
    rows = conn.execute("""SELECT operation_id FROM publish_operation_events
        WHERE task_id=? AND claim=? AND operation_status='PUBLISHED'""",
        (task_id, owner)).fetchall()
    ids = {row['operation_id'] for row in rows}
    if not conn.execute("""SELECT 1 FROM publish_operation_events WHERE task_id=?
            AND claim=? AND operation_status='SESSION_CREATED' LIMIT 1""", (task_id, owner)).fetchone():
        raise ValueError('HUMAN_SESSION_EVIDENCE_MISSING')
    if not conn.execute("""SELECT 1 FROM publish_write_intents WHERE task_id=?
            AND claim=? AND stage='youtube_initialize' LIMIT 1""", (task_id, owner)).fetchone():
        raise ValueError('HUMAN_INITIALIZE_INTENT_MISSING')
    if not conn.execute("""SELECT 1 FROM publish_write_intents WHERE task_id=?
            AND claim=? AND stage LIKE 'youtube_chunk_%' LIMIT 1""", (task_id, owner)).fetchone():
        raise ValueError('HUMAN_CHUNK_INTENT_MISSING')
    if (len(rows) != 1 or len(ids) != 1 or _human_identity(conn, current) != source_fingerprint):
        raise ValueError('HUMAN_PUBLISHED_EVIDENCE_AMBIGUOUS')
    video_id = ids.pop()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', video_id):
        raise ValueError('HUMAN_VIDEO_ID_INVALID')
    if current['provider_operation_status'] != 'PUBLISHED' or current['provider_operation_id'] != video_id:
        raise ValueError('HUMAN_PROVIDER_CORRELATION_DRIFT')
    url = f'https://www.youtube.com/watch?v={video_id}'
    conn.execute("""UPDATE publish_tasks SET status='published',platform_video_id=?,
        published_url=?,error_message=NULL,updated_at=? WHERE id=? AND execution_claim=?
        AND status IN ('publishing','review')""",
        (video_id, url, policy.now().isoformat(), task_id, owner))
    _event(conn, task_id, 'published', video_id, url)


_PREWRITE_STAGES = frozenset({'ASSET_DOWNLOAD', 'CREDENTIAL_BUILD',
    'AUTHORIZED_SESSION_BUILD', 'VIDEO_PATH_VALIDATION', 'INITIALIZE_INTENT'})
_SAFE_ASSET_FAILURE_REASONS = frozenset({
    'MISSING_ASSET_URL', 'UNSAFE_ASSET_URL', 'DNS_UNAVAILABLE', 'NON_PUBLIC_ADDRESS',
    'REDIRECT_LIMIT_OR_MISSING_LOCATION', 'UNSAFE_REDIRECT',
    'REMOTE_TEMPORARILY_UNAVAILABLE', 'REMOTE_HTTP_REJECTED',
    'CONTENT_TYPE_REJECTED', 'ENCODED_BODY_REJECTED', 'INVALID_CONTENT_LENGTH',
    'MEDIA_TOO_SMALL', 'MEDIA_TOO_LARGE', 'EXTERNAL_TEMP_REQUIRED',
    'DOWNLOAD_TIMEOUT', 'INCOMPLETE_DOWNLOAD', 'REMOTE_FETCH_UNAVAILABLE',
})
_UNCLASSIFIED_ASSET_FAILURE = 'ASSET_DOWNLOAD_FAILURE_UNCLASSIFIED'


def _human_prewrite_failure(conn, task_id, owner, stage, reason=None):
    """Classify only a proven zero-write failure; preserve the original claim."""
    if stage not in _PREWRITE_STAGES:
        return False
    row = manager._serialize(conn.execute('SELECT * FROM publish_tasks WHERE id=?', (task_id,)).fetchone())
    if (not row or row['execution_claim'] != owner or row['status'] != 'publishing'
            or row.get('provider_operation_id') or row.get('provider_operation_status')
            or row.get('platform_video_id')
            or conn.execute('SELECT 1 FROM publish_write_intents WHERE task_id=? LIMIT 1', (task_id,)).fetchone()
            or conn.execute('SELECT 1 FROM publish_operation_events WHERE task_id=? LIMIT 1', (task_id,)).fetchone()):
        return False
    evidence = json.loads(row.get('policy_evidence') or '{}')
    try:
        if (evidence.get('human_task_fingerprint') != policy.task_fingerprint(row)
                or evidence.get('human_source_fingerprint') != _human_identity(conn, row)):
            return False
    except ValueError:
        return False
    code = 'HUMAN_PREWRITE_' + stage + '_FAILED'
    evidence['human_prewrite_failure'] = {'stage': stage, 'code': code,
                                          'at': policy.now().isoformat()}
    if stage == 'ASSET_DOWNLOAD':
        evidence['human_prewrite_failure']['reason'] = (
            reason if isinstance(reason, str) and reason in _SAFE_ASSET_FAILURE_REASONS
            else _UNCLASSIFIED_ASSET_FAILURE
        )
    conn.execute("""UPDATE publish_tasks SET status='review',error_message=?,policy_evidence=?,
        updated_at=? WHERE id=? AND execution_claim=? AND status='publishing'""",
        (code, json.dumps(evidence, separators=(',', ':')), policy.now().isoformat(), task_id, owner))
    return True


def execute_human_authorized_publish_task(task_id, *, credential_refresh_authorized=False,
                                          asset_resolver=None, before_finalization=None):
    """One explicit human authorization; never reassign an interrupted owner."""
    return _run_human_authorized_publish_task(task_id,
        credential_refresh_authorized=credential_refresh_authorized,
        asset_resolver=asset_resolver, before_finalization=before_finalization)


def resume_human_authorized_prewrite_publish_task(task_id, *, credential_refresh_authorized=False,
                                                  asset_resolver=None):
    """Resume the same human claim only when durable proof shows zero external writes."""
    return _run_human_authorized_publish_task(task_id,
        credential_refresh_authorized=credential_refresh_authorized,
        asset_resolver=asset_resolver, resume_prewrite=True)


def _run_human_authorized_publish_task(task_id, *, credential_refresh_authorized=False,
                                       asset_resolver=None, before_finalization=None,
                                       resume_prewrite=False):
    from oauth.manager import get_token
    from accounts.manager import get_account
    from publish.orchestrator import get_publish_account_readiness, get_publish_execution_readiness
    from assets.manager import get_asset_by_asset_id
    from assets.remote_media import RemoteMedia
    from events.manager import EventManager

    manager._init_db()
    EventManager(db_path=manager.database_path())
    task = manager.get_publish_task(task_id)
    if not task or task.get('autonomous_policy_version') is not None or task['platform'] != 'youtube':
        raise ValueError('Human YouTube PublishTask required')
    if not resume_prewrite and (task['execution_claim'] or task['status'] != 'pending'):
        return {'task': task, 'executed': False, 'recovery': 'READ_ONLY_OR_REVIEW'}
    if resume_prewrite and (not task['execution_claim'] or task['status'] != 'review'):
        raise ValueError('HUMAN_PREWRITE_RECOVERY_NOT_ELIGIBLE')
    if task['privacy_status'] != 'private':
        raise ValueError('HUMAN_YOUTUBE_PRIVATE_ONLY')
    if not get_publish_execution_readiness('youtube')['publish_ready']:
        raise ValueError('HUMAN_YOUTUBE_ADAPTER_NOT_READY')
    if not get_publish_account_readiness('youtube', task['account_id'])['ready']:
        raise ValueError('HUMAN_YOUTUBE_ACCOUNT_NOT_READY')
    account = get_account(task['account_id'])
    if not account or account['platform'] != 'youtube' or account['status'] not in {'connected', 'active', 'ready'}:
        raise ValueError('HUMAN_YOUTUBE_ACCOUNT_NOT_READY')
    token = get_token(task['account_id'])
    expiry = None
    if token and token.get('expires_at'):
        try:
            expiry = policy.stamp(token['expires_at'])
        except (TypeError, ValueError):
            pass
    if not credential_refresh_authorized and (not token or not token.get('access_token')
            or expiry is None or expiry <= policy.now() + timedelta(minutes=5)):
        raise ValueError('YOUTUBE_TOKEN_REFRESH_REQUIRES_EXPLICIT_AUTHORIZATION')
    owner = task['execution_claim'] if resume_prewrite else uuid.uuid4().hex
    db = manager._connect()
    try:
        db.execute('BEGIN IMMEDIATE')
        current = manager._serialize(db.execute('SELECT * FROM publish_tasks WHERE id=?', (task_id,)).fetchone())
        if resume_prewrite:
            if current['execution_claim'] != owner or current['status'] != 'review':
                raise ValueError('HUMAN_PREWRITE_RECOVERY_NOT_ELIGIBLE')
        elif current['execution_claim'] or current['status'] != 'pending':
            return {'task': current, 'executed': False, 'recovery': 'READ_ONLY_OR_REVIEW'}
        if (current.get('autonomous_policy_version') is not None or current['platform'] != 'youtube'
                or current['privacy_status'] != 'private' or current['account_id'] != task['account_id']):
            raise ValueError('HUMAN_TASK_CHANGED')
        if policy.task_fingerprint(current) != policy.task_fingerprint(task):
            raise ValueError('HUMAN_TASK_CHANGED')
        source_fingerprint = _human_identity(db, current)
        task_fingerprint = policy.task_fingerprint(current)
        if (db.execute('SELECT 1 FROM publish_write_intents WHERE task_id=? LIMIT 1', (task_id,)).fetchone()
                or db.execute('SELECT 1 FROM publish_operation_events WHERE task_id=? LIMIT 1', (task_id,)).fetchone()
                or current.get('provider_operation_id') or current.get('provider_operation_status')
                or current.get('platform_video_id')):
            raise ValueError('HUMAN_EXISTING_WRITE_INTENT_REVIEW_REQUIRED')
        timestamp = policy.now().isoformat()
        if resume_prewrite:
            evidence = json.loads(current.get('policy_evidence') or '{}')
            if (evidence.get('human_task_fingerprint') != task_fingerprint
                    or evidence.get('human_source_fingerprint') != source_fingerprint):
                raise ValueError('HUMAN_CLAIM_IDENTITY_DRIFT')
            updated = db.execute("""UPDATE publish_tasks SET status='publishing',updated_at=?
                WHERE id=? AND status='review' AND execution_claim=?""", (timestamp, task_id, owner))
        else:
            evidence = json.dumps({'human_task_fingerprint': task_fingerprint,
                                   'human_source_fingerprint': source_fingerprint})
            updated = db.execute("""UPDATE publish_tasks SET execution_claim=?,execution_started_at=?,
                policy_evidence=?,status='publishing',updated_at=? WHERE id=? AND status='pending' AND execution_claim IS NULL""",
                (owner, timestamp, evidence, timestamp, task_id))
        if updated.rowcount != 1:
            raise ValueError('HUMAN_CLAIM_CONFLICT')
        db.commit()
    finally:
        db.close()

    def before_write(stage):
        if not re.fullmatch(r'youtube_(?:initialize|chunk_[0-9]+|resume_probe_[0-9]+)', str(stage or '')):
            raise ValueError('HUMAN_INVALID_WRITE_STAGE')
        if (not get_publish_execution_readiness('youtube')['publish_ready']
                or not get_publish_account_readiness('youtube', task['account_id'])['ready']):
            raise ValueError('HUMAN_YOUTUBE_READINESS_CHANGED')
        account = get_account(task['account_id'])
        if not account or account['status'] not in {'connected', 'active', 'ready'}:
            raise ValueError('HUMAN_YOUTUBE_ACCOUNT_NOT_READY')
        conn = manager._connect()
        try:
            conn.execute('BEGIN IMMEDIATE')
            _human_current(conn, task_id, owner, task_fingerprint, source_fingerprint)
            conn.execute('INSERT INTO publish_write_intents(task_id,stage,claim,created_at) VALUES(?,?,?,?)',
                         (task_id, stage, owner, policy.now().isoformat()))
            conn.commit()  # Durable before the YouTube POST/PUT.
        finally:
            conn.close()
        # Recheck after the durable intent, before releasing the provider write.
        if (not get_publish_execution_readiness('youtube')['publish_ready']
                or not get_publish_account_readiness('youtube', task['account_id'])['ready']):
            raise ValueError('HUMAN_POST_INTENT_READINESS_CHANGED')
        account = get_account(task['account_id'])
        if not account or account['status'] not in {'connected', 'active', 'ready'}:
            raise ValueError('HUMAN_POST_INTENT_ACCOUNT_CHANGED')
        conn = manager._connect()
        try:
            _human_current(conn, task_id, owner, task_fingerprint, source_fingerprint)
            intent = conn.execute('SELECT claim FROM publish_write_intents WHERE task_id=? AND stage=?',
                                  (task_id, stage)).fetchone()
            if not intent or intent['claim'] != owner:
                raise ValueError('HUMAN_POST_INTENT_OWNER_CHANGED')
        finally:
            conn.close()

    def correlation(operation_id, state):
        if (state not in {'SESSION_CREATED', 'PUBLISHED'}
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', str(operation_id or ''))
                or (state == 'SESSION_CREATED' and not re.fullmatch(r'[a-f0-9]{64}', operation_id))):
            raise ValueError('HUMAN_INVALID_PROVIDER_CORRELATION')
        conn = manager._connect()
        try:
            conn.execute('BEGIN IMMEDIATE')
            _human_current(conn, task_id, owner, task_fingerprint, source_fingerprint)
            expected = 'youtube_initialize' if state == 'SESSION_CREATED' else 'youtube_chunk_%'
            if not conn.execute('SELECT 1 FROM publish_write_intents WHERE task_id=? AND claim=? AND stage LIKE ? LIMIT 1',
                                (task_id, owner, expected)).fetchone():
                raise ValueError('HUMAN_CORRELATION_WITHOUT_WRITE_INTENT')
            if state == 'PUBLISHED' and not conn.execute("""SELECT 1 FROM publish_operation_events
                    WHERE task_id=? AND claim=? AND operation_status='SESSION_CREATED' LIMIT 1""",
                    (task_id, owner)).fetchone():
                raise ValueError('HUMAN_PUBLISHED_WITHOUT_SESSION')
            timestamp = policy.now().isoformat()
            conn.execute('''UPDATE publish_tasks SET provider_operation_id=?,provider_operation_status=?,
                provider_operation_updated_at=?,updated_at=? WHERE id=? AND execution_claim=? AND status='publishing' ''',
                (operation_id, state, timestamp, timestamp, task_id, owner))
            conn.execute('''INSERT INTO publish_operation_events(task_id,operation_id,operation_status,claim,created_at)
                VALUES(?,?,?,?,?)''', (task_id, operation_id, state, owner, timestamp))
            conn.commit()
        finally:
            conn.close()

    prepared = None
    failure_stage = 'ASSET_DOWNLOAD'
    asset_failure_reason = None
    downloads = ExitStack()
    try:
        from assets.remote_media import MediaFailure
        try:
            asset = get_asset_by_asset_id(task['asset_id'])
            if asset_resolver is not None:
                prepared = asset_resolver.prepare(asset)
            else:
                media = downloads.enter_context(RemoteMedia().download(asset['asset_url'], storage_type=asset['storage_type']))
                prepared = SimpleNamespace(file_path=str(media.path), cleanup=lambda: None)
        except MediaFailure as error:
            asset_failure_reason = error.reason
            raise
        except Exception:
            asset_failure_reason = _UNCLASSIFIED_ASSET_FAILURE
            raise
        adapter = get_adapter('youtube')
        failure_stage = 'CREDENTIAL_BUILD'
        result = adapter.publish_video(
            asset, task['account_id'], video_path=prepared.file_path,
            title=task['title'] or task['video_id'], description=task['description'],
            tags=task['tags'], privacy_status='private', before_write=before_write,
            operation_callback=correlation,
            credential_refresh_authorized=credential_refresh_authorized,
        )
        failure_stage = result.get('failure_stage') if result.get('status') != 'published' else None
        if before_finalization:
            before_finalization()
        db = manager._connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            current = _human_current(db, task_id, owner, task_fingerprint, source_fingerprint)
            if result.get('status') == 'published' and result.get('video_id'):
                _human_finalize(db, current, owner, source_fingerprint)
            else:
                if not _human_prewrite_failure(db, task_id, owner, failure_stage, asset_failure_reason):
                    db.execute("UPDATE publish_tasks SET status='review',error_message='HUMAN_EXTERNAL_OUTCOME_REQUIRES_REVIEW',updated_at=? WHERE id=?",
                               (policy.now().isoformat(), task_id))
            db.commit()
        finally:
            db.close()
    except Exception:
        db = manager._connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            if not _human_prewrite_failure(db, task_id, owner, failure_stage, asset_failure_reason):
                db.execute("""UPDATE publish_tasks SET status='review',error_message='HUMAN_EXTERNAL_OUTCOME_REQUIRES_REVIEW',
                    updated_at=? WHERE id=? AND execution_claim=? AND status='publishing'""",
                    (policy.now().isoformat(), task_id, owner))
            db.commit()
        finally:
            db.close()
    finally:
        try:
            if prepared:
                prepared.cleanup()
        finally:
            downloads.close()
    return {'task': manager.get_publish_task(task_id), 'executed': True}


def reconcile_human_authorized_publish_task(task_id):
    """Local-only recovery from durable provider evidence; never call YouTube."""
    manager._init_db()
    from events.manager import EventManager
    EventManager(db_path=manager.database_path())
    conn = manager._connect()
    try:
        conn.execute('BEGIN IMMEDIATE')
        current = manager._serialize(conn.execute('SELECT * FROM publish_tasks WHERE id=?', (task_id,)).fetchone())
        if not current or current.get('autonomous_policy_version') is not None or current['platform'] != 'youtube':
            raise ValueError('Human YouTube PublishTask required')
        if current['status'] == 'published':
            return current
        if not current['execution_claim'] or current['status'] not in {'publishing', 'review'}:
            raise ValueError('Human publish claim required for recovery')
        try:
            source_fingerprint = _human_identity(conn, current)
            _human_finalize(conn, current, current['execution_claim'], source_fingerprint)
        except ValueError:
            conn.execute("UPDATE publish_tasks SET status='review',error_message='HUMAN_RECOVERY_REVIEW_REQUIRED',updated_at=? WHERE id=?",
                         (policy.now().isoformat(), task_id))
        conn.commit()
    finally:
        conn.close()
    return manager.get_publish_task(task_id)


def _recheck(task, conn, signals):
    decision = policy.evaluate(conn, task, signals, exclude_task=task['id'])
    old = json.loads(task['policy_evidence'] or '{}')
    if decision['source_fingerprint'] != old.get('source_fingerprint'):
        raise ValueError('G5_SOURCE_DRIFT')
    if policy.task_fingerprint(task) != old.get('task_fingerprint'):
        raise ValueError('G5_TASK_DRIFT')
    if decision['decision'] != 'AUTO':
        raise ValueError('G5_AUTHORIZATION_NOT_AUTO')
    return decision


def _finish(task_id, owner, status, *, video_id=None, url=None, reason=None):
    conn = manager._connect()
    try:
        conn.execute('BEGIN IMMEDIATE')
        updated = conn.execute("""UPDATE publish_tasks SET status=?,platform_video_id=COALESCE(?,platform_video_id),
            published_url=COALESCE(?,published_url),error_message=?,updated_at=?
            WHERE id=? AND execution_claim=? AND status='publishing'""",
            (status, video_id, url, reason, policy.now().isoformat(), task_id, owner))
        if updated.rowcount == 1:
            _event(conn, task_id, status, video_id, url)
        conn.commit()
    finally:
        conn.close()


def _event(conn, task_id, status, video_id, url):
    task = conn.execute('SELECT video_id,platform FROM publish_tasks WHERE id=?', (task_id,)).fetchone()
    conn.execute('''INSERT INTO events(event_type,source,entity_type,entity_id,payload,created_at)
        VALUES(?,'publish','video',?,?,?)''',
        ('publish.completed' if status == 'published' else 'publish.review', task['video_id'],
         json.dumps({'publish_task_id': task_id, 'platform': task['platform'],
                     'platform_video_id': video_id, 'published_url': url}), policy.now().isoformat()))


def execute_autonomous_publish_task(task_id, *, asset_resolver=None):
    manager._init_db()
    from events.manager import EventManager
    EventManager(db_path=manager.database_path())
    task = manager.get_publish_task(task_id)
    if not task or task.get('autonomous_policy_version') != policy.POLICY_VERSION:
        raise ValueError('Canonical g5-v1 PublishTask required')
    # Owner never changes, including after timeout/restart. No blind POST retry.
    if task['execution_claim'] or task['status'] != 'pending':
        return {'task': task, 'executed': False, 'recovery': 'READ_ONLY_OR_REVIEW'}
    signals = policy.runtime_signals(task['platform'], task['account_id'])
    owner = uuid.uuid4().hex
    conn = manager._connect()
    try:
        conn.execute('BEGIN IMMEDIATE')
        task = manager._serialize(conn.execute('SELECT * FROM publish_tasks WHERE id=?', (task_id,)).fetchone())
        if task['execution_claim'] or task['status'] != 'pending':
            return {'task': task, 'executed': False}
        try:
            _recheck(task, conn, signals)
        except ValueError:
            conn.execute("UPDATE publish_tasks SET status='review',error_message='G5_PRECLAIM_REVIEW' WHERE id=?", (task_id,))
            conn.commit()
            return {'task': manager._serialize(conn.execute('SELECT * FROM publish_tasks WHERE id=?', (task_id,)).fetchone()), 'executed': False}
        timestamp = policy.now().isoformat()
        conn.execute("UPDATE publish_tasks SET execution_claim=?,execution_started_at=?,status='publishing',updated_at=? WHERE id=?",
                     (owner, timestamp, timestamp, task_id))
        conn.commit()
    finally:
        conn.close()
    fingerprint = policy.task_fingerprint(task)

    def before_write(stage):
        if not re.fullmatch(r'[a-z0-9_-]{1,80}', stage):
            raise ValueError('Invalid publish stage')
        fresh_signals = policy.runtime_signals(task['platform'], task['account_id'])
        db = manager._connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            current = manager._serialize(db.execute('SELECT * FROM publish_tasks WHERE id=?', (task_id,)).fetchone())
            if current['execution_claim'] != owner or current['status'] != 'publishing' or policy.task_fingerprint(current) != fingerprint:
                raise ValueError('Publish owner or payload changed')
            _recheck(current, db, fresh_signals)
            db.execute('INSERT INTO publish_write_intents(task_id,stage,claim,created_at) VALUES(?,?,?,?)',
                       (task_id, stage, owner, policy.now().isoformat()))
            db.execute('UPDATE publish_tasks SET updated_at=? WHERE id=?', (policy.now().isoformat(), task_id))
            db.commit()
        finally:
            db.close()

        # The intent is durable before this fresh authorization read. Preserve
        # it on denial; an interrupted/denied stage never gets a new owner.
        fresh_signals = policy.runtime_signals(task['platform'], task['account_id'])
        db = manager._connect()
        try:
            current = manager._serialize(db.execute('SELECT * FROM publish_tasks WHERE id=?', (task_id,)).fetchone())
            if (not current or current['execution_claim'] != owner
                    or current['status'] != 'publishing'
                    or current.get('autonomous_policy_version') != policy.POLICY_VERSION
                    or policy.task_fingerprint(current) != fingerprint):
                raise ValueError('G5_POST_INTENT_OWNER_OR_TASK_CHANGED')
            intent = db.execute('SELECT claim FROM publish_write_intents WHERE task_id=? AND stage=?',
                                (task_id, stage)).fetchone()
            if not intent or intent['claim'] != owner:
                raise ValueError('G5_POST_INTENT_OWNER_CHANGED')
            _recheck(current, db, fresh_signals)
        finally:
            db.close()

    def correlation(operation_id, state):
        # Provider-supplied identifiers are bounded, never URLs/headers/tokens.
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', str(operation_id or '')) or not re.fullmatch(r'[A-Z0-9_]{1,80}', str(state or '')):
            raise ValueError('Invalid provider correlation')
        db = manager._connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            updated = db.execute('''UPDATE publish_tasks SET provider_operation_id=?,provider_operation_status=?,
                provider_operation_updated_at=?,updated_at=? WHERE id=? AND execution_claim=? AND status='publishing' ''',
                (operation_id, state, policy.now().isoformat(), policy.now().isoformat(), task_id, owner))
            if updated.rowcount != 1:
                raise ValueError('Publish owner no longer active')
            db.execute('''INSERT INTO publish_operation_events(task_id,operation_id,operation_status,claim,created_at)
                          VALUES(?,?,?,?,?)''', (task_id, operation_id, state, owner, policy.now().isoformat()))
            db.commit()
        finally:
            db.close()

    from assets.manager import get_asset_by_asset_id
    from assets.remote_media import RemoteMedia
    asset = get_asset_by_asset_id(task['asset_id'])
    adapter = get_adapter(task['platform'])
    prepared = None
    downloads = ExitStack()
    try:
        # Recheck after durable claim, even before a preparatory remote download.
        fresh_signals = policy.runtime_signals(task['platform'], task['account_id'])
        db = manager._connect()
        try:
            _recheck(task, db, fresh_signals)
        finally:
            db.close()
        options = {'before_write': before_write, 'operation_callback': correlation}
        if task['platform'] == 'youtube':
            if asset_resolver is not None:
                prepared = asset_resolver.prepare(asset)
            else:
                media = downloads.enter_context(RemoteMedia().download(asset['asset_url'], storage_type=asset['storage_type']))
                prepared = SimpleNamespace(file_path=str(media.path), cleanup=lambda: None)
            options.update(video_path=prepared.file_path, title=task['title'] or task['video_id'],
                           description=task['description'], tags=task['tags'], privacy_status=task['privacy_status'])
        elif task['platform'] == 'instagram':
            options.update(caption=task['description'] or task['title'] or '')
        else:
            options.update(title=task['title'] or '', description=task['description'])
        result = adapter.publish_video(asset, task['account_id'], **options)
        video_id = str(result.get('video_id') or '')
        if result.get('status') == 'published' and re.fullmatch(r'[A-Za-z0-9_-]{1,160}', video_id):
            # Construct URL locally; never persist arbitrary provider error/URL.
            url = f'https://www.youtube.com/watch?v={video_id}' if task['platform'] == 'youtube' else None
            _finish(task_id, owner, 'published', video_id=video_id, url=url)
        else:
            _finish(task_id, owner, 'review', reason='PROVIDER_TERMINAL_OR_AMBIGUOUS')
    except Exception:
        _finish(task_id, owner, 'review', reason='EXTERNAL_OPERATION_AMBIGUOUS_OR_CONTROL_CHANGED')
    finally:
        try:
            if prepared:
                prepared.cleanup()
        finally:
            downloads.close()
    return {'task': manager.get_publish_task(task_id), 'executed': True}


def reconcile_autonomous_publish_task(task_id):
    """Recover only durable successful response evidence; otherwise REVIEW.

No recovery upload, no lease reassignment, no remote mutation. Unknown operation
outcomes remain REVIEW, retaining all stage intents and provider correlation.
"""
    task = manager.get_publish_task(task_id)
    if not task or task.get('autonomous_policy_version') != policy.POLICY_VERSION:
        raise ValueError('Canonical g5 task required')
    if task['status'] == 'published':
        return task
    from events.manager import EventManager
    EventManager(db_path=manager.database_path())
    if task['execution_claim']:
        conn = manager._connect()
        try:
            conn.execute('BEGIN IMMEDIATE')
            current = manager._serialize(conn.execute('SELECT * FROM publish_tasks WHERE id=?', (task_id,)).fetchone())
            # A current executor must not be interrupted by an ordinary read.
            if current['status'] == 'publishing' and (policy.now() - policy.stamp(current['updated_at'])).total_seconds() < 900:
                return current
            evidence = conn.execute("""SELECT operation_id FROM publish_operation_events
                WHERE task_id=? AND claim=? AND operation_status='PUBLISHED'""", (task_id, current['execution_claim'])).fetchall()
            ids = {r['operation_id'] for r in evidence}
            old = json.loads(current['policy_evidence'] or '{}')
            # Reconciliation records an existing success even with controls off,
            # but never binds it to a changed task or a changed source.
            decision = policy.evaluate(conn, current, ([], []), exclude_task=task_id)
            unchanged = (policy.task_fingerprint(current) == old.get('task_fingerprint')
                         and decision['source_fingerprint'] == old.get('source_fingerprint')
                         and decision['source_fingerprint'] is not None
                         and 'DUPLICATE_LEGACY_HISTORY' not in decision['reason_codes'])
            if len(ids) == 1 and unchanged and current['status'] in {'publishing', 'review'}:
                media_id = ids.pop()
                url = f'https://www.youtube.com/watch?v={media_id}' if current['platform'] == 'youtube' else None
                conn.execute("UPDATE publish_tasks SET status='published',platform_video_id=?,published_url=?,error_message=NULL,updated_at=? WHERE id=?",
                             (media_id, url, policy.now().isoformat(), task_id))
                _event(conn, task_id, 'published', media_id, url)
            elif current['status'] == 'publishing':
                conn.execute("UPDATE publish_tasks SET status='review',error_message='INTERRUPTED_OWNER_REQUIRES_READ_ONLY_RECONCILIATION',updated_at=? WHERE id=?",
                             (policy.now().isoformat(), task_id))
            conn.commit()
        finally:
            conn.close()
    return manager.get_publish_task(task_id)
