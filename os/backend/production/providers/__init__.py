from .github import GitHubProductionProvider

production_provider_registry = {
    "github": GitHubProductionProvider()
}


def get_provider(name):
    return production_provider_registry.get(name)
