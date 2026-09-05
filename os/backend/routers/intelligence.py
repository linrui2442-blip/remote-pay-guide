from fastapi import APIRouter

from intelligence.manager import analyze_video
from intelligence.insights import get_insights, get_video_insight

router = APIRouter()

@router.post('/intelligence/analyze/{video_id}')
def analyze(video_id: str):
    return analyze_video(video_id)

@router.get('/intelligence/insights')
def insights():
    return get_insights()

@router.get('/intelligence/video/{video_id}')
def video_insight(video_id: str):
    return get_video_insight(video_id)

@router.get('/intelligence/status')
def status():
    return {"status": "ready"}
