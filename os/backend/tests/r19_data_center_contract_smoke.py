from test_database_helper import TEST_DATABASE_PATH, assert_safe_test_database_path
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'os' / 'backend'
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)
os.environ.setdefault('YOUTUBE_OAUTH_CLIENT_ID', 'data-center-test-client')
os.environ.setdefault('YOUTUBE_OAUTH_CLIENT_SECRET', 'data-center-test-secret')

from analytics.collector import AnalyticsCollectionNotReady, AnalyticsCollector
from analytics.manager import get_latest_metrics, get_metrics, save_metric
from analytics.models import AnalyticsMetric
from analytics.publish_bridge import collect_publish_task_metrics
from analytics.youtube_api import YouTubeAnalyticsAPIClient
from data.manager import (
    get_content_funnel_data,
    get_platform,
    get_platform_runtime_capabilities,
    get_platforms,
    get_statistics,
    record_conversion_event,
    record_intent_event,
)
from data.models import ConversionRecord, IntentEvent
from data.platform_capabilities import register_platform_capability
from intelligence.feedback import analyze_feedback
from intelligence.strategy import build_production_strategy
from oauth.manager import (
    consume_oauth_state,
    create_oauth_state,
    create_token,
    get_token,
)
from oauth.providers.youtube import (
    YOUTUBE_ANALYTICS_SCOPE,
    YOUTUBE_READ_SCOPE,
    YOUTUBE_UPLOAD_SCOPE,
    YouTubeOAuthProvider,
)
from publish.manager import create_publish_task, update_publish_status


def reset_test_db():
    db_path = TEST_DATABASE_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()


