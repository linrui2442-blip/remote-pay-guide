from dataclasses import dataclass
from typing import Any, Callable

from accounts.manager import get_account, update_account_status
from oauth.manager import (
    consume_oauth_state_by_state,
    create_oauth_state,
    create_token,
)
from oauth.providers.youtube import (
    YouTubeOAuthConfigurationError,
    YouTubeOAuthProvider,
)
from oauth.meta_runtime_config import meta_config_status
from oauth.providers.meta import MetaOAuthConfigurationError, MetaOAuthProvider


class AccountConnectorConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AccountConnectorRegistration:
    platform: str
    connector_id: str
    status_factory: Callable[[], dict[str, Any]]
    authorize_factory: Callable[[int, str], dict[str, Any]]
    exchange_factory: Callable[[dict[str, Any], str, str], dict[str, Any]]
    state_provider: str


_ACCOUNT_CONNECTORS: dict[str, AccountConnectorRegistration] = {}


def _normalize_platform(platform: str | None) -> str:
    return str(platform or '').strip().lower()


def register_account_connector(
    platform: str,
    *,
    connector_id: str,
    status_factory: Callable[[], dict[str, Any]],
    authorize_factory: Callable[[int, str], dict[str, Any]],
    exchange_factory: Callable[[dict[str, Any], str, str], dict[str, Any]],
    state_provider: str | None = None,
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
        exchange_factory=exchange_factory,
        state_provider=_normalize_platform(state_provider) or normalized,
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
        'exchange_registered': True,
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

    if scope_profile == 'full' and normalized in {'facebook', 'instagram'}:
        scope_profile = 'facebook_publish' if normalized == 'facebook' else 'instagram_publish'
    result = dict(registration.authorize_factory(account_id, scope_profile) or {})
    return {
        'platform': normalized,
        'connector_id': registration.connector_id,
        **result,
    }


def complete_account_connection(
    platform: str,
    *,
    authorization_code: str,
    state: str,
    account_id: int | None = None,
) -> dict[str, Any]:
    normalized = _normalize_platform(platform)
    registration = get_account_connector(normalized)
    if registration is None:
        raise LookupError(
            f'account connector is not registered for platform {normalized or "unknown"}'
        )
    if not authorization_code:
        raise ValueError('authorization_code is required')
    if not state:
        raise ValueError('state is required')

    state_record = consume_oauth_state_by_state(
        state,
        provider=registration.state_provider,
        expected_scope_profile=(['facebook_publish', 'meta_full'] if normalized == 'facebook' else (['instagram_publish', 'meta_full'] if normalized == 'instagram' else None)),
        expected_connector_platform=normalized,
    )
    if not state_record:
        raise ValueError('invalid or expired OAuth state')

    resolved_account_id = state_record.get('account_id')
    if account_id is not None and account_id != resolved_account_id:
        raise ValueError('OAuth state/account mismatch')

    account = get_account(resolved_account_id)
    if not account:
        raise LookupError('account not found')
    account_platform = _normalize_platform(account.get('platform'))
    if account_platform != normalized:
        raise ValueError(
            f'account {resolved_account_id} belongs to {account_platform or "unknown"}, not {normalized}'
        )

    token = dict(
        registration.exchange_factory(
            state_record,
            authorization_code,
            state,
        )
        or {}
    )
    stored = create_token(
        {
            'account_id': resolved_account_id,
            'provider': normalized,
            **token,
        }
    )
    connection_status = 'authorized' if normalized in {'facebook', 'instagram'} else 'connected'
    update_account_status(resolved_account_id, connection_status)
    return {
        'platform': normalized,
        'connector_id': registration.connector_id,
        'account_id': resolved_account_id,
        'status': connection_status,
        'scope_profile': state_record.get('scope_profile'),
        'scopes': stored.get('scopes') if stored else [],
        'expires_at': stored.get('expires_at') if stored else None,
        'has_refresh_token': bool(stored and stored.get('refresh_token')),
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
        'callback_path': '/oauth/youtube/callback',
        'recommended_local_redirect_uri': 'http://localhost:5173/oauth/youtube/callback',
        'scope_profile': provider.scope_profile,
        'scopes': provider.scopes,
    }


def _youtube_authorize(account_id: int, scope_profile: str):
    try:
        provider = YouTubeOAuthProvider(scope_profile=scope_profile)
        result = provider.get_authorization_url()
    except YouTubeOAuthConfigurationError as exc:
        raise AccountConnectorConfigurationError(str(exc)) from exc

    create_oauth_state(
        account_id,
        result['state'],
        provider='youtube',
        connector_platform='youtube',
        scope_profile=provider.scope_profile,
        code_verifier=result.get('code_verifier'),
    )
    return {
        'authorization_url': result['authorization_url'],
        'state': result['state'],
        'scope_profile': result['scope_profile'],
        'scopes': result['scopes'],
    }


def _youtube_exchange(
    state_record: dict[str, Any],
    authorization_code: str,
    state: str,
):
    scope_profile = state_record.get('scope_profile') or 'publish'
    try:
        provider = YouTubeOAuthProvider(scope_profile=scope_profile)
        return provider.exchange_code(
            authorization_code,
            state=state,
            code_verifier=state_record.get('code_verifier'),
        )
    except YouTubeOAuthConfigurationError as exc:
        raise AccountConnectorConfigurationError(str(exc)) from exc


register_account_connector(
    'youtube',
    connector_id='google_oauth',
    status_factory=_youtube_status,
    authorize_factory=_youtube_authorize,
    exchange_factory=_youtube_exchange,
)

def _meta_status(platform):
    status = meta_config_status()
    status.update({"scope_profile": "facebook_publish" if platform == "facebook" else "instagram_publish", "scopes": MetaOAuthProvider(platform).scopes})
    return status

def _meta_authorize(platform, account_id, scope_profile):
    try: return MetaOAuthProvider(platform, scope_profile=scope_profile).authorization_url(account_id)
    except MetaOAuthConfigurationError as exc: raise AccountConnectorConfigurationError(str(exc)) from exc

def _meta_exchange(platform, state, code, state_value):
    try: return MetaOAuthProvider(platform, scope_profile=state.get('scope_profile')).exchange_code(code)
    except MetaOAuthConfigurationError as exc: raise AccountConnectorConfigurationError(str(exc)) from exc

register_account_connector("facebook", connector_id="meta_oauth", state_provider="meta", status_factory=lambda: _meta_status("facebook"), authorize_factory=lambda account_id, profile: _meta_authorize("facebook", account_id, profile), exchange_factory=lambda state, code, state_value: _meta_exchange("facebook", state, code, state_value))
register_account_connector("instagram", connector_id="meta_oauth", state_provider="meta", status_factory=lambda: _meta_status("instagram"), authorize_factory=lambda account_id, profile: _meta_authorize("instagram", account_id, profile), exchange_factory=lambda state, code, state_value: _meta_exchange("instagram", state, code, state_value))


__all__ = [
    'AccountConnectorConfigurationError',
    'AccountConnectorRegistration',
    'begin_account_connection',
    'complete_account_connection',
    'get_account_connector',
    'get_account_connector_status',
    'list_account_connectors',
    'register_account_connector',
]
