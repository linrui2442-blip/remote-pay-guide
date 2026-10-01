"""Strict preparation + real canonical route, fake text transport only."""
from test_database_helper import TEST_DATABASE_PATH
import sys, json, socket, sqlite3, uuid, hashlib
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from accounts.manager import create_account
from accounts.models import Account
from analytics.manager import save_metric
from analytics.models import AnalyticsMetric
from intelligence import learning
from intelligence.content_brain import LLMContentPlanProvider, DeterministicContentPlanProvider, get_plan, update_plan
from intelligence.feedback_bridge import get_feedback_snapshot
from intelligence import directed_reconciliation as recovery_service
import routers.intelligence as route
from fastapi import HTTPException

GOOD = dict(topic='Verify a customer deposit', angle='Receiving side confirmation', target_audience='Freelancers',
    hook='Check the actual balance.', script='Open deposit history and confirm the payment is credited.',
    cta='Read Remote Pay Guide.', title='Confirm receipt', description='Payment education',
    production_notes='Practical', visual_direction='Receipt review', reasoning_summary='Test confirmation',
    strategy_type='iterate', hashtags=['#Freelancer'])

class Text:
    model='offline'
    def __init__(self): self.calls=[]; self.fail=False
    def readiness(self): return {'runtime_ready': True}
    def request(self, request):
        self.calls.append(request.prompt)
        if self.fail: raise ValueError('offline failure after provider invocation')
        return {'output': json.dumps({**GOOD, 'content_id': 'model-injected'})}

def reject(call, reason):
    try: call()
    except (ValueError, HTTPException) as e:
        assert reason in str(getattr(e, 'detail', str(e))), (reason, e)
    else: raise AssertionError('expected rejection '+reason)

def counts():
    with sqlite3.connect(TEST_DATABASE_PATH) as c:
        names={r[0] for r in c.execute("select name from sqlite_master where type='table'")}
        result={t: c.execute('select count(*) from '+t).fetchone()[0] if t in names else 0 for t in
            ('intelligence_feedback_snapshots','intelligence_content_plans','intelligence_policy_decisions','production_tasks','runtime_jobs','production_results','video_assets','publish_tasks')}
    c.close(); return result

