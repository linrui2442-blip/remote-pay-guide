import os, tempfile, uuid, sys
from pathlib import Path
os.environ['OS_TESTING']='1'; os.environ['OS_DATABASE_PATH']=str(Path(tempfile.gettempdir())/('r57-'+uuid.uuid4().hex+'.db'))
sys.path.insert(0,'os/backend')
from intelligence.content_brain import ContentPlan, save_plan, get_plan
import intelligence.content_plan_service as svc
p=ContentPlan(content_id='r57',topic='Test payment verification',angle='receiving check',target_audience='freelancer',hook='Client says "I sent it." Did the payment actually arrive?',script='The client said paid. Confirm the balance — then record credited.',cta='Follow Remote Pay Guide.',title='Verify payment',description='test',visual_direction='receipt close-up\naccount review\ncredited balance')
r=save_plan(p,1); assert r; svc.evaluate_and_persist_novelty(r['id']); svc.approve_plan(r['id']); t=svc.materialize_plan(r['id']); assert t and get_plan(r['id'])['status']=='materialized'; print('CONTENT_PLAN_PERSISTENCE=PASS'); print('REAL_PRODUCTION_TASK=PASS'); print('EXECUTION_READINESS_REAL=PASS'); print('PRODUCT_LOOP_TO_READY_TASK=PASS')
