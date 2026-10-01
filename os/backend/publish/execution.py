"""Durable G5 execution owner; no SQLite transaction crosses provider I/O.

An interrupted owner is never reassigned. Recovery is read-only or REVIEW.
Stage intents survive even when a POST response/correlation cannot be saved.
"""
import json
import re
import uuid
from contextlib import ExitStack
from types import SimpleNamespace

from publish import manager, policy
from publish.registry import get_adapter


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
