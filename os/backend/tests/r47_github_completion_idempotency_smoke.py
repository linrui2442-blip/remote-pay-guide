"""Real manual task/job/result contract, shared promotion claim, fake network."""
import gc, json, os, socket, sqlite3, sys, tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
TEMP=tempfile.TemporaryDirectory(prefix='r47-manual-')
os.environ.update(OS_TESTING='1',OS_DATABASE_PATH=str(Path(TEMP.name)/'os.db'))
from production.results.manager import create_result,get_result,get_results
from production.providers import github_completion
from production.tasks.manager import create_task
from production.tasks.scheduler import schedule_task
from assets.manager import get_assets

class Client:
    owner,repo='example','offline'
    def __init__(self): self.runs=[]; self.posts=0; self.crash=None; self.lock=Lock(); self.pending_reads=0
    def list_workflow_runs(self,*a,**k): return {'workflow_runs':list(self.runs)}
    def get_workflow_run(self,run_id):
        if run_id==200 and self.pending_reads:
            self.pending_reads-=1
            return {'id':run_id,'status':'in_progress','conclusion':None}
        return {'id':run_id,'status':'completed','conclusion':'success','html_url':'https://example.invalid/run'}
    def get_workflow_run_artifacts(self,run_id): return {'artifacts':[{'id':2,'name':'manual','expired':False}]}
    def trigger_workflow(self,workflow,branch='main',inputs=None):
        row=get_result(self.result_id)
        assert row['promotion_state']=='intent' and json.loads(row['promotion_metadata'])['asset_path']=='final-output.mp4'
        if self.crash=='before': raise RuntimeError('before POST')
        with self.lock:
            self.posts+=1
            self.runs.append({'id':200,'created_at':'2999-01-01T00:00:00Z','status':'completed','conclusion':'success'})
        if self.crash=='after': raise RuntimeError('after POST')

def setup():
    task=create_task({'source':'legacy','provider':'github','workflow':'render-short01.yml','branch':'main',
        'parameters':{'content_id':'manual','artifact_name':'manual','asset_path':'final-output.mp4','asset_filename':'manual.mp4'}})
    job=schedule_task(task)
    row=create_result({'runtime_job_id':job['id'],'provider':'github','video_id':'manual','status':'submitted','output':{'github_run_id':1}})
    client=Client(); client.result_id=row['id']
    return row,job,client

def main():
    def blocked(*a,**k): raise AssertionError('Real network forbidden')
    with patch.object(socket.socket,'connect',blocked),patch.object(github_completion,'_verify_public_url',return_value=True):
        row,job,client=setup(); barrier=Barrier(4)
        def call(_):
            barrier.wait(timeout=10)
            return github_completion.complete_github_execution(row['id'],job,client)
        with ThreadPoolExecutor(max_workers=4) as pool: outcomes=list(pool.map(call,range(4)))
        final=get_result(row['id'])
        assert final['status']=='completed' and final['output']['promotion_run_id']==200 and client.posts==1
        assert len([r for r in get_results() if r['runtime_job_id']==job['id']])==1
        assert len(get_assets())==1
        for _ in range(3): assert github_completion.complete_github_execution(row['id'],job,client)['id']==row['id']
        assert client.posts==1 and len(get_assets())==1
        print('MANUAL_COMPLETION_CONCURRENCY=PASS')
        print('MANUAL_PROMOTION_AT_MOST_ONCE=PASS')
        print('MANUAL_TERMINAL_REPLAY_IDEMPOTENT=PASS')
        row,job,client=setup(); client.pending_reads=1
        assert github_completion.complete_github_execution(row['id'],job,client)['status']=='completed'
        assert client.posts==1 and client.pending_reads==0
        print('MANUAL_SYNCHRONOUS_TERMINAL_WAIT=PASS')
        row,job,client=setup()
        try: github_completion.complete_github_execution(row['id'],{},client)
        except ValueError: pass
        else: raise AssertionError('Empty job accepted')
        assert client.posts==0 and get_result(row['id'])['status']=='submitted'
        for phase,expected in (('before',0),('after',1)):
            row,job,client=setup(); client.crash=phase
            first=github_completion.complete_github_execution(row['id'],job,client)
            assert first['status']=='running'
            again=github_completion.complete_github_execution(row['id'],job,client)
            assert client.posts==expected
            assert again['status']==('running' if phase=='before' else 'completed')
            if phase=='after': assert again['output']['promotion_run_id']==200
            print('MANUAL_PROMOTION_PRE_POST_CRASH_SAFE=PASS' if phase=='before' else 'MANUAL_PROMOTION_POST_CRASH_RECOVERY=PASS')
        print('MANUAL_AUTO_PROMOTION_SAFETY_SHARED=PASS')
        print('P1 GitHub completion idempotency smoke passed')

if __name__=='__main__':
    try: main()
    finally:
        gc.collect(); TEMP.cleanup()
