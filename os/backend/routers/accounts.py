from fastapi import APIRouter, HTTPException

from accounts.manager import create_account, get_account, get_accounts
from accounts.models import Account


router = APIRouter()


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
