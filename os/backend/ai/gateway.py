from .router import route
from .providers.text import TextProvider
from .providers.video import VideoProvider

class AIGatewayService:
    def __init__(self):
        self.providers = {
            "text": TextProvider(),
            "video": VideoProvider()
        }

    def request(self, request):
        provider_name = route(request.task_type)
        provider = self.providers[provider_name]
        return provider.request(request)
