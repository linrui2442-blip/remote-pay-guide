"""Existing adapter/Publish Center pytest regressions in external TEMP, offline."""
import gc
import os
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'os/backend'))


def blocked(*args, **kwargs):
    raise AssertionError('Real network forbidden in G5 regression')


def main():
    import pytest
    with tempfile.TemporaryDirectory(prefix='g5-publish-regressions-') as temp:
        os.environ.update(OS_TESTING='1', OS_DATABASE_PATH=str(Path(temp) / 'isolated.db'),
                          META_INSTAGRAM_LIVE_PUBLISH_ENABLED='false', META_FACEBOOK_LIVE_PUBLISH_ENABLED='false')
        tests = ['r36_instagram_reels_adapter_smoke.py', 'r37_instagram_reels_graph_contract_smoke.py',
                 'r38_instagram_publish_center_integration_smoke.py', 'r42_facebook_reels_graph_contract_smoke.py']
        try:
            with patch.object(socket.socket, 'connect', blocked), patch.object(socket, 'getaddrinfo', blocked):
                code = pytest.main(['-q', '-p', 'no:cacheprovider', '--basetemp', str(Path(temp) / 'pytest'),
                                    *[str(Path(__file__).parent / name) for name in tests]])
            assert code == 0, 'Existing publish regression failed'
        finally:
            gc.collect()
    print('G5_LEGACY_PUBLISH_ADAPTER_REGRESSIONS=PASS')


if __name__ == '__main__':
    main()
