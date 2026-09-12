from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from accounts.manager import create_account, get_account, get_accounts
from accounts.models import Account
from data.sync_state import (
    get_sync_state,
    list_runtime_health_events,
    list_runtime_operation_history,
)
from integrations.sync_planner import build_account_sync_plan
from integrations.sync_registry import run_content_sync
from integrations.sync_scheduler import account_sync_scheduler, execute_account_sync


router = APIRouter()
DEFAULT_CONTENT_SYNC_LIMIT = 10


class AccountSyncRequest(BaseModel):
    max_results: int = Field(default=DEFAULT_CONTENT_SYNC_LIMIT, ge=1, le=200)
    sync_mode: Literal['incremental', 'full_refresh'] = 'incremental'


class AccountFullSyncRequest(AccountSyncRequest):
    start_date: str | None = None
    end_date: str | None = None


@router.get('/accounts')
def accounts():
    return get_accounts()


@router.get('/accounts/scheduler/status')
def scheduler_status():
    """Read-only process and persistent health for background account sync."""
    return account_sync_scheduler.status()


@router.get('/accounts/scheduler/history')
def scheduler_history(
    limit: int = 20,
    account_id: int | None = None,
    platform: str | None = None,
    status: str | None = None,
):
    """Read-only durable scheduler run history, newest first."""
    try:
        return {
            'items': list_runtime_operation_history(
                limit=min(200, max(1, limit)), account_id=account_id,
                platform=platform, status=status,
            )
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/accounts/scheduler/events')
def scheduler_events(
    limit: int = 20,
    account_id: int | None = None,
    platform: str | None = None,
    severity: str | None = None,
    event_type: str | None = None,
):
    """Read-only durable scheduler health transitions, newest first."""
    return {
        'items': list_runtime_health_events(
            limit=min(200, max(1, limit)), account_id=account_id,
            platform=platform, severity=severity, event_type=event_type,
        )
    }


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
    return build_account_sync_plan(account_id, platform)


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


@router.post('/accounts/{account_id}/sync-all')
def sync_all_account_data(
    account_id: int,
    request: AccountFullSyncRequest | None = None,
):
    account = get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail='account not found')

    platform = str(account.get('platform') or '').strip().lower()
    request = request or AccountFullSyncRequest()
    result = execute_account_sync(
        account_id,
        platform,
        requested_limit=request.max_results,
        sync_mode=request.sync_mode,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    if result['planned'] == 0:
        raise HTTPException(
            status_code=409,
            detail=f'no sync adapters are registered for platform {platform or "unknown"}',
        )
    return result
