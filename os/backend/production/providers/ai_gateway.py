class AIGatewayProvider:
    def __init__(self):
        self.config = None

    def initialize(self, config=None):
        self.config = config or {}
        return {
            "provider": "ai_gateway",
            "status": "ready"
        }

    def submit_job(self, task):
        return {
            "provider": "ai_gateway",
            "status": "submitted",
            "job_id": "mock_ai_job"
        }

    def get_status(self, job_id):
        return {
            "job_id": job_id,
            "status": "processing"
        }

    def cancel_job(self, job_id):
        return {
            "job_id": job_id,
            "status": "cancelled"
        }

    def run(self, task):
        submitted = self.submit_job(task)
        return {
            "status": "completed",
            "provider": "ai_gateway",
            "output": submitted
        }

    def get_provider_status(self):
        return {
            "provider": "ai_gateway",
            "status": "ready"
        }
