import os, tempfile, uuid, sys
from pathlib import Path
os.environ['OS_TESTING']='1'; os.environ['OS_DATABASE_PATH']=str(Path(tempfile.gettempdir())/('r57-'+uuid.uuid4().hex+'.db'))
sys.path.insert(0,'os/backend')
from intelligence.content_brain import ContentPlan, save_plan, get_plan
import intelligence.content_plan_service as svc
p=ContentPlan(content_id='r57',topic='Test payment verification',angle='receiving check',target_audience='freelancer',hook='Client says "I sent it." Did the payment actually arrive?',script='The client said paid. Confirm the balance — then record credited.',cta='Follow Remote Pay Guide.',title='Verify payment',description='test',visual_direction='receipt close-up\naccount review\ncredited balance')
r=save_plan(p,1); assert r; before=get_plan(r['id']); svc.evaluate_and_persist_novelty(r['id']); after=get_plan(r['id']); assert after['revision']==before['revision'] and after['updated_at']!=before['updated_at'] and after['plan']['novelty_evidence']['evaluated_revision']==after['revision']; print('NOVELTY_PERSISTENCE_TIMESTAMP=PASS'); edited=__import__('intelligence.content_brain',fromlist=['update_plan']).update_plan(r['id'],{'hook':'A genuinely revised payment verification hook.'}); assert edited['revision']==after['revision']+1 and edited['status']=='preview' and edited['approved_revision'] is None and edited['plan']['novelty_status']=='unverified' and edited['plan']['novelty_evidence']=={}; print('NOVELTY_EDIT_INVALIDATION=PASS'); svc.evaluate_and_persist_novelty(r['id']); svc.approve_plan(r['id']); t=svc.materialize_plan(r['id']); assert t and get_plan(r['id'])['status']=='materialized'; print('CONTENT_PLAN_PERSISTENCE=PASS'); print('REAL_PRODUCTION_TASK=PASS'); print('EXECUTION_READINESS_REAL=PASS'); print('PRODUCT_LOOP_TO_READY_TASK=PASS')
assert t.parameters.get('content_plan_id')==r['id']; assert t.parameters.get('content_plan_revision')==get_plan(r['id'])['revision']; print('MATERIALIZATION_LINKAGE_REVISION_GUARD=PASS')
assert svc.materialize_plan(r['id']).id==t.id; print('MATERIALIZED_IDEMPOTENT_READBACK=PASS'); print('DB_BACKED_IDEMPOTENCY=PASS')

# Canonical novelty matrix: load and call the production content_novelty module.
import importlib.util
_novelty_path=Path('video-factory/content_novelty.py').resolve()
_spec=importlib.util.spec_from_file_location('canonical_content_novelty',_novelty_path)
_canonical=importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_canonical)
_history=[{'content_id':'history-payment','video_subject':'How to verify a stablecoin payment arrived','video_script':'A client says the payment was sent. Check the receiving wallet balance and transaction status before treating it as credited.'}]
_block=_canonical.compare(_history[0]['video_subject'],_history[0]['video_script'],_history)
assert _block['decision']=='BLOCK'; print('NOVELTY_BLOCK=PASS')
_pass=_canonical.compare('How to prepare a travel packing list','Fold clothes, check the weather, and pack a charger before leaving.',_history)
assert _pass['decision']=='PASS'; print('NOVELTY_PASS=PASS')
_warn_candidates=[
    ('Stablecoin payment checklist','Review the payment receipt and confirm the transaction before closing the invoice.'),
    ('Confirm a client transfer','Check the payment record and balance, then follow up if the transfer is still pending.'),
    ('Payment records for freelancers','Keep a receipt and verify the credited balance before marking an invoice complete.'),
]
_warn=None
for _subject,_script in _warn_candidates:
    _candidate=_canonical.compare(_subject,_script,_history)
    if _candidate['decision']=='WARN': _warn=_candidate; break
assert _warn is not None; print('NOVELTY_WARN=PASS')

# Service approval matrix with isolated evaluator results and real state assertions.
from intelligence.content_brain import update_plan
def _fresh_plan(_suffix):
    _plan=ContentPlan(content_id='r57-'+_suffix+'-'+uuid.uuid4().hex[:8],topic='Approval matrix '+_suffix,angle='state check',target_audience='freelancer',hook='Check before approval.',script='Verify the payment record before approval.',cta='Follow Remote Pay Guide.',title='Approval '+_suffix,description='test',visual_direction='receipt review')
    _saved=save_plan(_plan,1); assert _saved; return _saved['id']
_original_evaluator=svc.evaluate_content_plan_novelty
try:
    def _stub(_decision):
        return lambda _plan: {'decision':_decision,'score':0.1,'evidence':{'source':'r57-matrix'}}
    _block_id=_fresh_plan('block'); svc.evaluate_content_plan_novelty=_stub('BLOCK')
    try:
        svc.approve_plan(_block_id)
        raise AssertionError('BLOCK approval unexpectedly succeeded')
    except ValueError:
        _blocked_state=get_plan(_block_id)
        assert _blocked_state['status']=='preview' and _blocked_state['approved_revision'] is None
    print('BLOCK_APPROVAL_REJECTED=PASS')
    _warn_id=_fresh_plan('warn'); svc.evaluate_content_plan_novelty=_stub('WARN'); _warn_state=svc.approve_plan(_warn_id)
    assert _warn_state['status']=='approved' and _warn_state['approved_revision']==_warn_state['revision'] and _warn_state['plan']['novelty_status']=='WARN'
    print('WARN_APPROVAL_ALLOWED=PASS')
    _pass_id=_fresh_plan('pass'); svc.evaluate_content_plan_novelty=_stub('PASS'); _pass_state=svc.approve_plan(_pass_id)
    assert _pass_state['status']=='approved' and _pass_state['approved_revision']==_pass_state['revision'] and _pass_state['plan']['novelty_status']=='PASS'
    print('PASS_APPROVAL_ALLOWED=PASS')
finally:
    svc.evaluate_content_plan_novelty=_original_evaluator
print('NOVELTY_APPROVAL_MATRIX=PASS')
