from intelligence.content_brain import get_plan, update_plan, set_plan_status, ContentPlan
from intelligence.novelty import evaluate_content_plan_novelty
from intelligence.production_spec import build_production_spec
from intelligence.task_generator import generate_production_task

def evaluate_and_persist_novelty(plan_id):
    p=get_plan(plan_id)
    if not p: raise KeyError('plan not found')
    n=evaluate_content_plan_novelty(ContentPlan(**p['plan'])); n['evaluated_revision']=p.get('revision',1)
    payload=dict(p['plan']); payload['novelty_status']=n['decision']; payload['novelty_evidence']=n
    return update_plan(plan_id, {}) if False else _write(plan_id,payload,p)

def _write(plan_id,payload,p):
    import sqlite3,json; from data.database_path import database_path
    c=sqlite3.connect(database_path()); c.execute('UPDATE intelligence_content_plans SET payload_json=? WHERE id=?',(json.dumps(payload,ensure_ascii=False),plan_id)); c.commit(); c.close(); return get_plan(plan_id)

def approve_plan(plan_id):
    p=get_plan(plan_id)
    if not p: raise KeyError('plan not found')
    n=p['plan'].get('novelty_status')
    if n not in ('PASS','WARN'):
        p=evaluate_and_persist_novelty(plan_id); n=p['plan'].get('novelty_status')
    if n=='BLOCK': raise ValueError('content novelty blocked')
    return set_plan_status(plan_id,'approved')

def materialize_plan(plan_id, failure_hook=None):
    p=get_plan(plan_id)
    if not p: raise KeyError('plan not found')
    if p['status']!='approved' or p.get('approved_revision')!=p.get('revision'): raise ValueError('revision approval conflict')
    payload=dict(p['plan']); spec=build_production_spec(ContentPlan(**payload)); key=f'content-plan:{plan_id}:revision:{p.get("revision",1)}'
    params=dict(spec); params.update({'idempotency_key':key,'content_plan_id':plan_id,'content_plan_revision':p.get('revision',1),'script':payload['script']})
    task=generate_production_task({'provider_suggestion':'github','objective':payload['topic'],'workflow':spec['workflow'],'branch':'main','task_type':'video_batch','parameters':params})
    if failure_hook: failure_hook()
    set_plan_status(plan_id,'materialized'); return task
