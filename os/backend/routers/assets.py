from fastapi import APIRouter

from assets.manager import get_asset, get_asset_by_asset_id, get_assets


router = APIRouter()


@router.get('/assets')
def assets():
    return get_assets()


@router.get('/assets/video/{video_id}')
def asset_by_video(video_id: str):
    return get_asset(video_id)


@router.get('/assets/{asset_id}')
def asset_by_id(asset_id: str):
    return get_asset_by_asset_id(asset_id)
