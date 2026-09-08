from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
TESTS = ROOT / "os" / "backend" / "tests"
sys.path.insert(0, str(ROOT / "os" / "backend"))


def test_no_destructive_production_db_literals_in_tests():
    offenders = []
    for path in TESTS.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if path.name == Path(__file__).name:
            continue
        normalized = text.replace("\\", "/").lower()
        if "os/database/os.db" in normalized:
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, "direct production DB path in test code: " + ", ".join(offenders)


def test_test_mode_requires_override():
    import os
    from data.database_path import database_path
    old_testing, old_path = os.environ.get("OS_TESTING"), os.environ.get("OS_DATABASE_PATH")
    try:
        os.environ["OS_TESTING"] = "1"
        os.environ.pop("OS_DATABASE_PATH", None)
        try:
            database_path()
        except RuntimeError as exc:
            assert "OS_DATABASE_PATH" in str(exc)
        else:
            raise AssertionError("test mode accepted missing database override")
    finally:
        if old_testing is None: os.environ.pop("OS_TESTING", None)
        else: os.environ["OS_TESTING"] = old_testing
        if old_path is None: os.environ.pop("OS_DATABASE_PATH", None)
        else: os.environ["OS_DATABASE_PATH"] = old_path


def test_production_paths_are_rejected():
    import os
    import tempfile
    from data.database_path import PRODUCTION_DB_PATH, database_path
    old_testing, old_path = os.environ.get("OS_TESTING"), os.environ.get("OS_DATABASE_PATH")
    try:
        os.environ["OS_TESTING"] = "1"
        for candidate in (PRODUCTION_DB_PATH, PRODUCTION_DB_PATH.parent / "test.db"):
            os.environ["OS_DATABASE_PATH"] = str(candidate)
            try:
                database_path()
            except RuntimeError as exc:
                assert "REFUSING" in str(exc)
            else:
                raise AssertionError(f"unsafe test database accepted: {candidate}")
        os.environ["OS_DATABASE_PATH"] = str(Path(tempfile.gettempdir()) / "safe-test.db")
        assert database_path().parent == Path(tempfile.gettempdir()).resolve()
    finally:
        if old_testing is None: os.environ.pop("OS_TESTING", None)
        else: os.environ["OS_TESTING"] = old_testing
        if old_path is None: os.environ.pop("OS_DATABASE_PATH", None)
        else: os.environ["OS_DATABASE_PATH"] = old_path


if __name__ == "__main__":
    test_no_destructive_production_db_literals_in_tests()
    test_test_mode_requires_override()
    test_production_paths_are_rejected()
    print("Test database isolation static safety gate passed")
