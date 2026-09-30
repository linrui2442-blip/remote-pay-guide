import os
import ipaddress
import hashlib
from urllib.parse import urljoin, urlsplit, urlunsplit

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
        # Remote errors/metadata are untrusted and may echo credentials.
        error = "AI Remote Production failed" if data.get("error") else ""
        if (
            status == "failed"
            and str(raw_status or "").strip().lower()
            not in self.ACTIVE_STATUSES | self.TERMINAL_STATUSES
            and not error
        ):
            error = "AI Remote Production returned unsupported status"

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
        allowed = {"remote_job_id", "job_id", "status_url", "poll_url", "asset_url", "video_url", "url"}
        merged = {k: v for k, v in previous_output.items() if k in allowed}
        merged.update({k: v for k, v in output.items() if k in allowed})
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

        try:
            for key in ("remote_job_id", "job_id"):
                if key in merged:
                    value = merged[key]
                    if not isinstance(value, (str, int)) or len(str(value)) > 256 or self._contains_secret(str(value)):
                        raise ValueError("invalid correlation")
            if merged.get("status_url") or merged.get("poll_url"):
                merged["status_url"] = self._poll_url(merged)
                merged.pop("poll_url", None)
            if status in self.ACTIVE_STATUSES and not merged.get("status_url"):
                raise ValueError("active response requires poll URL")
            if status == "completed":
                merged["asset_url"] = self._asset_url(merged.get("asset_url") or merged.get("video_url") or merged.get("url"))
            else:
                merged.pop("asset_url", None)
            merged.pop("video_url", None)
            merged.pop("url", None)
        except ValueError:
            return AIResponse(status="failed", model=model, error="AI Remote Production response contract rejected")
        return AIResponse(
            status=status,
            model=model,
            output=merged,
            usage={},
            error=error,
        )

    def _contains_secret(self, value):
        return any(secret and secret in value for secret in
                   (self._api_key(), os.getenv("AI_TEXT_API_KEY"), os.getenv("SUB2_KEY")))

    def normalized_endpoint(self):
        value = self._endpoint()
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or self._contains_secret(value)):
            raise ValueError("AI video endpoint configuration required")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        host = parsed.hostname.lower()
        if ":" in host:
            host = "[" + host + "]"
        return urlunsplit((parsed.scheme, f"{host}:{port}", parsed.path or "/", "", ""))

    def _asset_url(self, value):
        if not isinstance(value, str) or self._contains_secret(value):
            raise ValueError("invalid asset reference")
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        if (parsed.scheme != "https" or not host or parsed.username or parsed.password
                or host == "localhost" or host.endswith((".localhost", ".local", ".internal"))
                or "." not in host or "\\" in value or any(ord(c) < 33 for c in value)):
            raise ValueError("invalid asset reference")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            # Reject legacy numeric host encodings as well as ordinary IP literals.
            if host.replace(".", "").isdigit() or host.startswith("0x"):
                raise ValueError("invalid asset host")
        else:
            if not address.is_global:
                raise ValueError("non-public asset host")
        return value

    def _poll_url(self, output):
        if not isinstance(output, dict):
            return ""
        value = output.get("status_url") or output.get("poll_url")
        if not value:
            return ""
        endpoint = self.normalized_endpoint()
        target = urljoin(endpoint, str(value))
        parsed, origin = urlsplit(target), urlsplit(endpoint)
        if (parsed.username or parsed.password or parsed.fragment or "\\" in target
                or self._contains_secret(target) or any(ord(c) < 33 for c in target)
                or (parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
                != (origin.scheme, origin.hostname, origin.port)):
            raise ValueError("AI poll URL must be same-origin")
        return target

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
        if getattr(request, 'endpoint_fingerprint', ''):
            # Freeze the exact checked server endpoint at the network boundary.
            endpoint = self.normalized_endpoint()
            if hashlib.sha256(endpoint.encode()).hexdigest() != request.endpoint_fingerprint:
                raise ValueError('AI execution endpoint drift')
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
        headers = self._headers()
        if getattr(request, "request_id", ""):
            headers["Idempotency-Key"] = request.request_id

        try:
            response = self.session.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=False,
            )
            if 300 <= getattr(response, "status_code", 200) < 400:
                raise ValueError("redirect rejected")
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            return AIResponse(
                status="failed",
                model=request.model,
                output={"ambiguous_dispatch": True},
                error="AI Remote Production request outcome unknown",
            )
        except ValueError as exc:
            return AIResponse(
                status="failed",
                model=request.model,
                output={"ambiguous_dispatch": True},
                error="AI Remote Production returned invalid JSON or redirect",
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
        try:
            poll_url = self._poll_url(previous_output)
        except ValueError:
            return AIResponse(status="failed", model=model, error="AI poll URL rejected")
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
                allow_redirects=False,
            )
            if 300 <= getattr(response, "status_code", 200) < 400:
                return AIResponse(status="failed", model=model, error="AI poll redirect rejected")
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            # A transient status endpoint failure does not convert an active
            # remote generation into a terminal production failure.
            return AIResponse(
                status="running",
                model=model,
                output=previous_output,
                error="AI Remote Production status check temporarily unavailable",
            )
        except ValueError as exc:
            return AIResponse(
                status="running",
                model=model,
                output=previous_output,
                error="AI Remote Production status check returned invalid JSON",
            )

        result = self._normalize_payload(
            data,
            model=model,
            previous_output=previous_output,
        )
        if result.status in self.ACTIVE_STATUSES and not self._poll_url(result.output):
            result.output["status_url"] = poll_url
        return result
