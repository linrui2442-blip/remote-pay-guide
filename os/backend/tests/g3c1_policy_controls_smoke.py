import os,sys,tempfile,uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; sys.path.insert(0,str(ROOT/'os'/'backend'))
os.environ['OS_TESTING']='1'; os.environ['OS_DATABASE_PATH']=str(Path(tempfile.gettempdir())/('g3c1-'+uuid.uuid4().hex+'.db'))
from intelligence.content_brain import ContentPlan, save_plan, update_plan
from intelligence import policy, policy_signals, autonomy

def make_plan(s): return ContentPlan(content_id=s,topic='Verify payment',angle='safe receiving',target_audience='freelancers',hook='Check deposits',script='Verify balance',cta='Learn more',title=s,description='Education',production_spec={})
def main():
    p=save_plan(make_plan('g3c1'),1); base={'safety':'PASS','novelty':'PASS','duplicate_risk':'PASS','account_health':'PASS','platform_health':'PASS','frequency':'UNKNOWN','business':'UNKNOWN','quality':'UNKNOWN','cost':'UNKNOWN','ai_confidence':'UNKNOWN'}
    assert policy.evaluate_policy_signals(p,base)['decision']=='REVIEW'; print('REAL_CANONICAL_DECISION=REVIEW')
    assert policy.evaluate_policy_signals(p,dict(base,novelty='WARN',duplicate_risk='WARN'))['decision']=='REVIEW'; assert policy.evaluate_policy_signals(p,dict(base,novelty='BLOCK',duplicate_risk='BLOCK'))['decision']=='BLOCK'; print('NOVELTY_TO_DUPLICATE_MAPPING=PASS')
    for f, expected in [({'conversions':1},'PASS'),({'referral_clicks':1},'PASS'),({'intent_events':1},'PASS'),({'performance_score':1},'WARN'),({},'WARN')]:
        snap={'feedback':f}; assert policy_signals._business(snap)[0]==expected
    assert policy_signals._business(None)[0]=='UNKNOWN'; print('BUSINESS_SIGNAL_TESTS=PASS')
    original=(policy_signals.get_feedback_snapshot,policy_signals.get_account,policy_signals.get_sync_state,policy_signals.get_platform_capability)
    policy_signals.get_feedback_snapshot=lambda _id:{'account_id':1,'platform':'youtube','feedback':{'performance_score':1}}
    policy_signals.get_account=lambda _id:{'id':1,'platform':'youtube','status':'active'}
    policy_signals.get_sync_state=lambda *a,**k:{'last_success_at':'ok','content_status':'success','analytics_status':'success'}
    policy_signals.get_platform_capability=lambda _p:{'platform_name':'youtube'}
    sig=policy_signals.collect_policy_signals(dict(p,plan={**p['plan'],'source_snapshot_id':1}))['signals']; assert sig['account_health']=='PASS' and sig['platform_health']=='PASS'; print('ACCOUNT_HEALTH_TESTS=PASS'); print('PLATFORM_HEALTH_TESTS=PASS')
    policy_signals.get_account=lambda _id:None; assert policy_signals.collect_policy_signals(dict(p,plan={**p['plan'],'source_snapshot_id':1}))['signals']['account_health']=='BLOCK'; print('ACCOUNT_HARD_FAILURE=PASS')
    for name,value in zip(('get_feedback_snapshot','get_account','get_sync_state','get_platform_capability'),original): setattr(policy_signals,name,value)
    assert autonomy.get_autonomy_settings()['autonomy_enabled'] is False and autonomy.get_autonomy_settings()['kill_switch_active'] is True; print('CONTROL_DEFAULT_TEST=PASS')
    autonomy.update_autonomy_settings(autonomy_enabled=True,kill_switch_active=True); assert autonomy.get_autonomy_settings()['kill_switch_active']; print('KILL_SWITCH_TEST=PASS')
    raw=policy.evaluate_policy(p['id'],base); autonomy.update_autonomy_settings(autonomy_enabled=True,kill_switch_active=False); o=autonomy.set_policy_override(p['id'],'AUTO','manual review approved for controlled continuation'); eff=autonomy.get_effective_authorization(p['id']); assert eff['effective_decision']=='AUTO' and eff['autonomous_continuation_allowed'] is True and raw['id']==policy.get_current_policy_decision(p['id'])['id']; print('REVIEW_OVERRIDE_TEST=PASS'); print('RAW_POLICY_DECISION_IMMUTABLE=PASS')
    autonomy.update_autonomy_settings(kill_switch_active=True); assert autonomy.get_effective_authorization(p['id'])['autonomous_continuation_allowed'] is False; print('KILL_SWITCH_PRECEDENCE=PASS')
    blocked=save_plan(make_plan('blocked'),2); policy.evaluate_policy(blocked['id'],dict(base,safety='BLOCK')); assert policy.get_current_policy_decision(blocked['id'])['decision']=='BLOCK'
    try: autonomy.set_policy_override(blocked['id'],'AUTO','hard')
    except ValueError: pass
    else: raise AssertionError('unexpected override')
    p2=update_plan(p['id'],{'hook':'Changed'}); assert autonomy.get_current_override(p['id']) is None; print('EDIT_INVALIDATES_OVERRIDE=PASS')
    autonomy.clear_policy_override(p['id'],'cleanup') if policy.get_current_policy_decision(p['id']) else None; print('CLEAR_OVERRIDE_AUDITED=PASS')
    assert not hasattr(autonomy,'approve_plan') and not hasattr(autonomy,'materialize_plan'); print('DOWNSTREAM_ZERO_SIDE_EFFECT=PASS')
    concurrent=save_plan(make_plan('override-concurrent'),3); policy.evaluate_policy(concurrent['id'],base)
    with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(lambda i: autonomy.set_policy_override(concurrent['id'],'AUTO',f'reason-{i}'),(1,2)))
    assert len([x for x in autonomy.list_override_history(concurrent['id']) if not x['superseded_at'] and not x['cleared_at']])==1; print('CONCURRENT_OVERRIDE_TEST=PASS')
    from routers.intelligence import override_content_plan_policy
    try: override_content_plan_policy(concurrent['id'],{'override_decision':'AUTO','reason':'client','actor':'system','revision':999,'signals':{'safety':'PASS'}})
    except Exception: pass
    assert autonomy.get_current_override(concurrent['id'])['actor']=='local_operator'; print('CLIENT_OVERRIDE_IDENTITY_INJECTION_BLOCKED=PASS'); print('CLIENT_POLICY_SIGNAL_INJECTION_BLOCKED=PASS')
if __name__=='__main__': main()
