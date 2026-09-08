from test_database_helper import TEST_DATABASE_PATH, assert_safe_test_database_path
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'os' / 'backend'
sys.path.insert(0, str(BACKEND))
os.chdir(ROOT)

from accounts.manager import create_account, get_account
from accounts.models import Account
from data.manager import get_platform_runtime_capabilities
from data.platform_capabilities import register_platform_capability
from oauth.manager import create_oauth_state, get_token
from oauth.registry import (
    begin_account_connection,
    complete_account_connection,
    get_account_connector_status,
    register_account_connector,
)


PLATFORM = 'mockauth'


def reset_test_db():
    db = TEST_DATABASE_PATH
    if db.exists():
        db.unlink()


def fake_status():
    return {
        'configured': True,
        'missing_configuration': [],
        'callback_path': f'/oauth/{PLATFORM}/callback',
    }


def fake_authorize(account_id, scope_profile):
    state = 'mock-state'
    create_oauth_state(
        account_id,
        state,
        provider=PLATFORM,
        scope_profile=scope_profile,
        code_verifier='mock-verifier',
    )
    return {
        'authorization_url': f'https://example.invalid/oauth/{account_id}',
        'state': state,
        'scope_profile': scope_profile,
        'scopes': ['mock.read'],
    }


def fake_exchange(state_record, authorization_code, state):
    assert authorization_code == 'mock-code'
    assert state == 'mock-state'
    assert state_record['code_verifier'] == 'mock-verifier'
    return {
        'access_token': 'mock-access-token',
        'refresh_token': 'mock-refresh-token',
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
        exchange_factory=fake_exchange,
        replace=True,
    )

    connector = get_account_connector_status(PLATFORM)
    assert connector['registered'] is True
    assert connector['exchange_registered'] is True
    assert connector['configured'] is True
    assert connector['connector_id'] == 'mock_oauth'
    assert connector['callback_path'] == f'/oauth/{PLATFORM}/callback'

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

    completed = complete_account_connection(
        PLATFORM,
        authorization_code='mock-code',
        state=authorization['state'],
        account_id=account['id'],
    )
    assert completed['platform'] == PLATFORM
    assert completed['connector_id'] == 'mock_oauth'
    assert completed['status'] == 'connected'
    assert completed['has_refresh_token'] is True
    assert completed['scopes'] == ['mock.read']
    assert get_account(account['id'])['status'] == 'connected'
    assert get_token(account['id'])['access_token'] == 'mock-access-token'

    runtime = get_platform_runtime_capabilities(PLATFORM)
    assert runtime['account_connector_registered'] is True
    assert runtime['account_connector']['connector_id'] == 'mock_oauth'
    assert runtime['account_connector']['exchange_registered'] is True
    assert runtime['publish_supported'] is True

    youtube_runtime = get_platform_runtime_capabilities('youtube')
    assert youtube_runtime['content_sync_registered'] is True
    assert youtube_runtime['analytics_sync_registered'] is True
    assert youtube_runtime['account_connector_registered'] is True
    assert youtube_runtime['account_connector']['connector_id'] == 'google_oauth'
    assert youtube_runtime['account_connector']['exchange_registered'] is True

    oauth_router_source = (BACKEND / 'routers' / 'oauth.py').read_text(encoding='utf-8')
    assert "/oauth/connect/{platform}/{account_id}" in oauth_router_source
    assert "/oauth/exchange/{platform}" in oauth_router_source
    assert 'complete_account_connection' in oauth_router_source
    assert "exchange_account_connection('youtube', request)" in oauth_router_source

    print('Account connector runtime smoke test passed')
    print('Generic connector registry -> authorization + code exchange dispatch')
    print('Platform runtime -> publish/content/analytics/account connector metadata')
    print('YouTube compatibility endpoints -> same connector boundary')


if __name__ == '__main__':
    main()
