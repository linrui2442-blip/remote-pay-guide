import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'os' / 'backend'
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from ai.models import AIResponse
from ai.providers.video import VideoProvider
from config.ai_gateway import get_ai_gateway_settings, save_ai_gateway_settings
from production.providers import production_provider_registry
from production.providers.ai_gateway import AIGatewayProvider
from production.runtime.manager import get_jobs
from production.runtime.worker import ProductionRuntimeWorker
from production.tasks.execution import get_execution_readiness
from production.tasks.manager import create_task, get_task
from production.tasks.models import ProductionTask
from production.tasks.scheduler import schedule_task


def reset_test_db():
    Path('os/database').mkdir(parents=True, exist_ok=True)
    db = Path('os/database/os.db')
    if db.exists():
        db.unlink()


class FakeGateway:
    def __init__(self):
        self.requests = []

    def request(self, request):
        self.requests.append(request)
        return AIResponse(
            status='completed',
            model=request.model,
            output={
                'asset_url': 'https://example.invalid/remote-video.mp4',
                'remote_job_id': 'remote-job-17',
            },
        )


def main():
    reset_test_db()

    blocked = create_task(
        ProductionTask(
            source='ai_intelligence',
            objective='test github execution readiness',
            provider='github',
            template='short_video_template',
            parameters={'task_type': 'video_batch'},
            resources=['source-content'],
            task_type='video_batch',
            workflow='',
            branch='main',
        )
    )
    readiness = get_execution_readiness(blocked)
    assert readiness['ready'] is False
    assert 'workflow' in readiness['missing']

    try:
        schedule_task(blocked)
        raise AssertionError('GitHub task without workflow should not schedule')
    except ValueError as exc:
        assert 'workflow' in str(exc).lower()

    # Contract validation must happen before lifecycle mutation or Runtime Job creation.
    blocked_after = get_task(blocked.id)
    assert blocked_after.status == 'created'
    assert get_jobs() == []

    fake_gateway = FakeGateway()
    fake_provider = AIGatewayProvider(gateway=fake_gateway)
    previous_provider = production_provider_registry['ai_gateway']
    production_provider_registry['ai_gateway'] = fake_provider
    try:
        remote = create_task(
            ProductionTask(
                source='ai_intelligence',
                objective='Create a controlled follow-up for the conversion-winning angle',
                provider='ai_gateway',
                template='short_video_template',
                parameters={
                    'task_type': 'video_generation',
                    'prompt': 'Create a realistic vertical remote-payment explainer video.',
                    'model': 'auto',
                    'input': {'content_id': 'winner-content'},
                    'options': {'aspect_ratio': '9:16', 'duration_seconds': 30},
                },
                resources=['winner-content'],
                task_type='video_generation',
                workflow='',
                branch='main',
            )
        )
        remote_readiness = get_execution_readiness(remote)
        assert remote_readiness['ready'] is True

        job = schedule_task(remote)
        assert job['provider'] == 'ai_gateway'
        assert get_task(remote.id).status == 'scheduled'

        result = ProductionRuntimeWorker().run(job)
        assert result['status'] == 'completed', result
        assert get_task(remote.id).status == 'completed'
        assert result['production_result']['status'] == 'completed'

        assert len(fake_gateway.requests) == 1
        request = fake_gateway.requests[0]
        assert request.task_type == 'video_generation'
        assert request.prompt == 'Create a realistic vertical remote-payment explainer video.'
        assert request.input['objective'].startswith('Create a controlled follow-up')
        assert request.input['template'] == 'short_video_template'
        assert request.input['resources'] == ['winner-content']
        assert request.input['content_id'] == 'winner-content'
        assert request.options['aspect_ratio'] == '9:16'
        assert request.options['duration_seconds'] == 30
    finally:
        production_provider_registry['ai_gateway'] = previous_provider

    # The real video provider must fail closed when no external relay is configured.
    unconfigured = VideoProvider(endpoint='', api_key='')
    status = unconfigured.initialize()
    assert status['configured'] is False
    assert status['local_inference'] is False
    response = unconfigured.request(fake_gateway.requests[0])
    assert response.status == 'failed'
    assert 'AI_GATEWAY_VIDEO_URL' in response.error

    # A non-secret relay endpoint can be persisted in OS settings and is picked
    # up dynamically without recreating the production provider registry.
    saved = save_ai_gateway_settings('https://relay.example.test/v1/video')
    assert saved['configured'] is True
    assert saved['source'] == 'os_settings'
    assert saved['api_key_configured'] is bool(os.getenv('AI_GATEWAY_API_KEY'))
    persisted = get_ai_gateway_settings()
    assert persisted['video_url'] == 'https://relay.example.test/v1/video'
    dynamic_provider = VideoProvider(api_key='')
    dynamic_status = dynamic_provider.initialize()
    assert dynamic_status['configured'] is True
    assert dynamic_status['endpoint_source'] == 'os_settings'
    assert dynamic_status['local_inference'] is False

    print('Production execution contract smoke test passed')
    print('GitHub missing workflow -> blocked before scheduling')
    print('AI Runtime Job -> normalized AIRequest -> remote gateway provider')
    print('AI video provider -> external HTTP only; no local inference fallback')
    print('AI Gateway endpoint -> persisted OS setting -> live provider readiness')


if __name__ == '__main__':
    main()
