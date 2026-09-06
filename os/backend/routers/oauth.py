from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from oauth.registry import (
    AccountConnectorConfigurationError,
    begin_account_connection,
    complete_account_connection,
    get_account_connector_status,
    list_account_connectors,
)

router = APIRouter()


class OAuthExchangeRequest(BaseModel):
    authorization_code: str
    state: str
    account_id: int | None = None


YouTubeOAuthExchangeRequest = OAuthExchangeRequest


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
    except AccountConnectorConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post('/oauth/exchange/{platform}')
def exchange_account_connection(platform: str, request: OAuthExchangeRequest):
    try:
        return complete_account_connection(
            platform,
            authorization_code=request.authorization_code,
            state=request.state,
            account_id=request.account_id,
        )
    except LookupError as exc:
        detail = str(exc)
        status_code = 404 if detail == 'account not found' else 409
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AccountConnectorConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f'{platform} OAuth exchange failed: {exc}',
        ) from exc


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
    # Compatibility endpoint retained for already-configured Google redirect
    # flows. The actual code exchange now goes through the connector registry.
    return exchange_account_connection('youtube', request)
