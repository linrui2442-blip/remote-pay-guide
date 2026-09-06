from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from accounts.manager import get_account, update_account_status
from oauth.manager import (
    consume_oauth_state,
    create_oauth_state,
    create_token,
)
from oauth.providers.youtube import (
    YouTubeOAuthConfigurationError,
    YouTubeOAuthProvider,
)

router = APIRouter()


class YouTubeOAuthExchangeRequest(BaseModel):
    account_id: int
    authorization_code: str
    state: str


@router.get("/oauth/youtube/authorize/{account_id}")
def youtube_authorize(account_id: int):
    account = get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    if str(account.get("platform", "")).lower() != "youtube":
        raise HTTPException(status_code=400, detail="account is not a YouTube account")

    try:
        result = YouTubeOAuthProvider().get_authorization_url()
        create_oauth_state(account_id, result["state"], provider="youtube")
        return result
    except YouTubeOAuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/oauth/youtube/exchange")
def youtube_exchange(request: YouTubeOAuthExchangeRequest):
    account = get_account(request.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="account not found")
    if str(account.get("platform", "")).lower() != "youtube":
        raise HTTPException(status_code=400, detail="account is not a YouTube account")

    if not consume_oauth_state(
        request.account_id,
        request.state,
        provider="youtube",
    ):
        raise HTTPException(status_code=400, detail="invalid or expired OAuth state")

    try:
        token = YouTubeOAuthProvider().exchange_code(
            request.authorization_code,
            state=request.state,
        )
        stored = create_token({"account_id": request.account_id, **token})
        update_account_status(request.account_id, "connected")
        return {
            "account_id": request.account_id,
            "status": "connected",
            "expires_at": stored.get("expires_at") if stored else None,
            "has_refresh_token": bool(stored and stored.get("refresh_token")),
        }
    except YouTubeOAuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"YouTube OAuth exchange failed: {exc}",
        ) from exc
