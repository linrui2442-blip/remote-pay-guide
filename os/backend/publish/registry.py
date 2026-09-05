from publish.adapters.youtube import YouTubeAdapter
from publish.adapters.tiktok import TikTokAdapter
from publish.adapters.instagram import InstagramAdapter
from publish.adapters.facebook import FacebookAdapter


platform_registry = {
    "youtube": YouTubeAdapter(),
    "tiktok": TikTokAdapter(),
    "instagram": InstagramAdapter(),
    "facebook": FacebookAdapter(),
}

for adapter in platform_registry.values():
    adapter.initialize()


def get_adapter(platform):
    if not isinstance(platform, str):
        return None
    return platform_registry.get(platform.lower())
