from intelligence.content_brain import get_plan, update_plan, set_plan_status, ContentPlan
from intelligence.novelty import evaluate_content_plan_novelty
from intelligence.production_spec import build_production_spec
from intelligence.task_generator import generate_production_task
from production.tasks.manager import get_task_by_idempotency_key
from production.tasks.execution import get_execution_readiness

def evaluate_and_persist_novelty(plan_id):
    p=get_plan(plan_id)
    if not p: raise KeyError('plan not found')
    n=evaluate_content_plan_novelty(ContentPlan(**p['plan'])); n['evaluated_revision']=p.get('revision',1)
    payload=dict(p['plan']); payload['novelty_status']=n['decision']; payload['novelty_evidence']=n
    return _write(plan_id,payload,p)

def _write(plan_id,payload,p):
    import sqlite3,json; from data.database_path import database_path
    from datetime import datetime, timezone
    c=sqlite3.connect(database_path()); c.execute('UPDATE intelligence_content_plans SET payload_json=?,updated_at=? WHERE id=?',(json.dumps(payload,ensure_ascii=False),datetime.now(timezone.utc).isoformat(),plan_id)); c.commit(); c.close(); return get_plan(plan_id)

def approve_plan(plan_id):
    p=get_plan(plan_id)
    if not p: raise KeyError('plan not found')
    n=p['plan'].get('novelty_status'); ev=p['plan'].get('novelty_evidence') or {}
    if n not in ('PASS','WARN') or ev.get('evaluated_revision') != p.get('revision'):
        p=evaluate_and_persist_novelty(plan_id); n=p['plan'].get('novelty_status')
    if n=='BLOCK': raise ValueError('content novelty blocked')
    return set_plan_status(plan_id,'approved')

def materialize_plan(plan_id, failure_hook=None):
    p=get_plan(plan_id)
    if not p: raise KeyError('plan not found')
    key=f'content-plan:{plan_id}:revision:{p.get("revision",1)}'
    if p['status']=='materialized':
        task=get_task_by_idempotency_key(key)
        return _validate_materialized_task(task,plan_id,p.get('revision'),key)
    if p['status']!='approved' or p.get('approved_revision')!=p.get('revision'): raise ValueError('revision approval conflict')
    existing=get_task_by_idempotency_key(key)
    if existing:
        _validate_materialized_task(existing,plan_id,p.get('revision'),key)
        set_plan_status(plan_id,'materialized'); return existing
    payload=dict(p['plan']); spec=build_production_spec(ContentPlan(**payload))
    params=dict(spec); params.update({'idempotency_key':key,'content_plan_id':plan_id,'content_plan_revision':p.get('revision',1),'script':payload['script']})
    task=generate_production_task({'provider_suggestion':'github','objective':payload['topic'],'workflow':spec['workflow'],'branch':'main','task_type':'video_batch','parameters':params})
    _validate_materialized_task(task,plan_id,p.get('revision'),key)
    if not get_execution_readiness(task)['ready']: raise ValueError('production task is not executable')
    if failure_hook: failure_hook()
    latest=get_plan(plan_id)
    if latest['status']=='materialized': return _validate_materialized_task(get_task_by_idempotency_key(key),plan_id,p.get('revision'),key)
    import sqlite3
    from data.database_path import database_path
    with sqlite3.connect(database_path()) as c:
        cur=c.execute("UPDATE intelligence_content_plans SET status='materialized',updated_at=datetime('now') WHERE id=? AND status='approved' AND revision=? AND approved_revision=?",(plan_id,p.get('revision'),p.get('revision')))
        c.commit()
        if cur.rowcount==0:
            latest=get_plan(plan_id)
            if latest and latest['status']=='materialized': return _validate_materialized_task(get_task_by_idempotency_key(key),plan_id,p.get('revision'),key)
            raise ValueError('concurrent materialization conflict')
    return task
def _validate_materialized_task(task, plan_id, revision, key):
    if not task: raise ValueError('materialization task missing')
    p=task.parameters or {}
    if p.get('content_plan_id') != plan_id or p.get('content_plan_revision') != revision or p.get('idempotency_key') != key:
        raise ValueError('materialized task linkage invalid')
    if not get_execution_readiness(task).get('ready'): raise ValueError('materialized task not executable')
    return task
