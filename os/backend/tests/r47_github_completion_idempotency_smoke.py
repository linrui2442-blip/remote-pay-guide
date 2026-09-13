"""Isolated exactly-once completion claim and terminal no-op verification."""
import os, sys, tempfile, threading
from pathlib import Path
DB=Path(tempfile.gettempdir())/"remote-pay-guide-p1-r47.db"; DB.unlink(missing_ok=True)
os.environ["OS_TESTING"]="1"; os.environ["OS_DATABASE_PATH"]=str(DB)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from production.results.manager import create_result, get_result, get_results
from production.providers import github_completion

class Client: pass
class Monitor:
    def __init__(self, mode="success"): self.mode=mode
    def wait_for_terminal(self,*a,**k): return {"id":1,"status":"completed","conclusion":"success"}
    def discover_artifact(self,*a,**k): return {"id":2,"name":"remote-pay-guide-short12","size_in_bytes":1}
class Promotion:
    count=0
    lock=threading.Lock()
    def __call__(self,**kwargs):
        with self.lock: self.count+=1
        return {"storage_type":"github_pages","asset_url":"https://example.invalid/media/short12.mp4","asset_ready":True}
promotion=Promotion()
github_completion.promote_artifact_to_pages=promotion
github_completion.GitHubRunMonitor=lambda c: Monitor()
result=create_result({"runtime_job_id":1,"provider":"github","video_id":"short12","status":"submitted","output":{"github_run_id":1}})
outs=[]
def call(): outs.append(github_completion.complete_github_execution(result["id"],{},client=Client()))
threads=[threading.Thread(target=call) for _ in range(2)]
[t.start() for t in threads]; [t.join() for t in threads]
assert promotion.count==1, promotion.count
assert get_result(result["id"])["status"]=="completed"
assert github_completion.complete_github_execution(result["id"],{},client=Client())["status"]=="completed"
assert promotion.count==1
failed=create_result({"runtime_job_id":2,"provider":"github","video_id":"short12","status":"failed","output":{}})
assert github_completion.complete_github_execution(failed["id"],{},client=Client())["status"]=="failed"
assert promotion.count==1
assert len(get_results())==2
print("P1 GitHub completion idempotency smoke passed")
