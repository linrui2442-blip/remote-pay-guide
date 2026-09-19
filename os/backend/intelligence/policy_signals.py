from intelligence.content_brain import ContentPlan, validate_content_plan
from intelligence.content_plan_service import evaluate_and_persist_novelty
from intelligence.feedback_bridge import get_feedback_snapshot
from accounts.manager import get_account
from data.sync_state import get_sync_state
from data.platform_capabilities import get_platform_capability

def _business(snapshot):
    if not snapshot: return 'UNKNOWN','SOURCE_SNAPSHOT_MISSING'
    f=snapshot.get('feedback') or {}
    if (f.get('conversions') or 0)>0: return 'PASS','ATTRIBUTED_CONVERSION_PRESENT'
    if (f.get('referral_clicks') or 0)>0: return 'PASS','QUALIFIED_REFERRAL_INTENT_PRESENT'
    if (f.get('intent_events') or 0)>0: return 'PASS','QUALIFIED_INTENT_PRESENT'
    if (f.get('performance_score') or snapshot.get('performance_score') or 0)>0: return 'WARN','TRAFFIC_WITHOUT_QUALIFIED_INTENT'
    return 'WARN','INSUFFICIENT_BUSINESS_SIGNAL'

def collect_policy_signals(plan_record):
    plan=plan_record['plan']; evidence={}; signals={}
    try: validate_content_plan(ContentPlan(**plan)); signals['safety']='PASS'; evidence['safety']={'source':'validate_content_plan','result':'PASS'}
    except Exception as exc: signals['safety']='BLOCK'; evidence['safety']={'source':'validate_content_plan','result':'BLOCK','reason_code':'CONTENT_SAFETY_BLOCK'}
    n=plan.get('novelty_status'); ev=plan.get('novelty_evidence') or {}
    if ev.get('evaluated_revision') != plan_record.get('revision'):
        try: plan_record=evaluate_and_persist_novelty(plan_record['id']); plan=plan_record['plan']; n=plan.get('novelty_status'); ev=plan.get('novelty_evidence') or {}
        except Exception: n='UNKNOWN'
    signals['novelty']=n if n in {'PASS','WARN','BLOCK'} else 'UNKNOWN'; signals['duplicate_risk']=signals['novelty']; evidence['novelty']={'source':'canonical_novelty','status':signals['novelty'],'evaluated_revision':ev.get('evaluated_revision')}; evidence['duplicate_risk']={'source':'canonical_novelty','status':signals['duplicate_risk']}
    authoritative_snapshot_id=plan_record.get('source_snapshot_id')
    payload_snapshot_id=plan.get('source_snapshot_id')
    if authoritative_snapshot_id is not None and payload_snapshot_id not in (None, authoritative_snapshot_id):
        signals['business']='UNKNOWN'; signals['account_health']='UNKNOWN'; signals['platform_health']='UNKNOWN'; evidence['source_snapshot']={'reason_code':'SOURCE_SNAPSHOT_IDENTITY_MISMATCH','authoritative_source_snapshot_id':authoritative_snapshot_id}; snapshot=None; snapshot_id=None
    else:
        snapshot_id=authoritative_snapshot_id if authoritative_snapshot_id is not None else payload_snapshot_id
        snapshot=get_feedback_snapshot(snapshot_id) if snapshot_id is not None else None
    if not snapshot:
        signals.update(account_health='UNKNOWN',platform_health='UNKNOWN',business='UNKNOWN'); evidence.setdefault('source_snapshot',{'reason_code':'SOURCE_SNAPSHOT_MISSING'})
    else:
        account=get_account(snapshot.get('account_id')); platform=snapshot.get('platform'); evidence['source_snapshot']={'account_id':snapshot.get('account_id'),'platform':platform,'content_id':snapshot.get('content_id')}
        status=str(account.get('status') or '').lower() if account else ''
        if not account: signals['account_health']='BLOCK'
        elif str(account.get('platform') or '').lower()!=str(platform or '').lower() or status in {'inactive','disabled','error'}: signals['account_health']='BLOCK'
        else:
            state=get_sync_state(snapshot.get('account_id'),platform,create=False)
            signals['account_health']='PASS' if status in {'active','connected','ready'} and state and state.get('last_success_at') else 'UNKNOWN'
        cap=get_platform_capability(platform); state=get_sync_state(snapshot.get('account_id'),platform,create=False)
        if not cap: signals['platform_health']='BLOCK'
        elif state and state.get('last_success_at') and state.get('content_status') not in {'failed'} and (not cap.get('analytics_supported') or state.get('analytics_status') not in {'failed'}): signals['platform_health']='PASS'
        elif state and state.get('content_status') in {'partial','running'}: signals['platform_health']='WARN'
        else: signals['platform_health']='UNKNOWN'
        signals['business'], business_reason=_business(snapshot); evidence['business']={'reason_code':business_reason,'performance_score':(snapshot.get('feedback') or {}).get('performance_score',snapshot.get('performance_score',0)),'intent_events':(snapshot.get('feedback') or {}).get('intent_events',0),'referral_clicks':(snapshot.get('feedback') or {}).get('referral_clicks',0),'conversions':(snapshot.get('feedback') or {}).get('conversions',0),'conversion_value':(snapshot.get('feedback') or {}).get('conversion_value',0)}
        evidence['sync_health']={'content_status':state.get('content_status') if state else None,'analytics_status':state.get('analytics_status') if state else None,'last_success_at':state.get('last_success_at') if state else None,'last_error_at':state.get('last_error_at') if state else None}
    for key in ('frequency','quality','cost','ai_confidence'): signals[key]='UNKNOWN'
    return {'signals':signals,'evidence':evidence}
