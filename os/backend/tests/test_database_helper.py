"""Process-wide isolated database bootstrap for standalone smoke scripts."""
import atexit
import os
import shutil
import tempfile
from pathlib import Path


_ROOT = Path(tempfile.mkdtemp(prefix="remote-pay-guide-tests-"))
TEST_DATABASE_PATH = (_ROOT / "os.db").resolve()
os.environ["OS_TESTING"] = "1"
os.environ["OS_DATABASE_PATH"] = str(TEST_DATABASE_PATH)


def assert_safe_test_database_path(path=TEST_DATABASE_PATH):
    from data.database_path import assert_safe_test_database_path as guard
    return guard(path)


def cleanup():
    assert_safe_test_database_path(TEST_DATABASE_PATH)
    shutil.rmtree(_ROOT, ignore_errors=True)


atexit.register(cleanup)
