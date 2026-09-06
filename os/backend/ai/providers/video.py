import os

import requests

from ai.models import AIResponse


class VideoProvider:
    """Remote video-generation transport.

    Remote Pay Guide OS never performs local model inference here. The provider
    forwards a stable AIRequest envelope to a configured relay/gateway, which
    can route to any external video-generation service.
    """

    def __init__(self, endpoint=None, api_key=None, session=None, timeout=None):
        self.endpoint = (endpoint or os.getenv("AI_GATEWAY_VIDEO_URL") or "").strip()
        self.api_key = api_key if api_key is not None else os.getenv("AI_GATEWAY_API_KEY")
        self.session = session or requests.Session()
        self.timeout = int(timeout or os.getenv("AI_GATEWAY_TIMEOUT_SECONDS") or 120)

    def initialize(self):
        return {
            "provider": "video",
            "status": "ready" if self.endpoint else "configuration_required",
            "configured": bool(self.endpoint),
            "transport": "remote_http",
            "local_inference": False,
            "missing_configuration": [] if self.endpoint else ["AI_GATEWAY_VIDEO_URL"],
        }

    def request(self, request):
        if not self.endpoint:
            return AIResponse(
                status="failed",
                model=getattr(request, "model", "auto") or "auto",
                error=(
                    "AI Remote Production is not configured: set "
                    "AI_GATEWAY_VIDEO_URL to the external relay endpoint"
                ),
            )

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "task_type": request.task_type,
            "model": request.model,
            "prompt": request.prompt,
            "input": request.input,
            "options": request.options,
        }

        try:
            response = self.session.post(
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            return AIResponse(
                status="failed",
                model=request.model,
                error=f"AI Remote Production request failed: {exc}",
            )
        except ValueError as exc:
            return AIResponse(
                status="failed",
                model=request.model,
                error=f"AI Remote Production returned invalid JSON: {exc}",
            )

        if not isinstance(data, dict):
            return AIResponse(
                status="failed",
                model=request.model,
                error="AI Remote Production returned a non-object response",
            )

        status = str(data.get("status") or "completed").strip().lower()
        if status not in {"submitted", "running", "completed", "failed"}:
            status = "failed"

        return AIResponse(
            status=status,
            model=data.get("model") or request.model,
            output=data.get("output"),
            usage=data.get("usage") if isinstance(data.get("usage"), dict) else {},
            error=str(data.get("error") or ""),
        )
