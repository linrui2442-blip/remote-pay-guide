"""Run existing registry/resolver/publish-prepare assertions with offline I/O."""
import gc
import os
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'os/backend'))
sys.path.insert(0, str(Path(__file__).parent))
TEMP = tempfile.TemporaryDirectory(prefix='g4d-legacy-')
os.environ.update(OS_TESTING='1', OS_DATABASE_PATH=str(Path(TEMP.name) / 'os.db'))


def blocked(*a, **k):
    raise AssertionError('Real network forbidden')


def main():
    from assets.manager import create_video_asset, get_asset_by_asset_id
    manual = {'asset_id': 'legacy-upsert', 'video_id': 'manual', 'source_provider': 'external',
              'storage_type': 'external', 'asset_url': 'https://example.test/manual.mp4', 'status': 'ready'}
    create_video_asset(manual)
    create_video_asset({**manual, 'metadata': {'updated': True}})
    assert get_asset_by_asset_id('legacy-upsert')['metadata'] == {'updated': True}
    print('G4D_LEGACY_REGISTRY_UPSERT=PASS')
    import r39_github_pages_videoasset_integration_smoke as r39
    for test in (r39.test_github_result_binds_ready_video_asset_and_instagram_prepare,
                 r39.test_runtime_worker_preserves_provider_content_identity,
                 r39.test_public_url_verifier_rejects_html_and_accepts_video):
        with pytest.MonkeyPatch.context() as monkeypatch:
            test(monkeypatch)
    print('G4D_R39_LEGACY_ASSET_REGRESSION=PASS')
    import r3_youtube_readiness_smoke as r3
    class Response:
        status_code = 200
        headers = {'Content-Type': 'video/mp4', 'Content-Length': '65536'}
        def iter_content(self, chunk_size):
            yield b'x' * 65536
        def close(self):
            pass
    class Session:
        def get(self, *args, **kwargs):
            return Response()
    with patch('publish.asset_resolver.requests.Session', Session):
        r3.test_r2_online_asset_to_temp_and_cleanup()
    print('G4D_EXISTING_RESOLVER_FAKE_HTTP_REGRESSION=PASS')


if __name__ == '__main__':
    try:
        with patch.object(socket.socket, 'connect', blocked), patch.object(socket, 'getaddrinfo', blocked):
            main()
    finally:
        gc.collect()
        TEMP.cleanup()
