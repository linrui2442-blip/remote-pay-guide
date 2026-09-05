from ai.gateway import AIGatewayService
from ai.models import AIRequest


class AIGatewayProvider:
    def __init__(self):
        self.config = None
        self.gateway = AIGatewayService()

    def initialize(self, config=None):
        self.config = config or {}
        return {
            "provider": "ai_gateway",
            "status": "ready"
        }

    def submit_job(self, task):
        request = AIRequest(
            task_type=task.get("task_type", "analysis"),
            model=task.get("model", "auto"),
            prompt=task.get("prompt", ""),
            input=task.get("input", {}),
            options=task.get("options", {})
        )
        response = self.gateway.request(request)
        return {
            "provider": "ai_gateway",
            "status": response.status if hasattr(response, "status") else response.get("status"),
            "output": response.output if hasattr(response, "output") else response.get("output")
        }

    def get_status(self, job_id):
        return {"job_id": job_id, "status": "processing"}

    def cancel_job(self, job_id):
        return {"job_id": job_id, "status": "cancelled"}

    def run(self, task):
        result = self.submit_job(task)
        return {
            "status": "completed",
            "provider": "ai_gateway",
            "output": result
        }

    def get_provider_status(self):
        return {
            "provider": "ai_gateway",
            "status": "ready"
        }
