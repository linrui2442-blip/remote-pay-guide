from test_database_helper import TEST_DATABASE_PATH, assert_safe_test_database_path
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'os' / 'backend'
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from analytics.collector import AnalyticsCollector
from analytics.registry import build_analytics_adapters, register_analytics_adapter
from data.platform_capabilities import register_platform_capability
from integrations.sync_planner import build_account_sync_plan
from integrations.sync_registry import (
    register_content_sync_adapter,
    run_content_sync,
)
from integrations.sync_scheduler import execute_account_sync


PLATFORM = 'mocknet'


class FakeContentSync:
    calls = []

    def sync(self, account_id, max_results=10, sync_mode='incremental'):
        self.__class__.calls.append(
            {
                'account_id': account_id,
                'max_results': max_results,
                'sync_mode': sync_mode,
            }
        )
        return {
            'platform': PLATFORM,
            'account_id': account_id,
            'tracking_window': max_results,
            'sync_mode': sync_mode,
        }


class FakeAnalyticsAdapter:
    def readiness(self, account_id=None):
        return {
            'ready': account_id is not None,
            'collector_registered': True,
            'reason': None if account_id is not None else 'account_id required',
        }

    def collect_video(self, video_id, *, account_id, **kwargs):
        return {
            'platform': PLATFORM,
            'video_id': video_id,
            'account_id': account_id,
            'views': 11,
        }

    def collect_account(self, *, account_id, start_date=None, end_date=None):
        return {
            'platform': PLATFORM,
            'account_id': account_id,
            'period_start': start_date,
            'period_end': end_date,
            'metrics': {'views': 22},
        }


class FakeBatchCollector:
    def collect_account(self, platform, account_id=None, **kwargs):
        assert platform == PLATFORM
        return {
            'platform': platform,
            'account_id': account_id,
            'period_end': kwargs.get('end_date'),
            'metrics': {'views': 33},
        }

    def collect(self, *args, **kwargs):
        raise AssertionError('no publish tasks should exist in registry smoke test')


def fake_intelligence_refresh(account_id, platform=None, limit=10):
    assert account_id == 1400
    assert platform == PLATFORM
    assert limit == 7
    return {
        'account_id': account_id,
        'platform': platform,
        'found': 0,
        'generated': 0,
        'reused': 0,
        'top_strategy': None,
        'snapshots': [],
    }


def reset_test_db():
    db = TEST_DATABASE_PATH
    if db.exists():
        db.unlink()


def main():
    reset_test_db()
    register_platform_capability(
        PLATFORM,
        publish_supported=False,
        analytics_supported=True,
        oauth_required=False,
        metric_types=['views'],
    )
    register_content_sync_adapter(
        PLATFORM,
        FakeContentSync,
        active_limit=7,
        replace=True,
    )
    register_analytics_adapter(
        PLATFORM,
        lambda **context: FakeAnalyticsAdapter(),
        replace=True,
    )

    content = run_content_sync(
        1400,
        PLATFORM,
        max_results=99,
        sync_mode='incremental',
    )
    assert content['tracking_window'] == 7
    assert FakeContentSync.calls[-1]['max_results'] == 7

    collector = AnalyticsCollector(adapters=build_analytics_adapters())
    readiness = collector.readiness(PLATFORM, account_id=1400)
    assert readiness['ready'] is True
    video_metric = collector.collect(
        'video-1400',
        PLATFORM,
        account_id=1400,
    )
    assert video_metric['views'] == 11

    plan = build_account_sync_plan(
        1400,
        PLATFORM,
        requested_limit=50,
    )
    assert plan['active_limit'] == 7
    assert plan['intelligence_feedback_enabled'] is True
    assert [item['operation'] for item in plan['operations']] == [
        'content_sync',
        'analytics_sync',
        'intelligence_feedback',
    ]

    scheduled = execute_account_sync(
        1400,
        PLATFORM,
        requested_limit=50,
        end_date='2026-09-06',
        analytics_collector=FakeBatchCollector(),
        intelligence_refresher=fake_intelligence_refresh,
    )
    assert scheduled['status'] == 'success'
    assert scheduled['planned'] == 3
    assert scheduled['completed'] == 3
    assert scheduled['failed'] == 0
    assert scheduled['skipped'] == 0
    assert [item['operation'] for item in scheduled['results']] == [
        'content_sync',
        'analytics_sync',
        'intelligence_feedback',
    ]

    account_router_source = (BACKEND / 'routers' / 'accounts.py').read_text(encoding='utf-8')
    collector_source = (BACKEND / 'analytics' / 'collector.py').read_text(encoding='utf-8')
    scheduler_source = (BACKEND / 'integrations' / 'sync_scheduler.py').read_text(encoding='utf-8')
    assert "platform != 'youtube'" not in account_router_source
    assert 'YouTubeContentSync' not in account_router_source
    assert 'if normalized == "youtube"' not in collector_source
    assert "if normalized == 'youtube'" not in collector_source
    assert 'refresh_account_feedback' in scheduler_source
    assert 'auto' not in scheduler_source.lower() or 'automatically executing' in scheduler_source

    print('Provider-neutral sync registry smoke test passed')
    print('Content registry -> active limit enforced without router platform branching')
    print('Analytics registry -> fake platform collected without collector platform branching')
    print('Sync planner/scheduler -> content + analytics + Intelligence feedback in order')


if __name__ == '__main__':
    main()
