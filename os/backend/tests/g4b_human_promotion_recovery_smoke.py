"""Human promotion recovery and G4-D boundary, entirely offline."""
import gc
import json
import os
import socket
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TEMP = tempfile.TemporaryDirectory(prefix='g4b-human-promotion-')
DB = Path(TEMP.name) / 'os.db'
os.environ.update(OS_TESTING='1', OS_DATABASE_PATH=str(DB))

from assets.quality import evaluate_production_result_asset
from intelligence.content_brain import ContentPlan, save_plan, set_plan_status
from intelligence.content_plan_service import materialize_plan
from production.providers.github import GitHubProductionProvider
from production.providers import github_completion
from production.results.manager import create_result, get_result, update_promotion_state
from production.runtime.manager import update_job_status
from production.tasks.manager import get_task, update_task_status
from production.tasks.scheduler import schedule_task


class FakeGitHub:
    owner, repo = 'example', 'offline'

    def __init__(self, artifact_name):
        self.artifact_name = artifact_name
        self.posts = []
        self.runs = []

    def list_workflow_runs(self, workflow, branch=None, event=None, per_page=30):
        return {'workflow_runs': [r for r in self.runs if r['workflow'] == workflow]}

    def get_workflow_run(self, run_id):
        if run_id == 10:
            return {'id': 10, 'status': 'completed', 'conclusion': 'success',
                    'html_url': 'https://example.invalid/render'}
        return next(r for r in self.runs if r['id'] == run_id)

    def get_workflow_run_artifacts(self, run_id):
        assert run_id == 10
        return {'artifacts': [{'id': 77, 'name': self.artifact_name, 'expired': False,
                               'size_in_bytes': 100}]}

    def trigger_workflow(self, workflow, branch='main', inputs=None):
        assert workflow == 'promote-video-asset.yml' and branch == 'main'
        self.posts.append(workflow)
        self.runs.append({'id': 20, 'workflow': workflow, 'status': 'completed',
                          'conclusion': 'success', 'html_url': 'https://example.invalid/promotion',
                          'created_at': '2999-01-01T00:00:00Z'})
        return {'status': 'started'}


class FakeDownloader:
    @contextmanager
    def download(self, url, *, storage_type):
        assert storage_type == 'github_pages' and url.startswith('https://example.github.io/')
        path = Path(TEMP.name) / 'fake-media.mp4'
        path.write_bytes(b'x' * 100)
        yield type('Media', (), {'path': path, 'content_type': 'video/mp4',
                                 'size': 100, 'host': 'example.github.io'})()


class FakeProbe:
    def inspect(self, path):
        assert path.is_file()
        return {'format': {'format_name': 'mov,mp4,m4a,3gp,3g2,mj2', 'duration': '45'},
                'streams': [{'codec_type': 'video', 'codec_name': 'h264', 'width': 720,
                             'height': 1280}, {'codec_type': 'audio', 'codec_name': 'aac'}]}


def count(table):
    with sqlite3.connect(DB) as db:
        exists = db.execute('SELECT 1 FROM sqlite_master WHERE type="table" AND name=?', (table,)).fetchone()
        return db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] if exists else 0


