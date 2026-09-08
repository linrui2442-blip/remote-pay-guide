from data.database_path import database_path
import hashlib
import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from accounts.manager import get_account
from data.growth import get_content_funnel
from data.query import query_data_center
from intelligence.feedback import analyze_feedback
from intelligence.strategy import build_production_strategy
from intelligence.task_generator import generate_production_task
from production.tasks.manager import get_tasks


DB_PATH = database_path()
DEFAULT_REFRESH_LIMIT = 50


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table():
    with _connect() as conn:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS intelligence_feedback_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                content_id TEXT NOT NULL,
                platform_video_id TEXT,
                snapshot_key TEXT NOT NULL,
                metric_collected_at TEXT,
                performance_score INTEGER NOT NULL DEFAULT 0,
                priority_score REAL NOT NULL DEFAULT 0,
                strategy_type TEXT,
                feedback_json TEXT NOT NULL,
                strategy_json TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                funnel_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(account_id, platform, content_id, snapshot_key)
            )
            '''
        )
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_intelligence_feedback_account '
            'ON intelligence_feedback_snapshots(account_id, platform, id)'
        )
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_intelligence_feedback_content '
            'ON intelligence_feedback_snapshots(content_id, id)'
        )
        conn.commit()


def _normalize_platform(value):
    return str(value or '').strip().lower()


def _json(value):
    return json.dumps(value or {}, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def _deserialize(row):
    if not row:
        return None
    data = dict(row)
    for source, target in (
        ('feedback_json', 'feedback'),
        ('strategy_json', 'strategy'),
        ('metrics_json', 'metrics_snapshot'),
        ('funnel_json', 'growth_funnel'),
    ):
        try:
            data[target] = json.loads(data.get(source) or '{}')
        except (TypeError, ValueError, json.JSONDecodeError):
            data[target] = {}
    return data


def _snapshot_key(row, funnel):
    stable = {
        'content_id': row.get('content_id'),
        'platform_video_id': row.get('platform_video_id'),
        'period_start': row.get('period_start'),
        'period_end': row.get('period_end'),
        'views': row.get('views'),
        'watch_time': row.get('watch_time'),
        'average_view_duration': row.get('average_view_duration'),
        'average_view_percentage': row.get('average_view_percentage'),
        'likes': row.get('likes'),
        'comments': row.get('comments'),
        'shares': row.get('shares'),
        'referral_clicks': row.get('referral_clicks'),
        'conversions': row.get('conversions'),
        'conversion_value': row.get('conversion_value'),
        'funnel': funnel,
    }
    return hashlib.sha256(_json(stable).encode('utf-8')).hexdigest()


def _priority_score(feedback):
    # Business outcomes dominate traffic metrics by design.
    return (
        float(feedback.conversion_value or 0) * 1_000_000
        + int(feedback.conversions or 0) * 100_000
        + int(feedback.referral_clicks or 0) * 10_000
        + int(feedback.intent_events or 0) * 1_000
        + int(feedback.performance_score or 0)
    )


def _save_snapshot(account_id, platform, row, funnel, feedback, strategy):
    _ensure_table()
    content_id = str(row.get('content_id') or row.get('video_id') or row.get('platform_video_id') or '')
    if not content_id:
        raise ValueError('content_id is required for intelligence feedback')

    snapshot_key = _snapshot_key(row, funnel)
    strategy_dict = asdict(strategy)
    feedback_dict = asdict(feedback)
    strategy_type = (strategy_dict.get('parameters') or {}).get('strategy_type')
    priority_score = _priority_score(feedback)

    with _connect() as conn:
        existing = conn.execute(
            '''
            SELECT * FROM intelligence_feedback_snapshots
            WHERE account_id=? AND platform=? AND content_id=? AND snapshot_key=?
            LIMIT 1
            ''',
            (account_id, platform, content_id, snapshot_key),
        ).fetchone()
        if existing:
            result = _deserialize(existing)
            result['created'] = False
            return result

        created_at = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            '''
            INSERT INTO intelligence_feedback_snapshots
            (account_id, platform, content_id, platform_video_id, snapshot_key,
             metric_collected_at, performance_score, priority_score, strategy_type,
             feedback_json, strategy_json, metrics_json, funnel_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                account_id,
                platform,
                content_id,
                row.get('platform_video_id'),
                snapshot_key,
                row.get('collected_at'),
                int(feedback.performance_score or 0),
                priority_score,
                strategy_type,
                _json(feedback_dict),
                _json(strategy_dict),
                _json(row),
                _json(funnel),
                created_at,
            ),
        )
        conn.commit()
        saved = conn.execute(
            'SELECT * FROM intelligence_feedback_snapshots WHERE id=?',
            (cursor.lastrowid,),
        ).fetchone()

    result = _deserialize(saved)
    result['created'] = True
    return result


