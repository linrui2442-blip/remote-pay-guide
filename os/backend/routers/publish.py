from fastapi import APIRouter

from publish.registry import get_registry_status


router = APIRouter()


@router.get('/publish/platforms')
def publish_platforms():
    """Return runtime publish adapters with Data Center capability metadata."""
    return get_registry_status()


# Existing publish service calls remain unchanged; this router only exposes
# registry visibility for the OS control center.
