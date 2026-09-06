import json

from ai.gateway import AIGatewayService
from ai.models import AIRequest


class AIGatewayProvider:
    """Production-provider adapter for the AI Remote Production Line."""

    def __init__(self, gateway=None):
        self.config = None
        self.gateway = gateway or AIGatewayService()

    def initialize(self, config=None):
        self.config = config or {}
        return self.get_provider_status()

    def _payload(self, job):
        raw = job.get("input") or {}
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                decoded = json.loads(raw)
                return decoded if isinstance(decoded, dict) else {}
            except (TypeError, ValueError, json.JSONDecodeError):
                return {}
        return {}

    def _request_from_job(self, job):
        payload = self._payload(job)
        parameters = payload.get("parameters") or {}
        if not isinstance(parameters, dict):
            parameters = {}

        task_type = (
            payload.get("task_type")
            or parameters.get("task_type")
            or "video_generation"
        )
        prompt = (
            parameters.get("prompt")
            or payload.get("prompt")
            or payload.get("objective")
            or ""
        )
        model = parameters.get("model") or payload.get("model") or "auto"
        options = parameters.get("options") or payload.get("options") or {}
        if not isinstance(options, dict):
            options = {}

        explicit_input = parameters.get("input") or payload.get("input") or {}
        if not isinstance(explicit_input, dict):
            explicit_input = {"value": explicit_input}

        request_input = {
            "objective": payload.get("objective"),
            "template": payload.get("template"),
            "resources": payload.get("resources") or [],
            "parameters": parameters,
            **explicit_input,
        }

        return AIRequest(
            task_type=str(task_type),
            model=str(model),
            prompt=str(prompt),
            input=request_input,
            options=options,
        )

    def submit_job(self, job):
        request = self._request_from_job(job)
        response = self.gateway.request(request)

        if hasattr(response, "status"):
            status = response.status
            output = response.output
            error = getattr(response, "error", "")
            model = getattr(response, "model", request.model)
            usage = getattr(response, "usage", {})
        else:
            response = response or {}
            status = response.get("status")
            output = response.get("output")
            error = response.get("error", "")
            model = response.get("model", request.model)
            usage = response.get("usage", {})

        normalized_status = str(status or "failed").strip().lower()
        if normalized_status not in {"submitted", "running", "completed", "failed"}:
            normalized_status = "failed"
            if not error:
                error = f"unsupported AI Gateway status: {status}"

        return {
            "provider": "ai_gateway",
            "status": normalized_status,
            "output": output,
            "error": error or None,
            "model": model,
            "usage": usage if isinstance(usage, dict) else {},
            "task_type": request.task_type,
        }

    def get_status(self, job_id):
        return {"job_id": job_id, "status": "processing"}

    def cancel_job(self, job_id):
        return {"job_id": job_id, "status": "cancelled"}

    def run(self, job):
        result = self.submit_job(job)
        return {
            "status": result["status"],
            "provider": "ai_gateway",
            "output": result.get("output"),
            "error": result.get("error"),
            "model": result.get("model"),
            "usage": result.get("usage") or {},
            "task_type": result.get("task_type"),
        }

    def get_provider_status(self):
        video_provider = getattr(self.gateway, "providers", {}).get("video")
        if video_provider and hasattr(video_provider, "initialize"):
            video_status = video_provider.initialize()
        else:
            video_status = {
                "status": "unknown",
                "configured": False,
                "missing_configuration": ["AI_GATEWAY_VIDEO_URL"],
            }

        return {
            "provider": "ai_gateway",
            "status": video_status.get("status", "unknown"),
            "configured": bool(video_status.get("configured")),
            "transport": video_status.get("transport", "remote_http"),
            "local_inference": False,
            "missing_configuration": video_status.get("missing_configuration") or [],
        }
