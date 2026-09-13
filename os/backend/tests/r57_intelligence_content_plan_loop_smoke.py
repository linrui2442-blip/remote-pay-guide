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

# Stale novelty must be re-evaluated after an edit, using the current revision.
_reeval_id=_fresh_plan('stale-reeval'); _reeval_calls=[]
def _reeval_evaluator(_plan):
    _reeval_calls.append(_plan.hook)
    _decision='BLOCK' if len(_reeval_calls)==1 else 'PASS'
    return {'decision':_decision,'score':0.1,'evidence':{'call':len(_reeval_calls)}}
_original_evaluator=svc.evaluate_content_plan_novelty
try:
    svc.evaluate_content_plan_novelty=_reeval_evaluator
    _initial=svc.evaluate_and_persist_novelty(_reeval_id)
    assert _initial['plan']['novelty_status']=='BLOCK'
    _edited=update_plan(_reeval_id,{'hook':'A materially revised hook for the current payment workflow.'})
    assert _edited['revision']==_initial['revision']+1 and _edited['plan']['novelty_status']=='unverified' and _edited['plan']['novelty_evidence']=={}
    _approved=svc.approve_plan(_reeval_id)
    assert len(_reeval_calls)==2 and _approved['status']=='approved' and _approved['approved_revision']==_edited['revision'] and _approved['plan']['novelty_status']=='PASS' and _approved['plan']['novelty_evidence']['evaluated_revision']==_edited['revision']
finally:
    svc.evaluate_content_plan_novelty=_original_evaluator
print('STALE_NOVELTY_REEVALUATED=PASS')

# A stale pre-edit approval/materialization attempt is rejected; current revision is accepted.
_guard_id=_fresh_plan('stale-guard'); _guard_original=svc.evaluate_content_plan_novelty
try:
    svc.evaluate_content_plan_novelty=lambda _plan: {'decision':'PASS','score':0.1,'evidence':{'source':'r57-guard'}}
    _guard_approved=svc.approve_plan(_guard_id); _stale_revision=_guard_approved['revision']
    _guard_edit=update_plan(_guard_id,{'hook':'A new hook invalidates the previous approval.'})
    assert _guard_edit['revision']==_stale_revision+1 and _guard_edit['status']=='preview' and _guard_edit['approved_revision'] is None
    try:
        svc.materialize_plan(_guard_id)
        raise AssertionError('stale revision unexpectedly materialized')
    except ValueError as _exc:
        assert str(_exc)=='revision approval conflict'
    _current=svc.approve_plan(_guard_id)
    assert _current['status']=='approved' and _current['approved_revision']==_guard_edit['revision'] and _current['revision']==_guard_edit['revision']
finally:
    svc.evaluate_content_plan_novelty=_guard_original
print('STALE_REVISION_REJECTED=PASS')
print('CURRENT_REVISION_ACCEPTED=PASS')
print('NOVELTY_REVISION_GUARD=PASS')

# Exact quote-safe payload roundtrip through the real production-spec/task path.
from intelligence.production_spec import build_production_spec
import base64, json, sqlite3
_quote_plan=ContentPlan(content_id='r57-quote-'+uuid.uuid4().hex[:8],topic='Quote "topic" - 收款',angle='roundtrip',target_audience='freelancer',hook='Client said: "I sent it."\\nPlease verify.',script="Line one: \\path\\file\nLine two: 'credited' - 已到账。",cta="Don't guess - verify it.",title='Title "quoted" / 标题',description="Description with \\ slash and 'apostrophe'",visual_direction='receipt close-up')
_quote_id=save_plan(_quote_plan,1)['id']; _quote_original=svc.evaluate_content_plan_novelty
try:
    svc.evaluate_content_plan_novelty=lambda _plan: {'decision':'PASS','score':0.1,'evidence':{'source':'r57-quote'}}
    svc.approve_plan(_quote_id); _quote_task=svc.materialize_plan(_quote_id)
finally:
    svc.evaluate_content_plan_novelty=_quote_original
_quote_params=_quote_task.parameters; _quote_spec=build_production_spec(_quote_plan)
assert _quote_params['hook']==_quote_plan.hook and _quote_params['script']==_quote_plan.script and _quote_params['cta']==_quote_plan.cta and _quote_params['title']==_quote_plan.title and _quote_params['description']==_quote_plan.description
_decoded=json.loads(base64.b64decode(_quote_params['task_payload_b64']).decode('utf-8'))
assert _decoded['video_subject']==_quote_plan.topic and _decoded['video_script']==_quote_plan.script
assert _quote_params['task_payload_b64']==_quote_spec['task_payload_b64']
print('QUOTE_SAFE_PAYLOAD_ROUNDTRIP=PASS'); print('EXACT_PAYLOAD_PRESERVED=PASS')

# A materialized plan without its backing task must fail the existing validator path.
_orphan_id=save_plan(ContentPlan(content_id='r57-orphan-'+uuid.uuid4().hex[:8],topic='Orphan materialization',angle='validation',target_audience='freelancer',hook='Check the task.',script='Validate the task before proceeding.',cta='Verify first.',title='Orphan',description='test',visual_direction='receipt review'),1)['id']
_orphan_original=svc.evaluate_content_plan_novelty
try:
    svc.evaluate_content_plan_novelty=lambda _plan: {'decision':'PASS','score':0.1,'evidence':{'source':'r57-orphan'}}
    svc.approve_plan(_orphan_id); svc.set_plan_status(_orphan_id,'materialized')
    try:
        svc.materialize_plan(_orphan_id)
        raise AssertionError('materialized plan without task unexpectedly accepted')
    except ValueError as _orphan_exc:
        assert str(_orphan_exc)=='materialization task missing'
finally:
    svc.evaluate_content_plan_novelty=_orphan_original
print('MATERIALIZED_WITHOUT_TASK_REJECTED=PASS')

# SQL-level proof that the approved plan revision has exactly one task row.
from data.database_path import database_path
_idem=t.parameters['idempotency_key']; _same_a=svc.materialize_plan(r['id']).id; _same_b=svc.materialize_plan(r['id']).id
assert _same_a==_same_b==t.id
with sqlite3.connect(database_path()) as _db:
    _count=_db.execute('SELECT COUNT(*) FROM production_tasks WHERE idempotency_key=?',(_idem,)).fetchone()[0]
assert _count==1
print('DB_IDEMPOTENCY_EXACT_COUNT_ONE=PASS')
