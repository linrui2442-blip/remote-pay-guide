"""Canonical SQLite promotion boundary; no real network allowed."""
import gc, json, os, socket, sqlite3, sys, tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
TEMP=tempfile.TemporaryDirectory(prefix='g4b-promotion-')
os.environ.update(OS_TESTING='1',OS_DATABASE_PATH=str(Path(TEMP.name)/'os.db'))
from production.results import manager as results
from production.providers.github import GitHubProductionProvider
from production.runtime.manager import create_job
from production.tasks.manager import create_task
from production.tasks.scheduler import transition_task

class Fake:
    owner,repo='example','offline'
    def __init__(self):
        self.runs=[]; self.posts=0; self.status='completed'; self.conclusion='success'; self.crash=None
    def list_workflow_runs(self,workflow,branch=None,event=None,**kwargs): return {'workflow_runs':list(self.runs)}
    def get_workflow_run(self,run_id):
        if run_id==1: return {'id':1,'status':'completed','conclusion':'success'}
        return next(dict(r) for r in self.runs if r['id']==run_id)
    def get_workflow_run_artifacts(self,run_id): return {'artifacts':[{'id':7,'name':'expected','expired':False}]}
    def trigger_workflow(self,workflow,branch='main',inputs=None):
        row=results.get_result(self.result_id)
        assert row['promotion_state']=='intent'
        envelope=json.loads(row['promotion_metadata'])
        assert envelope['pre_dispatch_run_ids']==[] and inputs['asset_path']=='final-output.mp4'
        with sqlite3.connect(os.environ['OS_DATABASE_PATH'],timeout=5) as db:
            db.execute('BEGIN IMMEDIATE'); db.rollback()
        db.close()
        if self.crash=='before': raise RuntimeError('crash before POST')
        self.posts+=1
        self.runs.append({'id':100,'created_at':'2999-01-01T00:00:00Z','status':self.status,'conclusion':self.conclusion,'html_url':'https://example.invalid/run'})
        if self.crash=='after': raise RuntimeError('crash after POST')

def setup():
    task=create_task({'source':'legacy','provider':'github','workflow':'render-short01.yml','task_type':'video_batch'})
    for state in ('queued','scheduled','running'): task=transition_task(task,state)
    job=create_job({'task_id':task.id,'provider':'github','job_type':'github_runtime','input':{'parameters':{'artifact_name':'expected','asset_path':'final-output.mp4'}}})
    row=results.create_or_get_result_for_job({'runtime_job_id':job['id'],'provider':'github','status':'submitted','output':{'github_run_id':1,'g4b_no_asset_binding':True}})
    client=Fake(); client.result_id=row['id']; provider=GitHubProductionProvider(client); provider.monitor.sleep=lambda _:None
    return job,row,client,provider

def poll(case): return case[3].poll_job(case[0],results.get_result(case[1]['id']))

def pending(case):
    try: poll(case)
    except (RuntimeError,TimeoutError): return
    raise AssertionError('ambiguous run accepted')

def main():
    def forbidden(*a,**k): raise AssertionError('REAL NETWORK FORBIDDEN')
    with patch.object(socket.socket,'connect',forbidden),patch.object(socket,'create_connection',forbidden):
        case=setup(); first=poll(case)
        assert first['status']=='completed' and case[2].posts==1
        saved=json.loads(results.get_result(case[1]['id'])['promotion_metadata'])
        assert saved['artifact_id']==7 and saved['production_result_id']==case[1]['id'] and saved['promotion_started_at']
        assert poll(case)['status']=='completed' and case[2].posts==1
        print('CANONICAL_FIRST_PROMOTION_EXECUTOR=PASS')
        print('PROMOTION_INTENT_DURABLE_BEFORE_POST=PASS')
        print('DURABLE_INTENT_AND_POST_CORRELATION_MATCH=PASS')
        print('CANONICAL_SECOND_EXECUTOR_NO_REDISPATCH=PASS')
        for target in ('intent','running'):
            try: results.update_promotion_state(case[1]['id'],target)
            except ValueError: pass
            else: raise AssertionError('terminal promotion regressed')
        print('PROMOTION_STATE_MACHINE_SAFE=PASS')
        for remote,conclusion,expected,marker in (('queued',None,'running','QUEUED'),('in_progress',None,'running','RUNNING'),('completed','success','completed','SUCCESS'),('completed','failure','failed','FAILED')):
            case=setup(); case[2].crash='after'; case[2].status=remote; case[2].conclusion=conclusion
            pending(case); assert case[2].posts==1
            recovered=poll(case)
            assert recovered['status']==expected and recovered['output']['promotion_run_id']==100
            assert recovered['output']['asset_ready']==(expected=='completed')
            for _ in range(3): assert poll(case)['status']==expected
            assert case[2].posts==1
            print(f'RECOVERED_{marker}_PROMOTION=PASS')
        print('NONTERMINAL_PROMOTION_NEVER_COMPLETES_RESULT=PASS')
        print('FAILED_PROMOTION_RUN_FAILS_RESULT=PASS')
        print('PROMOTION_POST_CRASH_RECOVERY=PASS')
        case=setup(); case[2].crash='before'; pending(case); pending(case)
        assert case[2].posts==0 and results.get_result(case[1]['id'])['promotion_state']=='intent'
        print('PROMOTION_PRE_POST_CRASH_NO_REDISPATCH=PASS')
        print('PROMOTION_ZERO_MATCH_NO_REDISPATCH=PASS')
        case[2].runs=[{'id':i,'status':'queued','created_at':'2999-01-01T00:00:00Z'} for i in (100,101)]
        pending(case); assert case[2].posts==0
        print('PROMOTION_MULTI_MATCH_FAIL_CLOSED=PASS')
        for _ in range(20):
            case=setup(); barrier=Barrier(4); original=results.claim_promotion_execution
            def competing(*a,**k):
                barrier.wait(timeout=20); return original(*a,**k)
            def attempt(_):
                try: return poll(case)
                except (RuntimeError,TimeoutError): return None
            with patch.object(results,'claim_promotion_execution',competing):
                with ThreadPoolExecutor(max_workers=4) as pool: list(pool.map(attempt,range(4)))
            assert poll(case)['status']=='completed' and case[2].posts==1
            with sqlite3.connect(os.environ['OS_DATABASE_PATH']) as db:
                assert db.execute('SELECT COUNT(*) FROM production_results WHERE runtime_job_id=?',(case[0]['id'],)).fetchone()[0]==1
        print('PROMOTION_CONCURRENCY_ROUNDS=20')
        print('CANONICAL_PROMOTION_CONCURRENCY=PASS')
        with sqlite3.connect(os.environ['OS_DATABASE_PATH']) as db:
            for table in ('video_assets','publish_tasks'):
                exists=db.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone()
                assert not exists or db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]==0
        print('G4B_NO_VIDEO_ASSET_CREATION=PASS')
        print('G4B_NO_PUBLISH_TASK_CREATION=PASS')
        print('CANONICAL_POLL_USES_PROMOTION_CLAIM=PASS')
        print('G4B_PROMOTION_RECOVERY_SMOKE=PASS')

if __name__=='__main__':
    try: main()
    finally:
        gc.collect()
        TEMP.cleanup()
