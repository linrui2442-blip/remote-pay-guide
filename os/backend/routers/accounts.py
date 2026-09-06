from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from accounts.manager import create_account, get_account, get_accounts
from accounts.models import Account
from integrations.youtube import YouTubeContentSync


router = APIRouter()


class AccountSyncRequest(BaseModel):
    max_results: int = Field(default=50, ge=1, le=200)


@router.get('/accounts')
def accounts():
    return get_accounts()


@router.get('/accounts/{account_id}')
def account(account_id: int):
    record = get_account(account_id)
    if not record:
        raise HTTPException(status_code=404, detail='account not found')
    return record


@router.post('/accounts')
def add_account(account: Account):
    normalized_platform = (account.platform or '').strip().lower()
    if not normalized_platform:
        raise HTTPException(status_code=400, detail='platform is required')

    normalized_name = (account.account_name or '').strip()
    if not normalized_name:
        raise HTTPException(status_code=400, detail='account_name is required')

    return create_account(
        Account(
            platform=normalized_platform,
            account_name=normalized_name,
            status=account.status or 'inactive',
        )
    )


@router.post('/accounts/{account_id}/sync')
def sync_account(account_id: int, request: AccountSyncRequest | None = None):
    account = get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail='account not found')

    platform = str(account.get('platform') or '').strip().lower()
    if platform != 'youtube':
        raise HTTPException(
            status_code=409,
            detail=f'content sync is not implemented for platform {platform or "unknown"}',
        )

    request = request or AccountSyncRequest()
    try:
        return YouTubeContentSync().sync(
            account_id,
            max_results=request.max_results,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f'YouTube content sync failed: {exc}',
        ) from exc
