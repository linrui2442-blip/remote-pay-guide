from ai.gateway import AIGatewayService
from ai.models import AIRequest

class ContentAnalyzer:
    def __init__(self):
        self.gateway = AIGatewayService()

    def analyze(self, lifecycle, performance):
        request = AIRequest(
            task_type="analysis",
            prompt=f"Analyze content lifecycle: {lifecycle}, performance: {performance}"
        )
        return self.gateway.request(request)
