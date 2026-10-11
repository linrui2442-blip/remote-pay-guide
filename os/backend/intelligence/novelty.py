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
            '_canonical_id': row['id'],
            'content_id': row['content_id'],
            'topic': str(payload.get('topic') or ''),
            'angle': str(payload.get('angle') or ''),
            'hook': str(payload.get('hook') or ''),
            'visual_direction': str(payload.get('visual_direction') or ''),
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

def bounded_creative_history(candidate_content_id=None, limit=20):
    """Creative-only prompt context, newest canonical production first."""
    limit=max(1, min(int(limit or 20), 20))
    canonical=sorted(_canonical_production_history(), key=lambda item:item['_canonical_id'], reverse=True)
    legacy=[]
    for item in mod.scan_tasks(ROOT/'video-factory'):
        script=str(item.get('video_script') or '')
        legacy.append({
            'content_id': item.get('content_id'),
            'topic': str(item.get('video_subject') or ''),
            'angle': '',
            'hook': script.splitlines()[0][:500] if script else '',
            'visual_direction': '',
        })
    selected=[]; seen=set()
    for item in [*canonical, *sorted(legacy,key=lambda row:str(row.get('content_id') or ''))]:
        identity=str(item.get('content_id') or '').strip()
        if not identity or identity == candidate_content_id or identity in seen: continue
        seen.add(identity)
        selected.append({key:str(item.get(key) or '') for key in
                         ('content_id','topic','angle','hook','visual_direction')})
        if len(selected) == limit: break
    return selected

def evaluate_content_plan_novelty(plan):
    histories=novelty_history(plan.content_id)
    candidate={'video_subject':f'{plan.topic} {plan.angle}','video_script':f'{plan.hook}\n{plan.script}\n{plan.cta}'}
    best=None
    result=mod.compare(candidate['video_subject'],candidate['video_script'],histories)
    return result
