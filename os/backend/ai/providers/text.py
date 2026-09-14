from __future__ import annotations

import os
import requests


class TextProviderError(RuntimeError):
    """Controlled provider failure with no secret material."""


class TextProvider:
    def __init__(self, *, base_url=None, model=None, api_key=None, timeout=None, session=None):
        self.base_url = (base_url if base_url is not None else os.getenv("AI_TEXT_BASE_URL", "")).strip()
        self.model = (model if model is not None else os.getenv("AI_TEXT_MODEL", "")).strip()
        self.api_key = api_key if api_key is not None else os.getenv("AI_TEXT_API_KEY", "")
        self.timeout = float(timeout if timeout is not None else os.getenv("AI_TEXT_TIMEOUT", "30"))
        self.session = session or requests

    def readiness(self):
        missing = [n for n, v in (("base_url", self.base_url), ("model", self.model), ("api_key", self.api_key)) if not v]
        return {"provider": "llm", "implementation_ready": True, "runtime_ready": not missing, "missing_configuration": missing, "reason": "missing_configuration" if missing else None, "model": self.model or None}

    def initialize(self):
        return self.readiness()

    def request(self, request):
        ready = self.readiness()
        if not ready["runtime_ready"]:
            raise TextProviderError("text provider missing configuration: " + ",".join(ready["missing_configuration"]))
        endpoint = self.base_url.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint += "/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + self.api_key}
        body = {"model": request.model if request.model and request.model != "auto" else self.model, "messages": [{"role": "user", "content": request.prompt}]}
        try:
            response = self.session.post(endpoint, headers=headers, json=body, timeout=self.timeout)
        except requests.Timeout as exc:
            raise TextProviderError("text provider timeout") from exc
        except requests.RequestException as exc:
            raise TextProviderError("text provider connection error") from exc
        status = getattr(response, "status_code", None)
        if status in (401, 403): raise TextProviderError(f"text provider HTTP {status} authentication/permission error")
        if status == 429: raise TextProviderError("text provider HTTP 429 rate limited")
        if status is not None and status >= 500: raise TextProviderError(f"text provider HTTP {status} upstream error")
        if status is not None and status >= 400: raise TextProviderError(f"text provider HTTP {status} request error")
        try:
            payload = response.json()
            output = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise TextProviderError("text provider returned malformed response") from exc
        if not isinstance(output, str) or not output.strip(): raise TextProviderError("text provider returned empty output")
        return {"status": "completed", "provider": "llm", "model": body["model"], "output": output}