def main():
    plan = ContentPlan(content_id='human-promotion-fixture', topic='Payment verification',
                       angle='credited balance', target_audience='freelancers',
                       hook='Verify the receiving account.', script='Check that the payment is credited.',
                       cta='Read the guide.', title='Payment verification',
                       description='Educational payment guide', visual_direction='Account balance view')
    saved = save_plan(plan)
    set_plan_status(saved['id'], 'approved')
    task = materialize_plan(saved['id'])
    job = schedule_task(task)
    update_task_status(task.id, 'running', expected_status='scheduled')
    update_job_status(job['id'], 'running')
    # Recreate the live manual-run gap: routed result without the defer flag.
    result = create_result({'runtime_job_id': job['id'], 'video_id': plan.content_id,
                            'provider': 'github', 'status': 'submitted',
                            'output': {'github_run_id': 10, 'content_id': plan.content_id}})
    client = FakeGitHub(task.parameters['artifact_name'])
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('REAL NETWORK FORBIDDEN')), \
         patch.object(github_completion, '_verify_public_url', return_value=True):
        class RenderClient:
            def trigger_workflow(self, workflow, branch='main', inputs=None):
                assert workflow == 'render-short01.yml' and branch == 'main'
                return {'status': 'started'}

        provider = GitHubProductionProvider(client=RenderClient())
        provider.monitor.snapshot_run_ids = lambda *_: set()
        provider.monitor.discover_run = lambda **_: {'id': 10, 'status': 'queued', 'conclusion': None}
        submitted = provider.submit_job({'input': {'workflow': task.workflow, 'branch': task.branch,
                                                     'parameters': task.parameters}})
        assert submitted['status'] == 'submitted' and submitted['output']['g4b_no_asset_binding'] is True
        print('ROUTED_SUBMIT_DEFERS_ASSET_BINDING=PASS')

        # The unmodified autonomous path must stop at intent with no POST.
        blocked = github_completion.complete_github_execution(result['id'], job, client=client)
        assert blocked['status'] == 'running' and blocked['promotion_state'] == 'intent', (
            blocked['status'], blocked['promotion_state'], blocked.get('error'))
        assert client.posts == []
        print('AUTONOMOUS_AUTH_GATE=PASS')

        original_artifacts = client.get_workflow_run_artifacts
        client.get_workflow_run_artifacts = lambda _run_id: {
            'artifacts': [{'id': 78, 'name': client.artifact_name, 'expired': False}]}
        mismatched = github_completion.continue_human_authorized_github_completion(result['id'], client=client)
        assert mismatched['promotion_state'] == 'intent' and client.posts == []
        assert 'human_resume_post_claimed_at' not in json.loads(mismatched['promotion_metadata'])
        client.get_workflow_run_artifacts = original_artifacts
        print('MISMATCHED_ARTIFACT_NO_POST=PASS')

        before_jobs, before_results = count('runtime_jobs'), count('production_results')
        first = github_completion.continue_human_authorized_github_completion(result['id'], client=client)
        assert first['status'] == 'completed' and first['promotion_state'] == 'completed', (
            first['status'], first['promotion_state'], first.get('error'),
            json.loads(first.get('promotion_metadata') or '{}'), client.posts)
        assert first['output']['g4b_no_asset_binding'] is True
        assert first['output']['storage_type'] == 'github_pages' and first['output']['asset_ready'] is True
        assert first['asset_id'] is None and len(client.posts) == 1
        assert count('runtime_jobs') == before_jobs and count('production_results') == before_results
        assert count('video_assets') == count('asset_quality_checks') == 0
        assert json.loads(get_result(result['id'])['promotion_metadata'])['promotion_run_id'] == 20
        assert get_task(task.id).status == 'completed'
        print('HUMAN_INTENT_RESUME_EXACTLY_ONCE=PASS')
        print('G4B_DEFERRED_ASSET_BINDING=PASS')

        again = github_completion.continue_human_authorized_github_completion(result['id'], client=client)
        assert again['id'] == first['id'] and len(client.posts) == 1
        assert count('runtime_jobs') == before_jobs and count('production_results') == before_results
        print('PROMOTION_REPLAY=PASS')

        quality = evaluate_production_result_asset(result['id'], downloader=FakeDownloader(), probe=FakeProbe())
        assert quality['status'] == 'PASS'
        assert count('asset_quality_checks') == count('video_assets') == 1
        print('G4D_FIXTURE=PASS')

        # A previously correlated remote promotion run is GET-only, even when
        # the caller explicitly selects the human continuation entrypoint.
        later = save_plan(ContentPlan(**{**plan.to_dict(), 'content_id': 'human-promotion-existing-run'}))
        set_plan_status(later['id'], 'approved')
        later_task = materialize_plan(later['id'])
        later_job = schedule_task(later_task)
        update_task_status(later_task.id, 'running', expected_status='scheduled')
        update_job_status(later_job['id'], 'running')
        later_result = create_result({'runtime_job_id': later_job['id'], 'video_id': 'human-promotion-existing-run',
                                      'provider': 'github', 'status': 'submitted',
                                      'output': {'github_run_id': 10, 'content_id': 'human-promotion-existing-run'}})
        later_client = FakeGitHub(later_task.parameters['artifact_name'])
        stopped = github_completion.complete_github_execution(later_result['id'], later_job, client=later_client)
        assert stopped['promotion_state'] == 'intent' and later_client.posts == []
        later_client.runs.append({'id': 40, 'workflow': 'promote-video-asset.yml', 'status': 'completed',
                                  'conclusion': 'success', 'html_url': 'https://example.invalid/promotion/40',
                                  'created_at': '2999-01-01T00:00:00Z'})
        update_promotion_state(later_result['id'], 'submitted', {'promotion_run_id': 40})
        existing = github_completion.continue_human_authorized_github_completion(later_result['id'], client=later_client)
        assert existing['status'] == 'completed' and later_client.posts == []
        assert existing['output']['g4b_no_asset_binding'] is True
        assert count('video_assets') == count('asset_quality_checks') == 1
        print('EXISTING_RUN_READ_ONLY_REPLAY=PASS')

    # A submitted/running state with an existing remote run can only read back.
    assert client.posts == ['promote-video-asset.yml']
    print('RENDER_POSTS=0')
    print('TOTAL_PROMOTION_POSTS=1')
    print('G4B_HUMAN_PROMOTION_RECOVERY_SMOKE=PASS')


if __name__ == '__main__':
    try:
        main()
    finally:
        gc.collect()
        TEMP.cleanup()
