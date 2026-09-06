from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from accounts.manager import get_account, update_account_status
from oauth.manager import (
    consume_oauth_state_by_state,
    create_token,
)
from oauth.providers.youtube import (
    YouTubeOAuthConfigurationError,
    YouTubeOAuthProvider,
)
from oauth.registry import (
    begin_account_connection,
    get_account_connector_status,
    list_account_connectors,
)

router = APIRouter()


class YouTubeOAuthExchangeRequest(BaseModel):
    authorization_code: str
    state: str
    account_id: int | None = None


@router.get('/oauth/connectors')
def account_connectors():
    return list_account_connectors()


@router.get('/oauth/connect/{platform}/{account_id}')
def connect_account(platform: str, account_id: int, scope_profile: str = 'full'):
    try:
        return begin_account_connection(
            platform,
            account_id,
            scope_profile=scope_profile,
        )
    except LookupError as exc:
        detail = str(exc)
        status_code = 404 if detail == 'account not found' else 409
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except YouTubeOAuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get('/oauth/youtube/status')
def youtube_oauth_status():
    # Compatibility endpoint retained for existing clients. Runtime discovery
    # now comes from /oauth/connectors and the platform runtime capability API.
    return get_account_connector_status('youtube')


@router.get('/oauth/youtube/authorize/{account_id}')
def youtube_authorize(account_id: int, scope_profile: str = 'publish'):
    # Compatibility endpoint retained while delegating to the same registry
    # path used by provider-neutral account connection.
    return connect_account('youtube', account_id, scope_profile=scope_profile)


@router.post('/oauth/youtube/exchange')
def youtube_exchange(request: YouTubeOAuthExchangeRequest):
    state_record = consume_oauth_state_by_state(
        request.state,
        provider='youtube',
    )
    if not state_record:
        raise HTTPException(status_code=400, detail='invalid or expired OAuth state')

    account_id = state_record.get('account_id')
    if request.account_id is not None and request.account_id != account_id:
        raise HTTPException(status_code=400, detail='OAuth state/account mismatch')

    account = get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail='account not found')
    if str(account.get('platform', '')).lower() != 'youtube':
        raise HTTPException(status_code=400, detail='account is not a YouTube account')

    scope_profile = state_record.get('scope_profile') or 'publish'

    try:
        provider = YouTubeOAuthProvider(scope_profile=scope_profile)
        token = provider.exchange_code(
            request.authorization_code,
            state=request.state,
            code_verifier=state_record.get('code_verifier'),
        )
        stored = create_token(
            {
                'account_id': account_id,
                'provider': 'youtube',
                **token,
            }
        )
        update_account_status(account_id, 'connected')
        return {
            'account_id': account_id,
            'status': 'connected',
            'scope_profile': scope_profile,
            'scopes': stored.get('scopes') if stored else [],
            'expires_at': stored.get('expires_at') if stored else None,
            'has_refresh_token': bool(stored and stored.get('refresh_token')),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except YouTubeOAuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f'YouTube OAuth exchange failed: {exc}',
        ) from exc
