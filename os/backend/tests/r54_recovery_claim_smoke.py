import os,tempfile,sys
from pathlib import Path
os.environ['OS_TESTING']='1'; os.environ['OS_DATABASE_PATH']=str(Path(tempfile.gettempdir())/'r54.db'); Path(os.environ['OS_DATABASE_PATH']).unlink(missing_ok=True)
sys.path.insert(0,'os/backend')
from production.results.manager import create_result,claim_failed_result_for_recovery,get_result
r=create_result({'runtime_job_id':1,'provider':'github','video_id':'short13','status':'failed','output':{}}); assert claim_failed_result_for_recovery(r['id']); assert not claim_failed_result_for_recovery(r['id']); assert get_result(r['id'])['status']=='running'; print('Recovery claim smoke passed')
