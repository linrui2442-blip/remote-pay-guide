class GitHubProductionProvider:
    def initialize(self):
        return {
            "provider": "github",
            "status": "ready"
        }

    def run(self, task):
        return {
            "provider": "github",
            "status": "started",
            "workflow": task.get("workflow")
        }

    def get_status(self):
        return {
            "provider": "github",
            "status": "ready"
        }
