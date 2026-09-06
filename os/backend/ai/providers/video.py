import os

import requests

from ai.models import AIResponse
from config.ai_gateway import get_ai_gateway_settings


class VideoProvider:
    """Remote video-generation transport.

    Remote Pay Guide OS never performs local model inference here. The provider
    forwards a stable AIRequest envelope to a configured relay/gateway, which
    can route to any external video-generation service.
    """

    def __init__(self, endpoint=None, api_key=None, session=None, timeout=None):
        # `None` means use live OS/environment settings. Passing an explicit
        # empty string is useful for fail-closed tests and never falls back.
        self.endpoint_override = endpoint
        self.api_key_override = api_key
        self.session = session or requests.Session()
        self.timeout = int(timeout or os.getenv("AI_GATEWAY_TIMEOUT_SECONDS") or 120)

    def _endpoint(self):
        if self.endpoint_override is not None:
            return str(self.endpoint_override or '').strip()
        settings = get_ai_gateway_settings()
        return str(settings.get('video_url') or '').strip()

    def _api_key(self):
        if self.api_key_override is not None:
            return self.api_key_override
        return os.getenv("AI_GATEWAY_API_KEY")

    def initialize(self):
        endpoint = self._endpoint()
        return {
            "provider": "video",
            "status": "ready" if endpoint else "configuration_required",
            "configured": bool(endpoint),
            "transport": "remote_http",
            "local_inference": False,
            "endpoint_source": (
                "override"
                if self.endpoint_override is not None
                else get_ai_gateway_settings().get('source')
            ),
            "missing_configuration": [] if endpoint else ["AI Gateway video URL"],
        }

    def request(self, request):
        endpoint = self._endpoint()
        if not endpoint:
            return AIResponse(
                status="failed",
                model=getattr(request, "model", "auto") or "auto",
                error=(
                    "AI Remote Production is not configured: set the AI Gateway "
                    "video URL in OS settings or AI_GATEWAY_VIDEO_URL"
                ),
            )

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        api_key = self._api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "task_type": request.task_type,
            "model": request.model,
            "prompt": request.prompt,
            "input": request.input,
            "options": request.options,
        }

        try:
            response = self.session.post(
                endpoint,
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
