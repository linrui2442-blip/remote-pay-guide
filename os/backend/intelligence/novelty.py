import json, importlib.util, sqlite3
from pathlib import Path
from data.database_path import database_path
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('content_novelty',ROOT/'video-factory'/'content_novelty.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

def _canonical_production_history():
    """Read produced canonical plans without bootstrapping or mutating schema."""
    path = database_path()
    if not path.exists(): return []
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = conn.execute('''
            SELECT plan.id, plan.content_id, plan.payload_json
            FROM intelligence_content_plans plan
            WHERE plan.status='materialized'
              AND EXISTS (
                SELECT 1 FROM production_results result
                WHERE result.video_id=plan.content_id AND result.status='completed'
              )
            ORDER BY plan.id
        ''').fetchall()
    except sqlite3.Error:
        return []
    finally:
        if 'conn' in locals(): conn.close()
    history=[]
    for row in rows:
        try: payload=json.loads(row['payload_json'] or '{}')
        except (TypeError, ValueError, json.JSONDecodeError): continue
        history.append({
            'content_id': row['content_id'],
            'video_subject': f"{payload.get('topic','')} {payload.get('angle','')}".strip(),
            'video_script': '\n'.join(str(payload.get(key) or '') for key in ('hook','script','cta')),
        })
    return history

def novelty_history(candidate_content_id=None):
    by_identity={}
    for item in [*mod.scan_tasks(ROOT/'video-factory'), *_canonical_production_history()]:
        identity=str(item.get('content_id') or '').strip()
        if identity and identity != candidate_content_id: by_identity[identity]=item
    return [by_identity[key] for key in sorted(by_identity)]

def evaluate_content_plan_novelty(plan):
    histories=novelty_history(plan.content_id)
    candidate={'video_subject':f'{plan.topic} {plan.angle}','video_script':f'{plan.hook}\n{plan.script}\n{plan.cta}'}
    best=None
    result=mod.compare(candidate['video_subject'],candidate['video_script'],histories)
    return result
