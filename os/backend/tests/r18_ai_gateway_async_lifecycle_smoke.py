import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'os' / 'backend'
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from ai.models import AIResponse
from assets.manager import get_assets
from production.providers import production_provider_registry
from production.providers.ai_gateway import AIGatewayProvider
from production.results.manager import get_results
from production.runtime.manager import get_latest_job_for_task
from production.runtime.orchestrator import execute_production_task, refresh_production_task
from production.runtime.poller import ProductionRuntimePoller
from production.tasks.manager import create_task, get_task
from production.tasks.models import ProductionTask


def reset_test_db():
    Path('os/database').mkdir(parents=True, exist_ok=True)
    db = Path('os/database/os.db')
    if db.exists():
        db.unlink()


class ReadyVideoTransport:
    def initialize(self):
        return {
            'status': 'ready',
            'configured': True,
            'transport': 'remote_http',
            'local_inference': False,
            'missing_configuration': [],
        }


class AsyncGateway:
    def __init__(self):
        self.providers = {'video': ReadyVideoTransport()}
        self.submit_count = 0
        self.poll_count = 0

    def request(self, request):
        self.submit_count += 1
        return AIResponse(
            status='submitted',
            model=request.model,
            output={
                'remote_job_id': 'remote-async-18',
                'status_url': 'https://relay.example.test/jobs/remote-async-18',
            },
        )

    def poll(self, task_type, output, *, model='auto'):
        assert task_type == 'video_generation'
        assert output['remote_job_id'] == 'remote-async-18'
        self.poll_count += 1
        if self.poll_count == 1:
            return AIResponse(
                status='running',
                model=model,
                output={
                    **output,
                    'progress': 55,
                },
            )
        return AIResponse(
            status='completed',
            model=model,
            output={
                **output,
                'progress': 100,
                'asset_url': 'https://cdn.example.test/videos/remote-async-18.mp4',
            },
        )


class MissingAssetGateway(AsyncGateway):
    def request(self, request):
        self.submit_count += 1
        return AIResponse(
            status='completed',
            model=request.model,
            output={'remote_job_id': 'missing-asset'},
        )


def make_task(objective='async remote generation'):
    return create_task(
        ProductionTask(
            source='ai_intelligence',
            objective=objective,
            provider='ai_gateway',
            template='short_video_template',
            parameters={
                'task_type': 'video_generation',
                'prompt': 'Generate a realistic vertical video.',
                'model': 'auto',
            },
            resources=['source-content'],
            task_type='video_generation',
            workflow='',
            branch='main',
        )
    )


def main():
    reset_test_db()
    previous = production_provider_registry['ai_gateway']

    gateway = AsyncGateway()
    production_provider_registry['ai_gateway'] = AIGatewayProvider(gateway=gateway)
    try:
        task = make_task()
        started = execute_production_task(task)
        assert started['result']['status'] == 'submitted'
        assert get_task(task.id).status == 'running'
        assert gateway.submit_count == 1
        assert gateway.poll_count == 0

        results = get_results()
        assert len(results) == 1
        assert results[0]['status'] == 'submitted'
        result_id = results[0]['id']
        job_id = started['runtime_job']['id']

        # Background poller refreshes active jobs without re-submitting them.
        poller = ProductionRuntimePoller(interval_seconds=999)
        automatic = poller.poll_once()
        assert automatic['checked'] == 1
        assert automatic['refreshed'] == 1
        assert automatic['failed'] == 0
        first_result = get_results()[0]
        assert first_result['id'] == result_id
        assert first_result['status'] == 'running'
        assert get_task(task.id).status == 'running'
        assert gateway.submit_count == 1
        assert gateway.poll_count == 1
        assert len(get_results()) == 1

        # Explicit UI/API refresh remains available as a deterministic fallback.
        second_poll = refresh_production_task(get_task(task.id))
        assert second_poll['result']['status'] == 'completed', second_poll
        assert second_poll['result']['production_result']['id'] == result_id
        assert get_task(task.id).status == 'completed'
        assert gateway.submit_count == 1
        assert gateway.poll_count == 2
        assert len(get_results()) == 1

        runtime_job = get_latest_job_for_task(task.id)
        assert runtime_job['id'] == job_id
        assert runtime_job['status'] == 'completed'

        assets = get_assets()
        assert len(assets) == 1
        assert assets[0]['source_provider'] == 'ai_gateway'
        assert assets[0]['storage_type'] == 'ai_output'
        assert assets[0]['status'] == 'ready'
        assert assets[0]['asset_url'].endswith('/remote-async-18.mp4')
    finally:
        production_provider_registry['ai_gateway'] = previous

    # A remote AI provider cannot claim completion without a remote asset URL.
    reset_test_db()
    missing_gateway = MissingAssetGateway()
    production_provider_registry['ai_gateway'] = AIGatewayProvider(gateway=missing_gateway)
    try:
        missing_task = make_task('completed response without remote asset')
        missing = execute_production_task(missing_task)
        assert missing['result']['status'] == 'failed', missing
        assert 'remote asset URL' in missing['result']['error']
        assert get_task(missing_task.id).status == 'failed'
        assert get_assets() == []
    finally:
        production_provider_registry['ai_gateway'] = previous

    print('AI Gateway async lifecycle smoke test passed')
    print('submit once -> background running poll -> explicit completed poll')
    print('one Runtime Job -> one ProductionResult -> one remote VideoAsset')
    print('completed without remote URL -> failed closed; no local fallback')


if __name__ == '__main__':
    main()
