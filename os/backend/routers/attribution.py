import os
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from attribution.service import decode_redirect_token, encode_redirect_token, ingest_conversion, ingest_intent, status, verify_signed_request, _destination
router = APIRouter()
class LinkRequest(BaseModel):
    content_id: str; account_id: int; platform: str; platform_video_id: str; campaign_id: str|None=None; destination_key: str
async def _signed(request, timestamp, signature):
    body = await request.json()
    try: verify_signed_request(body, timestamp, signature)
    except RuntimeError as exc: raise HTTPException(503, str(exc)) from exc
    except ValueError as exc: raise HTTPException(401, str(exc)) from exc
    return body
@router.get('/attribution/status')
def attribution_status(): return status()
@router.post('/attribution/intent')
async def attribution_intent(request: Request, x_attribution_timestamp: str|None=Header(None), x_attribution_signature: str|None=Header(None)):
    try: return ingest_intent(await _signed(request, x_attribution_timestamp, x_attribution_signature))
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
@router.post('/attribution/conversion/{provider}')
async def attribution_conversion(provider: str, request: Request, x_attribution_timestamp: str|None=Header(None), x_attribution_signature: str|None=Header(None)):
    try: return ingest_conversion(provider, await _signed(request, x_attribution_timestamp, x_attribution_signature))
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
@router.post('/attribution/links')
def attribution_link(request: LinkRequest):
    try: token=encode_redirect_token(request.model_dump())
    except (RuntimeError, ValueError) as exc: raise HTTPException(503, str(exc)) from exc
    base=os.getenv('OS_ATTRIBUTION_PUBLIC_BASE_URL'); path='/attribution/r/'+token
    return {'tracking_path':path,'public_url':base.rstrip('/')+path if base else None,'public_url_available':bool(base)}
@router.get('/attribution/r/{token}')
def attribution_redirect(token: str):
    try:
        payload=decode_redirect_token(token); ingest_intent({**payload,'event_id':'redirect:'+token,'event_type':'referral_click','source':'referral'})
        return RedirectResponse(_destination(payload['destination_key']), status_code=302)
    except (ValueError, RuntimeError) as exc: raise HTTPException(400, str(exc)) from exc
