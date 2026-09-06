from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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

router = APIRouter()


class YouTubeOAuthExchangeRequest(BaseModel):
    authorization_code: str
    state: str
    account_id: int | None = None


@router.get("/oauth/youtube/authorize/{account_id}")
def youtube_authorize(account_id: int, scope_profile: str = "publish"):
    account = get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    if str(account.get("platform", "")).lower() != "youtube":
        raise HTTPException(status_code=400, detail="account is not a YouTube account")

    try:
        provider = YouTubeOAuthProvider(scope_profile=scope_profile)
        result = provider.get_authorization_url()
        create_oauth_state(
            account_id,
            result["state"],
            provider="youtube",
            scope_profile=provider.scope_profile,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except YouTubeOAuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/oauth/youtube/exchange")
def youtube_exchange(request: YouTubeOAuthExchangeRequest):
    state_record = consume_oauth_state_by_state(
        request.state,
        provider="youtube",
    )
    if not state_record:
        raise HTTPException(status_code=400, detail="invalid or expired OAuth state")

    account_id = state_record.get("account_id")
    if request.account_id is not None and request.account_id != account_id:
        raise HTTPException(status_code=400, detail="OAuth state/account mismatch")

    account = get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    if str(account.get("platform", "")).lower() != "youtube":
        raise HTTPException(status_code=400, detail="account is not a YouTube account")

    scope_profile = state_record.get("scope_profile") or "publish"

    try:
        provider = YouTubeOAuthProvider(scope_profile=scope_profile)
        token = provider.exchange_code(
            request.authorization_code,
            state=request.state,
        )
        stored = create_token(
            {
                "account_id": account_id,
                "provider": "youtube",
                **token,
            }
        )
        update_account_status(account_id, "connected")
        return {
            "account_id": account_id,
            "status": "connected",
            "scope_profile": scope_profile,
            "scopes": stored.get("scopes") if stored else [],
            "expires_at": stored.get("expires_at") if stored else None,
            "has_refresh_token": bool(stored and stored.get("refresh_token")),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except YouTubeOAuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"YouTube OAuth exchange failed: {exc}",
        ) from exc