def get_feedback_snapshot(snapshot_id):
    _ensure_table()
    with _connect() as conn:
        row = conn.execute(
            'SELECT * FROM intelligence_feedback_snapshots WHERE id=?',
            (int(snapshot_id),),
        ).fetchone()
    return _deserialize(row)


def get_latest_account_feedback(account_id, platform=None, limit=100):
    _ensure_table()
    normalized = _normalize_platform(platform) or None
    clauses = ['account_id=?']
    params = [account_id]
    if normalized:
        clauses.append('platform=?')
        params.append(normalized)
    where = ' AND '.join(clauses)
    limit = max(1, min(int(limit or 100), 1000))

    with _connect() as conn:
        rows = conn.execute(
            f'''
            SELECT snapshot.*
            FROM intelligence_feedback_snapshots snapshot
            JOIN (
                SELECT account_id, platform, content_id, MAX(id) AS max_id
                FROM intelligence_feedback_snapshots
                WHERE {where}
                GROUP BY account_id, platform, content_id
            ) latest ON latest.max_id = snapshot.id
            ORDER BY snapshot.priority_score DESC, snapshot.id DESC
            LIMIT ?
            ''',
            (*params, limit),
        ).fetchall()
    return [_deserialize(row) for row in rows]


def get_content_feedback_history(content_id, limit=100):
    _ensure_table()
    limit = max(1, min(int(limit or 100), 1000))
    with _connect() as conn:
        rows = conn.execute(
            '''
            SELECT * FROM intelligence_feedback_snapshots
            WHERE content_id=?
            ORDER BY id DESC
            LIMIT ?
            ''',
            (str(content_id), limit),
        ).fetchall()
    return [_deserialize(row) for row in rows]


def refresh_account_feedback(account_id, platform=None, limit=DEFAULT_REFRESH_LIMIT):
    account = get_account(account_id)
    if not account:
        raise LookupError('account not found')

    normalized = _normalize_platform(platform or account.get('platform'))
    if not normalized:
        raise ValueError('platform is required')
    account_platform = _normalize_platform(account.get('platform'))
    if account_platform and account_platform != normalized:
        raise ValueError(
            f'account {account_id} belongs to {account_platform}, not {normalized}'
        )

    view = query_data_center(
        account_id=account_id,
        platform=normalized,
        scope='active',
        sort_by='views',
        sort_direction='desc',
        limit=max(1, min(int(limit or DEFAULT_REFRESH_LIMIT), 200)),
    )

    snapshots = []
    generated = 0
    reused = 0
    for row in view.get('rows') or []:
        content_id = row.get('content_id') or row.get('video_id') or row.get('platform_video_id')
        if not content_id:
            continue
        funnel = get_content_funnel(content_id)
        feedback = analyze_feedback(
            {
                'video_id': content_id,
                'performance': row,
                'funnel': funnel,
            }
        )
        strategy = build_production_strategy(feedback)
        snapshot = _save_snapshot(
            account_id,
            normalized,
            row,
            funnel,
            feedback,
            strategy,
        )
        snapshots.append(snapshot)
        if snapshot.get('created'):
            generated += 1
        else:
            reused += 1

    snapshots.sort(
        key=lambda item: (float(item.get('priority_score') or 0), int(item.get('id') or 0)),
        reverse=True,
    )
    return {
        'account_id': account_id,
        'platform': normalized,
        'scope': 'active',
        'found': len(view.get('rows') or []),
        'generated': generated,
        'reused': reused,
        'top_strategy': snapshots[0] if snapshots else None,
        'snapshots': snapshots,
    }


def materialize_feedback_task(snapshot_id):
    """Explicitly convert one stored strategy snapshot into a ProductionTask.

    Sync/refresh only creates recommendations. This function is deliberately a
    separate user-action boundary and never schedules, runs, or publishes the
    resulting task. Repeating the same action reuses the existing task.
    """
    snapshot = get_feedback_snapshot(snapshot_id)
    if not snapshot:
        raise LookupError('intelligence feedback snapshot not found')

    target_snapshot_id = int(snapshot['id'])
    for task in get_tasks():
        parameters = task.parameters or {}
        if parameters.get('intelligence_snapshot_id') == target_snapshot_id:
            return {
                'created': False,
                'snapshot_id': target_snapshot_id,
                'production_task': asdict(task),
            }

    strategy = dict(snapshot.get('strategy') or {})
    parameters = dict(strategy.get('parameters') or {})
    parameters.update(
        {
            'intelligence_snapshot_id': target_snapshot_id,
            'intelligence_snapshot_key': snapshot.get('snapshot_key'),
            'source_account_id': snapshot.get('account_id'),
            'source_platform': snapshot.get('platform'),
            'source_content_id': snapshot.get('content_id'),
            'source_platform_video_id': snapshot.get('platform_video_id'),
        }
    )
    strategy['parameters'] = parameters
    task = generate_production_task(strategy)
    return {
        'created': True,
        'snapshot_id': target_snapshot_id,
        'production_task': asdict(task),
    }
