import os
from urllib.parse import urljoin

import requests

from ai.models import AIResponse
from config.ai_gateway import get_ai_gateway_settings


class VideoProvider:
    """Remote video-generation transport.

    Remote Pay Guide OS never performs local model inference here. The provider
    forwards a stable AIRequest envelope to a configured relay/gateway, which
    can route to any external video-generation service.

    Async jobs are polled through a status URL returned by the relay. The relay
    may return ``status_url`` or ``poll_url`` either inside ``output`` or at the
    top level. Relative URLs are resolved against the configured gateway URL.
    """

    ACTIVE_STATUSES = {"submitted", "running"}
    TERMINAL_STATUSES = {"completed", "failed"}

    def __init__(self, endpoint=None, api_key=None, session=None, timeout=None):
        # `None` means use live OS/environment settings. Passing an explicit
        # empty string is useful for fail-closed tests and never falls back.
        self.endpoint_override = endpoint
        self.api_key_override = api_key
        self.session = session or requests.Session()
        self.timeout = int(timeout or os.getenv("AI_GATEWAY_TIMEOUT_SECONDS") or 120)

    def _endpoint(self):
        if self.endpoint_override is not None:
            return str(self.endpoint_override or "").strip()
        settings = get_ai_gateway_settings()
        return str(settings.get("video_url") or "").strip()

    def _api_key(self):
        if self.api_key_override is not None:
            return self.api_key_override
        return os.getenv("AI_GATEWAY_API_KEY")

    def _headers(self):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        api_key = self._api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _normalize_status(self, value):
        normalized = str(value or "completed").strip().lower()
        if normalized not in self.ACTIVE_STATUSES | self.TERMINAL_STATUSES:
            return "failed"
        return normalized

    def _normalize_payload(self, data, *, model="auto", previous_output=None):
        if not isinstance(data, dict):
            return AIResponse(
                status="failed",
                model=model,
                error="AI Remote Production returned a non-object response",
            )

        raw_status = data.get("status") or "completed"
        status = self._normalize_status(raw_status)
        error = str(data.get("error") or "")
        if (
            status == "failed"
            and str(raw_status or "").strip().lower()
            not in self.ACTIVE_STATUSES | self.TERMINAL_STATUSES
            and not error
        ):
            error = f"AI Remote Production returned unsupported status: {raw_status}"

        output = data.get("output")
        if output is None:
            output = {
                key: value
                for key, value in data.items()
                if key not in {"status", "model", "usage", "error"}
            }
        elif isinstance(output, str):
            output = {"url": output} if status == "completed" else {"value": output}
        elif not isinstance(output, dict):
            output = {"value": output}

        previous_output = previous_output if isinstance(previous_output, dict) else {}
        merged = dict(previous_output)
        merged.update(output)
        for key in (
            "remote_job_id",
            "job_id",
            "status_url",
            "poll_url",
            "asset_url",
            "video_url",
            "url",
        ):
            if data.get(key) is not None:
                merged[key] = data.get(key)

        return AIResponse(
            status=status,
            model=data.get("model") or model,
            output=merged,
            usage=data.get("usage") if isinstance(data.get("usage"), dict) else {},
            error=error,
        )

    def _poll_url(self, output):
        if not isinstance(output, dict):
            return ""
        value = output.get("status_url") or output.get("poll_url")
        if not value:
            return ""
        endpoint = self._endpoint()
        return urljoin(endpoint, str(value)) if endpoint else str(value)

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
                else get_ai_gateway_settings().get("source")
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
                headers=self._headers(),
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

        result = self._normalize_payload(data, model=request.model)
        if result.status in self.ACTIVE_STATUSES and not self._poll_url(result.output):
            return AIResponse(
                status="failed",
                model=result.model,
                output=result.output,
                usage=result.usage,
                error=(
                    "AI Remote Production returned an async status without a "
                    "status_url or poll_url"
                ),
            )
        return result

    def poll(self, output, *, model="auto"):
        previous_output = output if isinstance(output, dict) else {}
        poll_url = self._poll_url(previous_output)
        if not poll_url:
            return AIResponse(
                status="failed",
                model=model,
                output=previous_output,
                error="AI Remote Production cannot be polled: status_url or poll_url is missing",
            )

        try:
            response = self.session.get(
                poll_url,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            # A transient status endpoint failure does not convert an active
            # remote generation into a terminal production failure.
            return AIResponse(
                status="running",
                model=model,
                output=previous_output,
                error=f"AI Remote Production status check failed: {exc}",
            )
        except ValueError as exc:
            return AIResponse(
                status="running",
                model=model,
                output=previous_output,
                error=f"AI Remote Production status check returned invalid JSON: {exc}",
            )

        result = self._normalize_payload(
            data,
            model=model,
            previous_output=previous_output,
        )
        if result.status in self.ACTIVE_STATUSES and not self._poll_url(result.output):
            result.output["status_url"] = poll_url
        return result