def main():
    reset_test_db()

    save_metric(
        AnalyticsMetric(
            video_id='verify-video',
            content_id='verify-content',
            platform='youtube',
            source='verification',
            impressions=1000,
            views=100,
            clicks=10,
            watch_time=500,
            likes=5,
            comments=2,
            shares=1,
        )
    )
    save_metric(
        AnalyticsMetric(
            video_id='verify-video',
            content_id='verify-content',
            platform='youtube',
            source='verification',
            impressions=1200,
            views=120,
            clicks=12,
            watch_time=600,
            likes=6,
            comments=3,
            shares=2,
        )
    )
    assert len(get_metrics()) == 2
    assert len(get_latest_metrics()) == 1
    assert get_latest_metrics()[0]['views'] == 120

    record_intent_event(
        IntentEvent(
            content_id='verify-content',
            video_id='verify-video',
            source='ga4',
            event_type='page_view',
        )
    )
    record_intent_event(
        IntentEvent(
            content_id='verify-content',
            video_id='verify-video',
            source='ga4',
            event_type='binance_referral_click',
        )
    )
    record_conversion_event(
        ConversionRecord(
            content_id='verify-content',
            video_id='verify-video',
            source='verification',
            conversion_type='referral_conversion',
            value=1,
        )
    )

    funnel = get_content_funnel_data('verify-content')
    assert funnel['traffic']['records'] == 1
    assert funnel['traffic']['impressions'] == 1200
    assert funnel['traffic']['views'] == 120
    assert funnel['traffic']['clicks'] == 12
    assert funnel['intent']['total'] == 2
    assert funnel['intent']['by_type']['binance_referral_click'] == 1
    assert funnel['conversion']['total'] == 1
    assert funnel['conversion']['value'] == 1

    statistics = get_statistics()
    assert statistics['total_metrics'] == 2
    assert statistics['intent_events'] == 2
    assert statistics['referral_clicks'] == 1
    assert statistics['conversions'] == 1

    feedback = analyze_feedback(
        {
            'video_id': 'verify-video',
            'performance': get_latest_metrics(),
            'funnel': funnel,
        }
    )
    assert feedback.intent_events == 2
    assert feedback.referral_clicks == 1
    assert feedback.conversions == 1
    assert 'attributed conversion observed' in feedback.successful_patterns

    strategy = build_production_strategy(feedback)
    assert strategy.parameters['strategy_type'] == 'scale_conversion_winner'
    assert strategy.parameters['conversions'] == 1

    platforms = get_platforms()
    assert {item['platform_name'] for item in platforms} >= {
        'youtube', 'instagram', 'facebook', 'tiktok'
    }
    youtube_capability = get_platform('youtube')
    assert youtube_capability['publish_supported'] is True
    assert youtube_capability['analytics_supported'] is True
    assert 'views' in youtube_capability['metric_types']
    assert 'retention' in youtube_capability['metric_types']
    assert 'impressions' not in youtube_capability['metric_types']

    register_platform_capability(
        'future-platform',
        publish_supported=True,
        analytics_supported=True,
        oauth_required=True,
        metric_types=['views', 'clicks'],
    )
    future_runtime = get_platform_runtime_capabilities('future-platform')
    # Runtime capabilities intentionally grow when adapters/connectors are
    # registered. Assert the stable contract instead of exact dict equality.
    assert future_runtime['platform'] == 'future-platform'
    assert future_runtime['publish_supported'] is True
    assert future_runtime['analytics_supported'] is True
    assert future_runtime['metric_types'] == ['clicks', 'views']
    assert future_runtime['content_sync_registered'] is False
    assert future_runtime['analytics_sync_registered'] is False
    assert future_runtime['account_connector_registered'] is False

    publish_provider = YouTubeOAuthProvider(
        client_id='verify-client',
        client_secret='verify-secret',
        redirect_uri='http://localhost/callback',
        scope_profile='publish',
    )
    full_provider = YouTubeOAuthProvider(
        client_id='verify-client',
        client_secret='verify-secret',
        redirect_uri='http://localhost/callback',
        scope_profile='full',
    )
    assert publish_provider.scopes == [YOUTUBE_UPLOAD_SCOPE]
    assert set(full_provider.scopes) == {
        YOUTUBE_UPLOAD_SCOPE,
        YOUTUBE_READ_SCOPE,
        YOUTUBE_ANALYTICS_SCOPE,
    }

    create_oauth_state(
        999,
        'verify-state',
        provider='youtube',
        scope_profile='full',
    )
    state_record = consume_oauth_state(
        999,
        'verify-state',
        provider='youtube',
        return_record=True,
    )
    assert state_record['scope_profile'] == 'full'
    assert consume_oauth_state(999, 'verify-state', provider='youtube') is False

    create_token({
        'account_id': 999,
        'provider': 'youtube',
        'access_token': 'verify-access',
        'refresh_token': 'verify-refresh',
        'scopes': [YOUTUBE_UPLOAD_SCOPE],
    })
    stored_token = get_token(999)
    assert stored_token['provider'] == 'youtube'
    assert stored_token['scopes'] == [YOUTUBE_UPLOAD_SCOPE]

    collector = AnalyticsCollector()
    youtube_status = collector.readiness('youtube')
    assert youtube_status['ready'] is False
    assert youtube_status['collector_registered'] is True
    assert youtube_status['collector_enabled'] is True
    assert 'account_id is required' in youtube_status['reason']
    try:
        collector.collect('verify-video', 'youtube')
    except AnalyticsCollectionNotReady:
        pass
    else:
        raise AssertionError('collector must require an account-specific credential')

    account_status = collector.readiness('youtube', account_id=999)
    assert account_status['credential_found'] is True
    assert account_status['credential_ready'] is False
    assert account_status['requires_reauthorization'] is True
    assert account_status['ready'] is False

    create_token({
        'account_id': 999,
        'provider': 'youtube',
        'access_token': 'verify-access-full',
        'refresh_token': 'verify-refresh',
        'scopes': [
            YOUTUBE_UPLOAD_SCOPE,
            YOUTUBE_READ_SCOPE,
            YOUTUBE_ANALYTICS_SCOPE,
        ],
    })
    full_account_status = collector.readiness('youtube', account_id=999)
    assert full_account_status['credential_ready'] is True
    assert full_account_status['requires_reauthorization'] is False
    assert full_account_status['collector_enabled'] is True
    assert full_account_status['ready'] is True

    normalized = YouTubeAnalyticsAPIClient.normalize_response({
        'columnHeaders': [
            {'name': 'views'},
            {'name': 'estimatedMinutesWatched'},
            {'name': 'averageViewDuration'},
            {'name': 'averageViewPercentage'},
            {'name': 'likes'},
            {'name': 'comments'},
            {'name': 'shares'},
        ],
        'rows': [[321, 15.5, 42.5, 67.25, 11, 4, 3]],
    })
    assert normalized == {
        'views': 321,
        'watch_time': 930,
        'average_view_duration': 42.5,
        'retention': 67.25,
        'likes': 11,
        'comments': 4,
        'shares': 3,
    }

    class FakeYouTubeAnalyticsClient:
        def initialize(self, credentials=None):
            assert credentials is not None
            return {'platform': 'youtube', 'status': 'ready'}

        def collect_video_metrics(self, video_id, start_date=None, end_date=None):
            assert video_id == 'live-video'
            assert start_date == '2026-08-01'
            assert end_date == '2026-08-31'
            return {
                'views': 321,
                'watch_time': 930,
                'average_view_duration': 42.5,
                'retention': 67.25,
                'likes': 11,
                'comments': 4,
                'shares': 3,
                'start_date': start_date,
                'end_date': end_date,
            }

    create_token({
        'account_id': 1000,
        'provider': 'youtube',
        'access_token': 'verify-full-access',
        'scopes': [YOUTUBE_READ_SCOPE, YOUTUBE_ANALYTICS_SCOPE],
    })
    live_collector = AnalyticsCollector(
        youtube_client_factory=FakeYouTubeAnalyticsClient
    )
    live_status = live_collector.readiness('youtube', account_id=1000)
    assert live_status['ready'] is True
    saved_live_metric = live_collector.collect(
        'live-video',
        'youtube',
        account_id=1000,
        content_id='live-content',
        start_date='2026-08-01',
        end_date='2026-08-31',
    )
    assert saved_live_metric['source'] == 'youtube_analytics_api'
    assert saved_live_metric['content_id'] == 'live-content'
    assert saved_live_metric['views'] == 321
    assert saved_live_metric['watch_time'] == 930
    assert saved_live_metric['retention'] == 67.25

    publish_task = create_publish_task({
        'asset_id': 'publish-asset',
        'video_id': 'publish-content',
        'platform': 'youtube',
        'account_id': 1000,
        'status': 'pending',
    })
    published_task = update_publish_status(
        publish_task['id'],
        'published',
        platform_video_id='live-video',
        published_url='https://www.youtube.com/watch?v=live-video',
    )
    assert published_task['platform_video_id'] == 'live-video'
    bridged_metric = collect_publish_task_metrics(
        published_task['id'],
        collector=live_collector,
        start_date='2026-08-01',
        end_date='2026-08-31',
    )
    assert bridged_metric['video_id'] == 'live-video'
    assert bridged_metric['content_id'] == 'publish-content'
    assert bridged_metric['platform'] == 'youtube'
    assert bridged_metric['views'] == 321

    future_status = collector.readiness('future-platform')
    assert future_status['ready'] is False
    assert future_status['collector_registered'] is False
    assert future_status['analytics_supported'] is True
    assert 'adapter is not registered' in future_status['reason']

    instagram_status = collector.readiness('instagram')
    assert instagram_status['ready'] is False
    assert instagram_status['analytics_supported'] is False
    assert 'not enabled' in instagram_status['reason']

    print('Data Center contract smoke test passed')
    print(funnel)
    print(statistics)
    print(strategy)
    print(future_runtime)
    print(full_account_status)
    print(bridged_metric)


if __name__ == '__main__':
    main()
