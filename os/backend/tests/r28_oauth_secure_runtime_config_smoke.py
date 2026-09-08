import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "os" / "backend"
sys.path.insert(0, str(BACKEND))

from analytics.adapters import youtube as analytics_youtube
from config.secure_store import (
    LocalSecretStore,
    SecureStoreCorruptError,
    SecureStoreUnavailableError,
)
from oauth import runtime_config
from oauth.providers import youtube as youtube_provider
from oauth.providers.youtube import (
    YOUTUBE_ANALYTICS_SCOPE,
    YOUTUBE_READ_SCOPE,
    YouTubeOAuthProvider,
)


class FakeProtector:
    prefix = b"protected:"

    def protect(self, value):
        return self.prefix + value[::-1]

    def unprotect(self, value):
        if not value.startswith(self.prefix):
            raise SecureStoreCorruptError("corrupt test payload")
        return value[len(self.prefix):][::-1]


def assert_parser_contract():
    fixtures = [
        ({"installed": {"client_id": "id-a", "client_secret": "secret-a"}}, "installed"),
        ({"web": {"client_id": "id-b", "client_secret": "secret-b"}}, "web"),
        ({"client_id": "id-c", "client_secret": "secret-c"}, "minimal_recovery"),
    ]
    for value, expected in fixtures:
        assert runtime_config.parse_client_config(value)["client_type"] == expected
    for value in [None, {}, {"client_id": "id"}, {"client_secret": "secret"}, {"installed": {}, "web": {}}]:
        try:
            runtime_config.parse_client_config(value)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid OAuth client configuration was accepted")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "invalid.json"
        path.write_text("not-json", encoding="utf-8")
        try:
            runtime_config.load_client_config(path)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid JSON was accepted")


def assert_cli_import_contract():
    fixtures = [
        ("installed", {"installed": {"client_id": "id-a", "client_secret": "secret-a"}}),
        ("web", {"web": {"client_id": "id-b", "client_secret": "secret-b"}}),
        ("minimal_recovery", {"client_id": "id-c", "client_secret": "secret-c"}),
    ]
    original_set = runtime_config.set_secret
    original_delete = runtime_config.delete_secret
    stored = {}
    try:
        runtime_config.set_secret = stored.__setitem__
        runtime_config.delete_secret = lambda name: stored.pop(name, None)
        with tempfile.TemporaryDirectory() as directory:
            for expected, value in fixtures:
                path = Path(directory) / f"{expected}.json"
                path.write_text(json.dumps(value), encoding="utf-8")
                output = StringIO()
                with redirect_stdout(output):
                    runtime_config.main(["import-json", str(path)])
                assert output.getvalue().strip() == "YouTube OAuth client configuration saved."
                assert runtime_config.load_client_config(path)["client_type"] == expected
                assert "secret-" not in output.getvalue()
    finally:
        runtime_config.set_secret = original_set
        runtime_config.delete_secret = original_delete


def assert_store_and_provider_contract():
    with tempfile.TemporaryDirectory() as directory:
        store = LocalSecretStore(directory, protector=FakeProtector())
        assert store.get_secret("missing") is None
        store.set_secret("youtube_oauth_client_id", "secure-id")
        store.set_secret("youtube_oauth_client_secret", "secure-secret")
        assert store.has_secret("youtube_oauth_client_id")
        reloaded = LocalSecretStore(directory, protector=FakeProtector())
        provider = YouTubeOAuthProvider(secret_getter=reloaded.get_secret)
        assert provider.client_id == "secure-id"
        assert provider.client_secret == "secure-secret"

        names = ("YOUTUBE_OAUTH_CLIENT_ID", "YOUTUBE_OAUTH_CLIENT_SECRET", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET")
        original = {name: os.environ.get(name) for name in names}
        try:
            os.environ["YOUTUBE_OAUTH_CLIENT_ID"] = "env-id"
            os.environ["YOUTUBE_OAUTH_CLIENT_SECRET"] = "env-secret"
            env_provider = YouTubeOAuthProvider(secret_getter=reloaded.get_secret)
            assert (env_provider.client_id, env_provider.client_secret) == ("env-id", "env-secret")
            explicit = YouTubeOAuthProvider(client_id="explicit-id", client_secret="explicit-secret", secret_getter=reloaded.get_secret)
            assert (explicit.client_id, explicit.client_secret) == ("explicit-id", "explicit-secret")
        finally:
            for name, value in original.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

        (Path(directory) / "corrupt.bin").write_bytes(b"not-protected")
        try:
            store.get_secret("corrupt")
        except SecureStoreCorruptError:
            pass
        else:
            raise AssertionError("corrupt encrypted payload did not fail safely")
        store.delete_secret("youtube_oauth_client_secret")
        assert not store.has_secret("youtube_oauth_client_secret")

    with tempfile.TemporaryDirectory() as directory:
        if os.name == "nt":
            store = LocalSecretStore(directory)
            store.set_secret("dpapi_probe", "fake-dpapi-test-value")
            assert store.get_secret("dpapi_probe") == "fake-dpapi-test-value"
            store.delete_secret("dpapi_probe")
        else:
            try:
                LocalSecretStore(directory)
            except SecureStoreUnavailableError:
                pass
            else:
                raise AssertionError("non-Windows default store did not fail safely")


def assert_readiness_contract():
    values = {"youtube_oauth_client_id": "readiness-secure-id", "youtube_oauth_client_secret": "readiness-secure-secret"}
    original_secret = youtube_provider.get_secret
    original_token = analytics_youtube.get_token
    names = ("YOUTUBE_OAUTH_CLIENT_ID", "YOUTUBE_OAUTH_CLIENT_SECRET", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET")
    original_env = {name: os.environ.get(name) for name in names}
    try:
        for name in names:
            os.environ.pop(name, None)
        youtube_provider.get_secret = values.get
        analytics_youtube.get_token = lambda account_id: {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "scopes": [YOUTUBE_READ_SCOPE, YOUTUBE_ANALYTICS_SCOPE],
        }
        status = analytics_youtube.YouTubeAnalyticsAdapter().readiness(account_id=1)
        assert status["oauth_client_configured"] is True
        assert status["credential_ready"] is True
        assert status["refresh_ready"] is True
        serialized = json.dumps(status)
        for value in [*values.values(), "test-access-token", "test-refresh-token"]:
            assert value not in serialized
    finally:
        youtube_provider.get_secret = original_secret
        analytics_youtube.get_token = original_token
        for name, value in original_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def main():
    assert_parser_contract()
    assert_cli_import_contract()
    assert_store_and_provider_contract()
    assert_readiness_contract()
    print("OAuth secure runtime configuration smoke test passed")
    print("formats; lifecycle; precedence; corruption; readiness; no serialization")


if __name__ == "__main__":
    main()
