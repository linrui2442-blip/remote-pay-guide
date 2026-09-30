"""Import/route preparation only. No ASGI lifespan or background workers."""
from test_database_helper import TEST_DATABASE_PATH
import os
import socket
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'os/backend'))
os.environ['OS_DISABLE_BACKGROUND_ACCOUNT_SYNC'] = '1'
os.environ['OS_DISABLE_ANALYTICS_BACKFILL_WORKER'] = '1'


def main():
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
        import main as backend
        from routers.runtime import operational_health
        from data.database_path import database_path, PRODUCTION_DB_PATH
        assert database_path() == TEST_DATABASE_PATH and database_path() != PRODUCTION_DB_PATH
        routes = list(backend.app.openapi()['paths'])
        assert routes.count('/operations/health') == 1
        response = operational_health()
        assert response['kill_switch_active']
        assert not backend.runtime_poller.status()['running']
        with patch.dict(os.environ, OS_DATABASE_PATH=str(PRODUCTION_DB_PATH)):
            try:
                database_path()
            except RuntimeError:
                pass
            else:
                raise AssertionError('production test path permitted')
        assert 'PROJECT_STATUS.md' in (ROOT/'README.md').read_text(encoding='utf-8')
        assert '--lifespan off' in (ROOT/'README.md').read_text(encoding='utf-8')
    print('G9_ISOLATED_IMPORT_AND_ROUTE=PASS')
    print('G9_BACKGROUND_WORKERS_NOT_STARTED=PASS')
    print('G9_PRODUCTION_TEST_PATH_REJECTED=PASS')
    print('G9_FRESH_MACHINE_INSTALL=NOT_EXECUTED')


if __name__ == '__main__':
    main()
