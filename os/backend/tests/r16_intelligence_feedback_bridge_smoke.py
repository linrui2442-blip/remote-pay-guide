import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'os' / 'backend'
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from accounts.manager import create_account
from accounts.models import Account
from analytics.manager import save_metric
from analytics.models import AnalyticsMetric
from data.growth import record_conversion, record_intent
from data.models import ConversionRecord, IntentEvent
from intelligence.feedback_bridge import (
    get_latest_account_feedback,
    refresh_account_feedback,
)
from production.tasks.manager import get_tasks


PLATFORM = 'mockintel'


def reset_test_db():
    Path('os/database').mkdir(parents=True, exist_ok=True)
    db = Path('os/database/os.db')
    if db.exists():
        db.unlink()


def main():
    reset_test_db()
    account = create_account(
        Account(
            platform=PLATFORM,
            account_name='Intelligence Test Account',
            status='connected',
        )
    )

    save_metric(
        AnalyticsMetric(
            video_id='winner-platform-video',
            content_id='winner-content',
            platform=PLATFORM,
            account_id=account['id'],
            source='test',
            views=120,
            likes=4,
            comments=1,
            shares=0,
            watch_time=60,
            retention=35.0,
            period_start='2026-08-10',
            period_end='2026-09-06',
        )
    )
    save_metric(
        AnalyticsMetric(
            video_id='traffic-platform-video',
            content_id='traffic-content',
            platform=PLATFORM,
            account_id=account['id'],
            source='test',
            views=6000,
            likes=800,
            comments=80,
            shares=90,
            watch_time=5000,
            retention=78.0,
            period_start='2026-08-10',
            period_end='2026-09-06',
        )
    )

    record_intent(
        IntentEvent(
            content_id='winner-content',
            video_id='winner-platform-video',
            event_type='binance_referral_click',
            source='test',
        )
    )
    record_conversion(
        ConversionRecord(
            content_id='winner-content',
            video_id='winner-platform-video',
            conversion_type='binance_referral_signup',
            source='test',
            value=5.0,
            currency='USD',
        )
    )

    first = refresh_account_feedback(
        account['id'],
        platform=PLATFORM,
        limit=10,
    )
    assert first['found'] == 2
    assert first['generated'] == 2
    assert first['reused'] == 0
    assert first['top_strategy']['content_id'] == 'winner-content'
    assert first['top_strategy']['strategy_type'] == 'scale_conversion_winner'
    assert first['top_strategy']['feedback']['conversions'] == 1
    assert first['top_strategy']['feedback']['referral_clicks'] == 1
    assert first['top_strategy']['feedback']['conversion_value'] == 5.0

    # Re-running against an unchanged Data Center snapshot must not create
    # duplicate strategy records or duplicate Production Center tasks.
    second = refresh_account_feedback(
        account['id'],
        platform=PLATFORM,
        limit=10,
    )
    assert second['generated'] == 0
    assert second['reused'] == 2

    latest = get_latest_account_feedback(account['id'], platform=PLATFORM)
    assert len(latest) == 2
    assert latest[0]['content_id'] == 'winner-content'
    assert latest[0]['strategy']['parameters']['strategy_type'] == 'scale_conversion_winner'
    assert get_tasks() == []

    print('Intelligence feedback bridge smoke test passed')
    print('Data Center ACTIVE rows -> feedback -> strategy snapshot')
    print('Conversion winner outranks higher-traffic vanity winner')
    print('Unchanged snapshots are de-duplicated; no ProductionTask auto-created')


if __name__ == '__main__':
    main()
