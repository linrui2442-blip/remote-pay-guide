from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config.network import get_proxy_status, save_proxy_settings


router = APIRouter()


class ProxySettingsRequest(BaseModel):
    mode: str = "system"
    proxy_url: str | None = None


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
