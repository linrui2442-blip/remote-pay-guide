import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'os' / 'backend'
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from accounts.manager import create_account
from accounts.models import Account
from data.manager import get_platform_runtime_capabilities
from data.platform_capabilities import register_platform_capability
from oauth.registry import (
    begin_account_connection,
    get_account_connector_status,
    register_account_connector,
)


PLATFORM = 'mockauth'


def reset_test_db():
    Path('os/database').mkdir(parents=True, exist_ok=True)
    db = Path('os/database/os.db')
    if db.exists():
        db.unlink()


def fake_status():
    return {
        'configured': True,
        'missing_configuration': [],
    }


def fake_authorize(account_id, scope_profile):
    return {
        'authorization_url': f'https://example.invalid/oauth/{account_id}',
        'state': 'mock-state',
        'scope_profile': scope_profile,
        'scopes': ['mock.read'],
    }


def main():
    reset_test_db()
    register_platform_capability(
        PLATFORM,
        publish_supported=True,
        analytics_supported=False,
        oauth_required=True,
        metric_types=[],
    )
    register_account_connector(
        PLATFORM,
        connector_id='mock_oauth',
        status_factory=fake_status,
        authorize_factory=fake_authorize,
        replace=True,
    )

    connector = get_account_connector_status(PLATFORM)
    assert connector['registered'] is True
    assert connector['configured'] is True
    assert connector['connector_id'] == 'mock_oauth'

    account = create_account(
        Account(
            platform=PLATFORM,
            account_name='Mock Auth Account',
            status='inactive',
        )
    )
    authorization = begin_account_connection(
        PLATFORM,
        account['id'],
        scope_profile='full',
    )
    assert authorization['platform'] == PLATFORM
    assert authorization['connector_id'] == 'mock_oauth'
    assert authorization['authorization_url'].endswith(f"/{account['id']}")

    runtime = get_platform_runtime_capabilities(PLATFORM)
    assert runtime['account_connector_registered'] is True
    assert runtime['account_connector']['connector_id'] == 'mock_oauth'
    assert runtime['publish_supported'] is True

    youtube_runtime = get_platform_runtime_capabilities('youtube')
    assert youtube_runtime['content_sync_registered'] is True
    assert youtube_runtime['analytics_sync_registered'] is True
    assert youtube_runtime['account_connector_registered'] is True
    assert youtube_runtime['account_connector']['connector_id'] == 'google_oauth'

    oauth_router_source = (BACKEND / 'routers' / 'oauth.py').read_text(encoding='utf-8')
    assert "/oauth/connect/{platform}/{account_id}" in oauth_router_source
    assert 'begin_account_connection' in oauth_router_source

    print('Account connector runtime smoke test passed')
    print('Generic connector registry -> account authorization dispatch')
    print('Platform runtime -> publish/content/analytics/account connector metadata')
    print('YouTube -> registered through the same connector boundary')


if __name__ == '__main__':
    main()
