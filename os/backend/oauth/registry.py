from dataclasses import dataclass
from typing import Any, Callable

from accounts.manager import get_account
from oauth.manager import create_oauth_state
from oauth.providers.youtube import (
    YouTubeOAuthConfigurationError,
    YouTubeOAuthProvider,
)


@dataclass(frozen=True)
class AccountConnectorRegistration:
    platform: str
    connector_id: str
    status_factory: Callable[[], dict[str, Any]]
    authorize_factory: Callable[[int, str], dict[str, Any]]


_ACCOUNT_CONNECTORS: dict[str, AccountConnectorRegistration] = {}


def _normalize_platform(platform: str | None) -> str:
    return str(platform or '').strip().lower()


def register_account_connector(
    platform: str,
    *,
    connector_id: str,
    status_factory: Callable[[], dict[str, Any]],
    authorize_factory: Callable[[int, str], dict[str, Any]],
    replace: bool = False,
) -> AccountConnectorRegistration:
    normalized = _normalize_platform(platform)
    if not normalized:
        raise ValueError('platform is required')
    if normalized in _ACCOUNT_CONNECTORS and not replace:
        raise ValueError(f'account connector already registered for {normalized}')

    registration = AccountConnectorRegistration(
        platform=normalized,
        connector_id=str(connector_id or normalized).strip() or normalized,
        status_factory=status_factory,
        authorize_factory=authorize_factory,
    )
    _ACCOUNT_CONNECTORS[normalized] = registration
    return registration


def get_account_connector(platform: str | None) -> AccountConnectorRegistration | None:
    return _ACCOUNT_CONNECTORS.get(_normalize_platform(platform))


def get_account_connector_status(platform: str | None) -> dict[str, Any] | None:
    registration = get_account_connector(platform)
    if registration is None:
        return None
    status = dict(registration.status_factory() or {})
    return {
        'platform': registration.platform,
        'connector_id': registration.connector_id,
        'registered': True,
        **status,
    }


def list_account_connectors() -> list[dict[str, Any]]:
    return [
        get_account_connector_status(platform)
        for platform in sorted(_ACCOUNT_CONNECTORS)
    ]


def begin_account_connection(
    platform: str,
    account_id: int,
    *,
    scope_profile: str = 'full',
) -> dict[str, Any]:
    normalized = _normalize_platform(platform)
    registration = get_account_connector(normalized)
    if registration is None:
        raise LookupError(
            f'account connector is not registered for platform {normalized or "unknown"}'
        )

    account = get_account(account_id)
    if not account:
        raise LookupError('account not found')
    account_platform = _normalize_platform(account.get('platform'))
    if account_platform != normalized:
        raise ValueError(
            f'account {account_id} belongs to {account_platform or "unknown"}, not {normalized}'
        )

    result = dict(registration.authorize_factory(account_id, scope_profile) or {})
    return {
        'platform': normalized,
        'connector_id': registration.connector_id,
        **result,
    }


def _youtube_status():
    provider = YouTubeOAuthProvider(scope_profile='full')
    missing = []
    if not provider.client_id:
        missing.append('YOUTUBE_OAUTH_CLIENT_ID')
    if not provider.client_secret:
        missing.append('YOUTUBE_OAUTH_CLIENT_SECRET')
    if not provider.redirect_uri:
        missing.append('YOUTUBE_OAUTH_REDIRECT_URI')
    return {
        'configured': not missing,
        'missing_configuration': missing,
        'redirect_uri': provider.redirect_uri,
        'recommended_local_redirect_uri': 'http://localhost:5173/oauth/youtube/callback',
        'scope_profile': provider.scope_profile,
        'scopes': provider.scopes,
    }


def _youtube_authorize(account_id: int, scope_profile: str):
    provider = YouTubeOAuthProvider(scope_profile=scope_profile)
    result = provider.get_authorization_url()
    create_oauth_state(
        account_id,
        result['state'],
        provider='youtube',
        scope_profile=provider.scope_profile,
        code_verifier=result.get('code_verifier'),
    )
    return {
        'authorization_url': result['authorization_url'],
        'state': result['state'],
        'scope_profile': result['scope_profile'],
        'scopes': result['scopes'],
    }


register_account_connector(
    'youtube',
    connector_id='google_oauth',
    status_factory=_youtube_status,
    authorize_factory=_youtube_authorize,
)


__all__ = [
    'AccountConnectorRegistration',
    'YouTubeOAuthConfigurationError',
    'begin_account_connection',
    'get_account_connector',
    'get_account_connector_status',
    'list_account_connectors',
    'register_account_connector',
]
