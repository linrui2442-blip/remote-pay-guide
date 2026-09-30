"""G4-D provider-neutral technical quality and atomic asset finalization."""
import hashlib
import json
import math
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from assets.manager import _init_db as init_assets
from assets.remote_media import MediaFailure, MediaProbe, RemoteMedia
from data.database_path import database_path

POLICY_VERSION = 'g4d-v1'


def _now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect():
    conn = sqlite3.connect(database_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_quality_table():
    init_assets()
    with _connect() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS asset_quality_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            production_result_id INTEGER NOT NULL,
            policy_version TEXT NOT NULL, source_fingerprint TEXT NOT NULL,
            status TEXT NOT NULL, reason_codes TEXT NOT NULL, evidence TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )''')
        duplicates = conn.execute('SELECT production_result_id FROM asset_quality_checks GROUP BY production_result_id HAVING COUNT(*) > 1').fetchall()
        if not duplicates:
            conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS uq_asset_quality_result ON asset_quality_checks(production_result_id) WHERE production_result_id IS NOT NULL')


def _load_source(conn, result_id):
    row = conn.execute('SELECT * FROM production_results WHERE id=?', (result_id,)).fetchone()
    if not row or row['status'] != 'completed' or row['provider'] not in {'github', 'ai_gateway'}:
        raise ValueError('Completed supported ProductionResult required')
    job = conn.execute('SELECT * FROM runtime_jobs WHERE id=?', (row['runtime_job_id'],)).fetchone()
    task = conn.execute('SELECT * FROM production_tasks WHERE id=?', (job['task_id'],)).fetchone() if job else None
    if (not job or not task or job['provider'] != row['provider'] or task['provider'] != row['provider']
            or job['status'] != 'completed' or task['status'] != 'completed'):
        raise ValueError('ProductionResult runtime/task linkage invalid')
    if conn.execute('SELECT COUNT(*) FROM production_results WHERE runtime_job_id=?', (job['id'],)).fetchone()[0] != 1:
        raise ValueError('Duplicate ProductionResult history')
    if conn.execute('SELECT COUNT(*) FROM runtime_jobs WHERE task_id=?', (task['id'],)).fetchone()[0] != 1:
        raise ValueError('Duplicate RuntimeJob history')
    try:
        output = json.loads(row['output'] or '{}')
        params = json.loads(task['parameters'] or '{}')
    except (TypeError, ValueError):
        raise ValueError('Invalid production source contract') from None
    if not isinstance(output, dict) or not (output.get('defer_asset_binding') or output.get('g4b_no_asset_binding')):
        raise ValueError('Deferred ProductionResult required')
    if not row['video_id'] or (params.get('content_id') and params['content_id'] != row['video_id']):
        raise ValueError('Production content identity mismatch')
    source = {'result_id': result_id, 'runtime_job_id': job['id'], 'task_id': task['id'],
              'video_id': row['video_id'], 'provider': row['provider'], 'output': output}
    fingerprint = hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    return row, output, fingerprint


def _quality_row(conn, result_id):
    rows = conn.execute('SELECT * FROM asset_quality_checks WHERE production_result_id=?', (result_id,)).fetchall()
    if len(rows) > 1:
        raise ValueError('Duplicate quality history; review required')
    return rows[0] if rows else None


def _binding(conn, result, check):
    assets = conn.execute('SELECT * FROM video_assets WHERE production_result_id=?', (str(result['id']),)).fetchall()
    if len(assets) > 1:
        raise ValueError('Duplicate legacy assets; history preserved')
    if check and check['status'] == 'PASS':
        expected = f"asset-result-{result['id']}"
        output = json.loads(result['output'])
        if (len(assets) != 1 or result['asset_id'] != expected or result['asset_status'] != 'ready'
                or assets[0]['asset_id'] != expected or assets[0]['status'] != 'ready'
                or assets[0]['video_id'] != result['video_id']
                or assets[0]['source_provider'] != result['provider']
                or assets[0]['storage_type'] != ('github_pages' if result['provider'] == 'github' else 'ai_output')
                or assets[0]['file_path'] is not None
                or assets[0]['asset_url'] != output.get('asset_url')):
            raise ValueError('Quality PASS asset binding inconsistent')
        metadata = json.loads(assets[0]['metadata'] or '{}')
        if (metadata.get('quality_check_id') != check['id'] or metadata.get('quality_policy_version') != POLICY_VERSION
                or metadata.get('quality_decision') != 'PASS'):
            raise ValueError('Quality asset provenance inconsistent')
    elif assets or result['asset_id']:
        raise ValueError('Existing asset binding requires review')


def _readback(conn, result_id):
    row = dict(_quality_row(conn, result_id))
    row['reason_codes'] = json.loads(row['reason_codes'])
    row['evidence'] = json.loads(row['evidence'])
    result = conn.execute('SELECT asset_id,asset_status,status FROM production_results WHERE id=?', (result_id,)).fetchone()
    return {**row, 'asset_id': result['asset_id'], 'asset_status': result['asset_status'],
            'production_result_status': result['status']}


def _technical_evidence(data):
    try:
        streams = data['streams']
        if not isinstance(streams, list):
            raise ValueError()
        videos = [s for s in streams if s.get('codec_type') == 'video']
        if not videos:
            raise MediaFailure('BLOCK', 'NO_VIDEO_STREAM')
        video = videos[0]
        duration = float(data['format']['duration'])
        width, height = int(video['width']), int(video['height'])
        if not math.isfinite(duration) or not 3 <= duration <= 180:
            raise MediaFailure('BLOCK', 'BAD_DURATION')
        if width < 360 or height < 640:
            raise MediaFailure('BLOCK', 'BAD_DIMENSIONS')
        aspect = width / height
        if not 0.50 <= aspect <= 0.65:
            raise MediaFailure('BLOCK', 'BAD_ASPECT')
        container, codec = data['format']['format_name'], video['codec_name']
        # Persist only bounded technical identifiers, not raw ffprobe output.
        if not all(isinstance(v, str) and re.fullmatch(r'[a-z0-9_,.-]{1,80}', v) for v in (container, codec)):
            raise ValueError()
        if not set(container.split(',')) & {'mov', 'mp4', 'm4a', '3gp', '3g2', 'mj2', 'matroska', 'webm'}:
            raise ValueError()
        return {'container': container, 'duration_seconds': duration, 'width': width, 'height': height,
                'aspect_ratio': aspect, 'video_codec': codec,
                'audio_stream_present': any(s.get('codec_type') == 'audio' for s in streams),
                'probe_method': 'ffprobe'}
    except MediaFailure:
        raise
    except (TypeError, ValueError, KeyError, AttributeError, OverflowError):
        raise MediaFailure('BLOCK', 'MALFORMED_MEDIA') from None


def evaluate_production_result_asset(result_id, *, downloader=None, probe=None, before_binding=None):
    """Evaluate either provider; all HTTP/probe I/O is outside transactions.

    Concurrent read-only inspections are permitted. Unique indexes and one
    final transaction enforce exactly one quality row and asset/binding.
    """
    if isinstance(result_id, bool) or not str(result_id).isdigit() or int(result_id) < 1:
        raise ValueError('Valid ProductionResult id required')
    result_id = int(result_id)
    init_quality_table()
    with _connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        result, output, fingerprint = _load_source(conn, result_id)
        check = _quality_row(conn, result_id)
        _binding(conn, result, check)
        if check:
            if check['source_fingerprint'] != fingerprint or check['policy_version'] != POLICY_VERSION:
                raise ValueError('Quality source or policy drift; review required')
            if check['status'] in {'PASS', 'BLOCK'}:
                return _readback(conn, result_id)
        else:
            now = _now()
            conn.execute('INSERT INTO asset_quality_checks(production_result_id,policy_version,source_fingerprint,status,reason_codes,evidence,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                         (result_id, POLICY_VERSION, fingerprint, 'REVIEW', '["EVALUATION_PENDING"]', '{}', now, now))
    url = output.get('asset_url')
    storage = 'github_pages' if result['provider'] == 'github' else 'ai_output'
    evidence = {'policy_version': POLICY_VERSION, 'source_provider': result['provider'], 'storage_type': storage,
                'source_url_fingerprint': hashlib.sha256(str(url or '').encode()).hexdigest(), 'checked_at': _now()}
    decision, reasons = 'PASS', []
    try:
        if result['provider'] == 'github' and output.get('storage_type') != 'github_pages':
            raise MediaFailure('BLOCK', 'INVALID_GITHUB_STORAGE')
        with (downloader or RemoteMedia()).download(url, storage_type=storage) as media:
            evidence.update(content_type=media.content_type, bytes=media.size, source_host=media.host)
            evidence.update(_technical_evidence((probe or MediaProbe()).inspect(media.path)))
    except MediaFailure as exc:
        decision, reasons = exc.decision, [exc.reason]
    except Exception:
        # Never persist subprocess/network exception text or signed URLs.
        decision, reasons = 'REVIEW', ['INSPECTION_UNAVAILABLE']

    with _connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        result, current_output, current_fingerprint = _load_source(conn, result_id)
        check = _quality_row(conn, result_id)
        if not check or current_fingerprint != fingerprint or check['source_fingerprint'] != fingerprint or check['policy_version'] != POLICY_VERSION:
            raise ValueError('Quality source drift during inspection')
        _binding(conn, result, check)
        if check['status'] in {'PASS', 'BLOCK'}:
            return _readback(conn, result_id)
        now = _now()
        if decision == 'PASS':
            asset_id = f'asset-result-{result_id}'
            metadata = {'quality_policy_version': POLICY_VERSION, 'quality_check_id': check['id'],
                        'quality_decision': 'PASS', 'quality_evidence': evidence}
            conn.execute('''INSERT INTO video_assets(asset_id,video_id,production_result_id,source_provider,storage_type,
                asset_url,file_path,status,metadata,created_at,updated_at,source,location)
                VALUES(?,?,?,?,?,?,NULL,'ready',?,?,?,?,?)''',
                         (asset_id, result['video_id'], str(result_id), result['provider'], storage, url,
                          json.dumps(metadata), now, now, result['provider'], url))
            if before_binding:
                before_binding()
            conn.execute("UPDATE production_results SET asset_id=?,asset_status='ready',updated_at=? WHERE id=?",
                         (asset_id, now, result_id))
        else:
            conn.execute('UPDATE production_results SET asset_status=?,updated_at=? WHERE id=?',
                         ('review' if decision == 'REVIEW' else 'blocked', now, result_id))
        conn.execute('UPDATE asset_quality_checks SET status=?,reason_codes=?,evidence=?,attempts=attempts+1,updated_at=? WHERE id=?',
                     (decision, json.dumps(reasons), json.dumps(evidence), now, check['id']))
        return _readback(conn, result_id)
