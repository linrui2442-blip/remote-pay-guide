from .github import GitHubProductionProvider
from .ai_gateway import AIGatewayProvider

production_provider_registry = {
    "github": GitHubProductionProvider(),
    "ai_gateway": AIGatewayProvider()
}


def get_provider(name):
    return production_provider_registry.get(name)
