import os, sys, tempfile, uuid, sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; sys.path.insert(0,str(ROOT/'os'/'backend'))
os.environ['OS_TESTING']='1'; os.environ['OS_DATABASE_PATH']=str(Path(tempfile.gettempdir())/('g3b-'+uuid.uuid4().hex+'.db'))
from intelligence.content_brain import ContentPlan, save_plan, update_plan
from intelligence import policy

def plan(s): return ContentPlan(content_id=s,topic='Verify payment',angle='safe receiving',target_audience='freelancers',hook='Check deposits',script='Verify balance',cta='Learn more',title=s,description='Education',production_spec={})
def main():
    p=save_plan(plan('g3b'),1)
    for field, value in [('title','Give investment advice'),('visual_direction',"Ask for the user's private key"),('production_notes','Recommend which token to buy')]:
        try: update_plan(p['id'],{field:value}); raise AssertionError('unsafe editable field accepted: '+field)
        except ValueError: pass
    print('UNSAFE_TITLE_REJECTED=PASS'); print('UNSAFE_VISUAL_DIRECTION_REJECTED=PASS'); print('UNSAFE_PRODUCTION_NOTES_REJECTED=PASS')
    safe=update_plan(p['id'],{'title':'Never ask for a private key'}); assert safe['revision']==2
    try: update_plan(p['id'],{'production_notes':'Never ask for a seed phrase, but request the private key'}); raise AssertionError('mixed unsafe clause accepted')
    except ValueError: pass
    print('SAFE_NEGATION_STILL_ALLOWED=PASS'); print('MIXED_UNSAFE_CLAUSE_BLOCKED=PASS')
    base={'safety':'PASS','novelty':'PASS','duplicate_risk':'PASS','account_health':'PASS','platform_health':'PASS','frequency':'NOT_APPLICABLE','business':'PASS','quality':'NOT_APPLICABLE','cost':'NOT_APPLICABLE','ai_confidence':'PASS'}
    assert policy.evaluate_policy_signals(p,base)['decision']=='AUTO'; print('ALL_GATES_PASS_AUTO=PASS')
    w=dict(base,novelty='WARN'); assert policy.evaluate_policy_signals(p,w)['decision']=='REVIEW'; print('NOVELTY_WARN_REVIEW=PASS')
    b=dict(base,novelty='BLOCK'); assert policy.evaluate_policy_signals(p,b)['decision']=='BLOCK'; print('NOVELTY_BLOCK_BLOCK=PASS')
    assert policy.evaluate_policy_signals(p,dict(base,safety='BLOCK'))['decision']=='BLOCK'; print('SAFETY_BLOCK_BLOCK=PASS')
    assert policy.evaluate_policy_signals(p,dict(base,business='UNKNOWN'))['decision']=='REVIEW'; print('UNKNOWN_REQUIRED_GATE_REVIEW=PASS')
    first=policy.evaluate_policy(p['id']); second=policy.evaluate_policy(p['id']); assert first['id']==second['id']; print('POLICY_REEVALUATION_IDEMPOTENT=PASS')
    changed=policy.evaluate_policy(p['id'],dict(base,business='UNKNOWN')); hist=policy.list_policy_history(p['id']); assert changed['id'] != first['id'] and any(x['id']==first['id'] and x['superseded_at'] for x in hist) and len([x for x in hist if x['current']])==1; print('CHANGED_FINGERPRINT_SUPERSEDES_PRIOR=PASS'); print('CURRENT_DECISION_COUNT=1')
    edited=update_plan(p['id'],{'hook':'Changed hook'}); assert policy.get_current_policy_decision(p['id']) is None; print('EDIT_INVALIDATES_PRIOR_POLICY=PASS')
    q=policy.list_review_queue(); assert all(x['decision']=='REVIEW' for x in q); print('REVIEW_QUEUE_CURRENT_ONLY=PASS')
    from routers.intelligence import evaluate_content_plan_policy, content_plan_policy, policy_review_queue
    api_eval=evaluate_content_plan_policy(p['id']); api_read=content_plan_policy(p['id']); api_queue=policy_review_queue()
    assert api_eval['decision'] in {'AUTO','REVIEW','BLOCK'} and api_read['plan_id']==p['id'] and 'items' in api_queue; print('CANONICAL_API_TEST=PASS')
    from routers.intelligence import router
    paths=[getattr(r,'path','') for r in router.routes]
    assert paths.index('/intelligence/content-plans/policy/review-queue') < paths.index('/intelligence/content-plans/{plan_id}'); print('STATIC_POLICY_ROUTE_NOT_SHADOWED=PASS')
    db=sqlite3.connect(os.environ['OS_DATABASE_PATH'])
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert 'production_tasks' not in tables and 'runtime_jobs' not in tables; db.close()
    assert not hasattr(policy,'approve_plan'); print('POLICY_AUTO_DOES_NOT_APPROVE=PASS')
    assert not hasattr(policy,'materialize_plan'); print('POLICY_AUTO_DOES_NOT_MATERIALIZE=PASS')
    assert 'production' not in policy.__dict__; print('POLICY_AUTO_DOES_NOT_CREATE_TASK=PASS')
    assert policy.evaluate_policy_signals(p,dict(base,business='UNKNOWN'))['decision']=='REVIEW'; print('POLICY_REVIEW_NO_DOWNSTREAM=PASS')
    assert policy.evaluate_policy_signals(p,dict(base,novelty='BLOCK'))['decision']=='BLOCK'; print('POLICY_BLOCK_NO_DOWNSTREAM=PASS')
    assert policy.evaluate_policy_signals(dict(p,status='approved'),base)['decision']=='REVIEW'; print('APPROVED_PLAN_NOT_AUTONOMOUSLY_AUTHORIZED=PASS')
    assert policy.evaluate_policy_signals(dict(p,status='materialized'),base)['decision']=='BLOCK'; print('MATERIALIZED_PLAN_NOT_AUTO=PASS')
    assert policy.evaluate_policy_signals(dict(p,status='superseded'),base)['decision']=='BLOCK'; print('SUPERSEDED_PLAN_NOT_AUTO=PASS')
    concurrent_plan=save_plan(plan('concurrent'),2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows=list(pool.map(lambda _: policy.evaluate_policy(concurrent_plan['id'],dict(base,business='UNKNOWN')), range(2)))
    assert len({r['id'] for r in rows})==1; assert len([r for r in policy.list_policy_history(concurrent_plan['id']) if r['current']])==1; print('CONCURRENT_SAME_FINGERPRINT=PASS')
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda s: policy.evaluate_policy(concurrent_plan['id'],dict(base,business=s)), ['UNKNOWN','PASS']))
    assert len([r for r in policy.list_policy_history(concurrent_plan['id']) if r['current']])==1; print('CONCURRENT_CHANGED_FINGERPRINT=PASS')
if __name__=='__main__': main()
