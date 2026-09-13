import os, tempfile, sys
from pathlib import Path
os.environ['OS_TESTING']='1'; os.environ['OS_DATABASE_PATH']=str(Path(tempfile.gettempdir())/'r57.db'); Path(os.environ['OS_DATABASE_PATH']).unlink(missing_ok=True)
sys.path.insert(0,'os/backend')
from intelligence.content_brain import DeterministicContentPlanProvider, save_plan, update_plan, set_plan_status
p=DeterministicContentPlanProvider().generate_content_plan({'id':1},{})
a=save_plan(p,1); b=save_plan(p,1); assert a['id']==b['id']
assert update_plan(a['id'], {'hook':'A revised safe hook.'})['plan']['hook']=='A revised safe hook.'
assert set_plan_status(a['id'],'approved')['status']=='approved'
assert set_plan_status(a['id'],'materialized')['status']=='materialized'
print('CONTENT_PLAN_LOOP=PASS')
