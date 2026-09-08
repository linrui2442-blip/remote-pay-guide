"""Central database path resolution and test safety boundary."""
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PRODUCTION_DB_PATH = (REPO_ROOT / "os" / "database" / "os.db").resolve()


def database_path() -> Path:
    configured = os.getenv("OS_DATABASE_PATH")
    testing = str(os.getenv("OS_TESTING") or "").lower() in {"1", "true", "yes"}
    if testing and not configured:
        raise RuntimeError("OS_TESTING requires OS_DATABASE_PATH")
    path = Path(configured).expanduser().resolve() if configured else PRODUCTION_DB_PATH
    if testing:
        try:
            path.relative_to(PRODUCTION_DB_PATH.parent)
            inside_production = True
        except ValueError:
            inside_production = False
        if path == PRODUCTION_DB_PATH or inside_production:
            raise RuntimeError("REFUSING_TO_USE_PRODUCTION_RUNTIME_DB_IN_TEST_MODE")
    return path


def assert_safe_test_database_path(path) -> Path:
    resolved = Path(path).expanduser().resolve()
    if str(os.getenv("OS_TESTING") or "").lower() not in {"1", "true", "yes"}:
        raise RuntimeError("test database operations require OS_TESTING=1")
    if resolved == PRODUCTION_DB_PATH:
        raise RuntimeError("REFUSING_TO_USE_PRODUCTION_RUNTIME_DB_IN_TEST_MODE")
    try:
        resolved.relative_to(PRODUCTION_DB_PATH.parent)
    except ValueError:
        return resolved
    raise RuntimeError("test database cannot be under the production database directory")


def isolated_test_database():
    """Return a temp-root DB path and environment values for a test process."""
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="remote-pay-guide-tests-"))
    path = root / "os.db"
    assert_safe_test_database_path(path) if os.getenv("OS_TESTING") else None
    return root, path
