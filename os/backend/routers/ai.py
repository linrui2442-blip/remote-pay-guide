from fastapi import APIRouter

from ai.gateway import AIService
from ai.models import AIRequest

router = APIRouter()

@router.post('/ai/request')
def ai_request(request: AIRequest):
    return AIService().request(request)

@router.get('/ai/status')
def ai_status():
    return {"status": "ready", "gateway": "enabled"}
