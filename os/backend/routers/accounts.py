from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from accounts.manager import create_account, get_account, get_accounts
from accounts.models import Account
from data.sync_state import get_sync_state
from integrations.sync_registry import get_content_sync_adapter, run_content_sync


router = APIRouter()
DEFAULT_CONTENT_SYNC_LIMIT = 10


class AccountSyncRequest(BaseModel):
    max_results: int = Field(default=DEFAULT_CONTENT_SYNC_LIMIT, ge=1, le=200)
    sync_mode: Literal['incremental', 'full_refresh'] = 'incremental'


@router.get('/accounts')
def accounts():
    return get_accounts()


@router.get('/accounts/{account_id}')
def account(account_id: int):
    record = get_account(account_id)
    if not record:
        raise HTTPException(status_code=404, detail='account not found')
    return record


@router.get('/accounts/{account_id}/sync-state')
def account_sync_state(account_id: int):
    record = get_account(account_id)
    if not record:
        raise HTTPException(status_code=404, detail='account not found')
    platform = str(record.get('platform') or '').strip().lower()
    if not platform:
        raise HTTPException(status_code=409, detail='account has no platform')
    return get_sync_state(account_id, platform)


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


@router.get('/accounts/{account_id}/sync-plan')
def account_sync_plan(account_id: int):
    account = get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail='account not found')

    platform = str(account.get('platform') or '').strip().lower()
    adapter = get_content_sync_adapter(platform)
    if adapter is None:
        return {
            'account_id': account_id,
            'platform': platform or None,
            'content_sync_registered': False,
            'operations': [],
        }

    return {
        'account_id': account_id,
        'platform': platform,
        'content_sync_registered': True,
        'active_limit': adapter.active_limit,
        'operations': [
            {
                'operation': 'content_sync',
                'sync_mode': 'incremental',
                'max_results': adapter.active_limit,
            }
        ],
    }


@router.post('/accounts/{account_id}/sync')
def sync_account(account_id: int, request: AccountSyncRequest | None = None):
    account = get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail='account not found')

    platform = str(account.get('platform') or '').strip().lower()
    request = request or AccountSyncRequest()
    try:
        return run_content_sync(
            account_id,
            platform,
            max_results=request.max_results,
            sync_mode=request.sync_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f'{platform or "platform"} content sync failed: {exc}',
        ) from exc