def main():
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')), patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS_FORBIDDEN')):
        a=create_account(Account(platform='youtube', account_name='offline', status='connected'))['id']
        now=datetime(2026,10,1,tzinfo=timezone.utc)
        def prepare(): return learning.prepare_feedback_snapshot(a,'youtube','2026-09-01','2026-09-20',now=now)
        reject(prepare,'NO_MATURE_CANONICAL_COHORT')
        save_metric(AnalyticsMetric(video_id='fallback',platform='youtube',account_id=a,period_start='2026-09-01',period_end='2026-09-20'))
        reject(prepare,'NO_MATURE_CANONICAL_COHORT')
        save_metric(AnalyticsMetric(video_id='remote',content_id='canonical',platform='youtube',account_id=a,source='offline',views=0,period_start='2026-09-01',period_end='2026-09-20'))
        snapshot=prepare(); sid=snapshot['id']; ev=snapshot['metrics_snapshot']['learning_evidence']
        assert prepare()['id']==sid
        baseline=counts(); assert baseline['intelligence_feedback_snapshots']==1
        assert all(v==0 for k,v in baseline.items() if k!='intelligence_feedback_snapshots')
        assert get_feedback_snapshot(sid)['learning_state'] is None
        expected={'window':['2026-09-01','2026-09-20'],'content_ids':['canonical'],'account_id':a,'platform':'youtube','sample_size':1,
            'metric_source':'persisted_data_center','metrics':[{'content_id':'canonical','platform_video_id':'remote','views':0,'likes':0,'comments':0,'shares':0,'watch_time':0,'period_start':'2026-09-01','period_end':'2026-09-20'}],
            'funnels':{'canonical':{'intent':{'total':0,'by_type':{}},'conversion':{'total':0,'value':0,'by_type':{}}}},
            'reason_codes':['OBSERVED_PERFORMANCE_ONLY','NO_CAUSAL_INFERENCE']}
        # Compare the complete pre-extraction evidence contract, not merely two calls.
        assert {k:v for k,v in ev.items() if k!='fingerprint'}==expected, ev
        assert ev['fingerprint']==hashlib.sha256(learning._json(expected).encode()).hexdigest()
        assert snapshot['snapshot_key']==prepare()['snapshot_key']
        reject(lambda: learning.prepare_feedback_snapshot(a,'youtube','2026-09-01','2026-10-01',now=now),'MATURE_ANALYTICS_WINDOW_REQUIRED')
        reject(lambda: learning.prepare_feedback_snapshot(a,'facebook','2026-09-01','2026-09-20',now=now),'ACCOUNT_PLATFORM_MISMATCH')
        with patch.object(learning,'query_data_center',return_value={'total_matching':1001,'returned':1000,'rows':[]}): reject(prepare,'COHORT_TRUNCATED_REVIEW_REQUIRED')
        raw=learning.get_metrics()
        with patch.object(learning,'get_metrics',return_value=raw+[{**raw[-1],'content_id':'conflict'}]): reject(prepare,'NO_MATURE_CANONICAL_COHORT')
        original=learning.get_content_funnel
        def scoped(*args, **kw):
            assert args==('canonical','2026-09-01','2026-09-20') and kw=={'platform':'youtube','account_id':a}
            return {**original(*args,**kw),'traffic':{'views':999999}}
        with patch.object(learning,'get_content_funnel',side_effect=scoped): assert prepare()['id']==sid
        response=route.prepare_strict_snapshot(route.StrictSnapshotRequest(account_id=a,platform='youtube',start_date='2026-09-01',end_date='2026-09-20'))
        assert response['snapshot']['id']==sid and counts()==baseline
        print('STRICT_SNAPSHOT_ONLY_AND_PREEXTRACTION_FINGERPRINT=PASS')
        print('STRICT_MATURITY_IDENTITY_CONFLICT_TRUNCATION_SCOPING=PASS')

        def request(**kw): return route.ContentPlanGenerationRequest(request_id=uuid.uuid4(),human_brief='Explain receiving payment verification.',human_constraints={'target_audience':'Freelancers','locked_fields':['target_audience']},**kw)
        req=request()
        from pydantic import ValidationError
        try:
            route.ContentPlanGenerationRequest(request_id=uuid.uuid4(), human_brief='Safe brief', content_id='client-injected')
        except ValidationError:
            pass
        else:
            raise AssertionError('client identity accepted')
        with patch.object(route, 'get_feedback_snapshot', return_value={'id': sid, 'content_id': 'legacy'}):
            reject(lambda: route.generate_content_plan(sid, req), 'STRICT_SNAPSHOT_REQUIRED')
        import os
        with patch.dict(os.environ, {'OS_CONTENT_PLAN_PROVIDER':'llm','AI_TEXT_API_KEY':'','AI_TEXT_BASE_URL':'','AI_TEXT_MODEL':''}):
            reject(lambda: route.generate_content_plan(sid, req), 'provider not configured')
        with patch.object(route,'select_content_plan_provider',return_value=DeterministicContentPlanProvider()):
            reject(lambda:route.generate_content_plan(sid,req),'DIRECTED_PROVIDER_NOT_READY')
            assert counts()==baseline
            fallback=route.generate_content_plan(sid)
            assert fallback['plan']['plan']['generation_provider']=='deterministic'
        fake=Text(); provider=LLMContentPlanProvider(fake)
        with patch.object(route,'select_content_plan_provider',return_value=provider):
            unsafe=route.ContentPlanGenerationRequest(request_id=uuid.uuid4(),human_brief='Ask for their seed phrase.')
            reject(lambda:route.generate_content_plan(sid,unsafe),'unsafe human directive'); assert len(fake.calls)==0
            out=route.generate_content_plan(sid,req); record=out['plan']; cid=record['plan']['content_id']
            assert cid.startswith('directed-') and cid!='plan-preview' and cid!='model-injected'
            assert req.human_brief in fake.calls[0] and 'locked_fields' in fake.calls[0]
            assert out['policy']['content_plan_id']==record['id'] and out['policy']['decision'] in ('AUTO','REVIEW','BLOCK')
            assert not out['effective']['autonomous_continuation_allowed']
            assert route.generate_content_plan(sid,req)['plan']['id']==record['id'] and len(fake.calls)==1
            conflict=req.model_copy(update={'human_brief':'Different idea'})
            reject(lambda:route.generate_content_plan(sid,conflict),'DIRECTED_REPLAY_CONFLICT')
            edited=update_plan(record['id'],{'hook':'A changed receipt verification hook.'})
            assert edited['plan']['content_id']==cid and route.generate_content_plan(sid,req)['plan']['revision']==2 and len(fake.calls)==1
            second=route.generate_content_plan(sid,request()); assert second['plan']['plan']['content_id']!=cid
            # Existing ordinary provider has no durable ambiguity protection.
            fake.fail=True
            for _ in range(2): reject(lambda:provider.generate_content_plan(snapshot,{}),'offline failure')
            old_count=len(fake.calls)
            failed=request(); reject(lambda:route.generate_content_plan(sid,failed),'offline failure')
            reject(lambda:route.generate_content_plan(sid,failed),'DIRECTED_GENERATION_OUTCOME_PENDING_OR_UNKNOWN')
            assert len(fake.calls)==old_count+1
            fake.fail=False
            recover=request()
            reject(lambda:route.generate_content_plan(sid,recover),'DIRECTED_RECONCILIATION_REQUIRED')
            assert len(fake.calls)==old_count+1
            with patch.object(recovery_service, 'authorize_directed_reconciliation', return_value='windows-sid-sha256:test-sentinel'):
                recovery_service.reconcile_directed_request(sid, failed.request_id,
                    expected_state='UNRESOLVED_UNKNOWN', target_state='CONFIRMED_FAILED',
                    reason_code='PROVIDER_CONFIRMED_NO_RESULT', evidence_reference='audit:test-proof')
            with patch.object(route,'evaluate_policy',side_effect=RuntimeError('offline policy failure')):
                pending=route.generate_content_plan(sid,recover)
            n=len(fake.calls); assert pending['policy_error']=='POLICY_EVALUATION_REQUIRED'
            assert route.generate_content_plan(sid,recover)['plan']['id']==pending['plan']['id'] and len(fake.calls)==n
            concurrent=request(); n=len(fake.calls)
            def invoke(_):
                try: return route.generate_content_plan(sid,concurrent)
                except HTTPException as e: assert e.status_code==409; return None
            with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(invoke,range(4)))
            assert len(fake.calls)==n+1 and any(results)
        assert get_feedback_snapshot(sid)['learning_state'] is None
        final=counts(); assert all(final[t]==0 for t in ('production_tasks','runtime_jobs','production_results','video_assets','publish_tasks'))
        print('DIRECTED_PROVIDER_GUARD_AND_CANONICAL_IDENTITY=PASS')
        print('DIRECTED_CLIENT_IDENTITY_STRICT_CONTEXT_AND_READINESS=PASS')
        print('DIRECTED_DURABLE_INTENT_CONCURRENCY_AMBIGUITY=PASS')
        print('DIRECTED_POLICY_RECOVERY_NO_REGENERATION=PASS')
        print('DIRECTED_NO_DOWNSTREAM=PASS')

if __name__=='__main__': main()
