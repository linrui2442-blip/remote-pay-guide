from .router import route
from .providers.text import TextProvider
from .providers.video import VideoProvider


class AIGatewayService:
    def __init__(self):
        self.providers = {
            "text": TextProvider(),
            "video": VideoProvider(),
        }

    def request(self, request):
        provider_name = route(request.task_type)
        provider = self.providers[provider_name]
        return provider.request(request)

    def poll(self, task_type, output, *, model="auto"):
        provider_name = route(task_type)
        provider = self.providers[provider_name]
        if not hasattr(provider, "poll"):
            raise ValueError(f"AI provider {provider_name} does not support polling")
        return provider.poll(output, model=model)


# Backward-compatible name used by earlier OS router code.
AIService = AIGatewayService
