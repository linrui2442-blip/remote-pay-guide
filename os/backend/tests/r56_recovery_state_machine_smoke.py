import os, sqlite3, tempfile, sys
from pathlib import Path

os.environ['OS_TESTING'] = '1'
os.environ['OS_DATABASE_PATH'] = str(Path(tempfile.gettempdir()) / 'r56_recovery.db')
Path(os.environ['OS_DATABASE_PATH']).unlink(missing_ok=True)
sys.path.insert(0, 'os/backend')

from production.tasks.models import ProductionTask
from production.tasks.scheduler import transition_task
from production.tasks.manager import create_task
from production.runtime.manager import create_job
from production.results.manager import create_result, claim_failed_result_for_recovery, complete_recovered_result, get_result
from assets.manager import create_asset

failed = ProductionTask(source='legacy', objective='x', provider='github', template='t', branch='main', status='failed')
try:
    transition_task(failed, 'completed')
except ValueError:
    pass
else:
    raise AssertionError('ordinary failed->completed transition must remain forbidden')

task = create_task(ProductionTask(source='legacy', objective='x', provider='github', template='t', branch='main', status='created'))
conn = sqlite3.connect(os.environ['OS_DATABASE_PATH'])
conn.execute("UPDATE production_tasks SET status='failed' WHERE id=?", (task.id,)); conn.commit(); conn.close()
job = create_job({'task_id': task.id, 'job_type': 'video', 'provider': 'github'})
conn = sqlite3.connect(os.environ['OS_DATABASE_PATH']); conn.execute("UPDATE runtime_jobs SET status='failed' WHERE id=?", (job['id'],)); conn.commit(); conn.close()
result = create_result({'runtime_job_id': job['id'], 'provider': 'github', 'video_id': 'test-recovery', 'status': 'failed', 'output': {}})
assert claim_failed_result_for_recovery(result['id'])
create_asset({'asset_id':'asset_r56', 'video_id':'test-recovery', 'production_result_id':str(result['id']), 'source_provider':'github', 'storage_type':'github_pages', 'asset_url':'https://example.github.io/media/test-recovery.mp4', 'status':'ready'})
out = {'url':'https://example.github.io/media/test-recovery.mp4', 'asset_url':'https://example.github.io/media/test-recovery.mp4', 'storage_type':'github_pages', 'asset_id':'asset_r56'}
done = complete_recovered_result(result['id'], output=out)
assert done['status'] == 'completed'
assert complete_recovered_result(result['id'], output=out)['status'] == 'completed'

# Invalid linkage must fail without lifecycle normalization.
bad = create_result({'runtime_job_id': 999, 'provider': 'github', 'video_id': 'bad-link', 'status': 'failed', 'output': {}})
assert claim_failed_result_for_recovery(bad['id'])
try:
    complete_recovered_result(bad['id'], output=out)
except ValueError:
    pass
else:
    raise AssertionError('invalid linkage must be rejected')
assert get_result(bad['id'])['status'] == 'running'
print('INVALID_LINKAGE_REJECTION=PASS')

# Ambiguous mixed lifecycle state must fail loudly.
conn = sqlite3.connect(os.environ['OS_DATABASE_PATH'])
conn.execute("UPDATE runtime_jobs SET status='failed' WHERE id=?", (job['id'],)); conn.execute("UPDATE production_tasks SET status='failed' WHERE id=?", (task.id,)); conn.commit(); conn.close()
mixed = create_result({'runtime_job_id': job['id'], 'provider': 'github', 'video_id': 'mixed', 'status': 'failed', 'output': {}})
assert claim_failed_result_for_recovery(mixed['id'])
conn = sqlite3.connect(os.environ['OS_DATABASE_PATH'])
conn.execute("UPDATE runtime_jobs SET status='completed' WHERE id=?", (job['id'],)); conn.commit(); conn.close()
try:
    complete_recovered_result(mixed['id'], output=out)
except ValueError:
    pass
else:
    raise AssertionError('ambiguous state must be rejected')
print('AMBIGUOUS_STATE_REJECTION=PASS')
print('Recovery state machine smoke passed')
