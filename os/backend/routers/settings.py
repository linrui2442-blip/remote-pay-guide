from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config.ai_gateway import get_ai_gateway_settings, save_ai_gateway_settings
from config.network import get_proxy_status, save_proxy_settings
from intelligence.autonomy import get_autonomy_settings, update_autonomy_settings


router = APIRouter()


class ProxySettingsRequest(BaseModel):
    mode: str = "system"
    proxy_url: str | None = None


class AIGatewaySettingsRequest(BaseModel):
    video_url: str | None = None


@router.get("/settings/network/proxy")
def network_proxy_settings():
    return get_proxy_status()


@router.post("/settings/network/proxy")
def update_network_proxy_settings(request: ProxySettingsRequest):
    try:
        return save_proxy_settings(
            mode=request.mode,
            proxy_url=request.proxy_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/settings/ai-gateway')
def ai_gateway_settings():
    return get_ai_gateway_settings()


@router.post('/settings/ai-gateway')
def update_ai_gateway_settings(request: AIGatewaySettingsRequest):
    try:
        return save_ai_gateway_settings(video_url=request.video_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get('/settings/autonomy')
def autonomy_settings(): return get_autonomy_settings()

@router.post('/settings/autonomy')
def update_autonomy(request: dict):
    allowed={'autonomy_enabled','kill_switch_active'}
    if set(request)-allowed: raise HTTPException(status_code=400, detail='unsupported autonomy field')
    if any(k in request and not isinstance(request[k], bool) for k in allowed):
        raise HTTPException(status_code=422, detail='autonomy settings require strict booleans')
    try: return update_autonomy_settings(**request)
    except ValueError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc
