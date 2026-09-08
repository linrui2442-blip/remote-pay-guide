from test_database_helper import TEST_DATABASE_PATH, assert_safe_test_database_path
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
from production.runtime.orchestrator import execute_production_task
from production.tasks.execution import get_execution_readiness
from production.tasks.manager import create_task, get_task
from production.tasks.models import ProductionTask
from production.tasks.scheduler import schedule_task


def reset_test_db():
    db = TEST_DATABASE_PATH
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


class ReadyAIGatewayProvider(AIGatewayProvider):
    def get_provider_status(self):
        return {
            'provider': 'ai_gateway',
            'status': 'ready',
            'configured': True,
            'transport': 'remote_http',
            'local_inference': False,
            'missing_configuration': [],
        }


def make_remote_task(objective='Create a controlled follow-up for the conversion-winning angle'):
    return create_task(
        ProductionTask(
            source='ai_intelligence',
            objective=objective,
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

    # The explicit Run action now means schedule + Runtime Worker execution.
    fake_gateway = FakeGateway()
    fake_provider = ReadyAIGatewayProvider(gateway=fake_gateway)
    previous_provider = production_provider_registry['ai_gateway']
    production_provider_registry['ai_gateway'] = fake_provider
    try:
        remote = make_remote_task()
        remote_readiness = get_execution_readiness(remote)
        assert remote_readiness['ready'] is True

        execution_result = execute_production_task(remote)
        assert execution_result['provider_readiness']['ready'] is True
        assert execution_result['runtime_job']['status'] == 'completed'
        assert execution_result['result']['status'] == 'completed'
        assert execution_result['production_task'].status == 'completed'
        assert execution_result['result']['production_result']['status'] == 'completed'

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

    # Provider runtime readiness is also checked before scheduling. With no relay
    # configured, an explicit AI Run leaves the task in created state.
    unconfigured_task = make_remote_task('test unconfigured remote provider')
    jobs_before = len(get_jobs())
    try:
        execute_production_task(unconfigured_task)
        raise AssertionError('unconfigured AI provider should not execute')
    except ValueError as exc:
        assert 'not ready' in str(exc).lower()
    assert get_task(unconfigured_task.id).status == 'created'
    assert len(get_jobs()) == jobs_before

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
    print('Production Run -> schedule -> Runtime Worker -> provider -> result')
    print('AI Runtime Job -> normalized AIRequest -> remote gateway provider')
    print('Unconfigured AI provider -> blocked before lifecycle mutation')
    print('AI video provider -> external HTTP only; no local inference fallback')
    print('AI Gateway endpoint -> persisted OS setting -> live provider readiness')


if __name__ == '__main__':
    main()
