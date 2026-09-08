"""Manage local YouTube OAuth client configuration without exposing values."""

import argparse
import json
from pathlib import Path

from config.secure_store import delete_secret, has_secret, set_secret


CLIENT_ID_KEY = "youtube_oauth_client_id"
CLIENT_SECRET_KEY = "youtube_oauth_client_secret"


def parse_client_config(value):
    if not isinstance(value, dict):
        raise ValueError("OAuth client JSON must contain an object")
    if "installed" in value and "web" in value:
        raise ValueError("OAuth client JSON must contain one client type")
    if "installed" in value:
        client_type, config = "installed", value["installed"]
    elif "web" in value:
        client_type, config = "web", value["web"]
    else:
        client_type, config = "minimal_recovery", value
    if not isinstance(config, dict):
        raise ValueError("OAuth client configuration must contain an object")
    client_id = config.get("client_id")
    client_secret = config.get("client_secret")
    if not isinstance(client_id, str) or not client_id.strip():
        raise ValueError("OAuth client configuration is missing client_id")
    if not isinstance(client_secret, str) or not client_secret.strip():
        raise ValueError("OAuth client configuration is missing client_secret")
    return {
        "client_type": client_type,
        "client_id": client_id.strip(),
        "client_secret": client_secret.strip(),
    }


def load_client_config(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("OAuth client JSON is invalid") from exc
    return parse_client_config(value)


def import_json(path):
    config = load_client_config(path)
    set_secret(CLIENT_ID_KEY, config["client_id"])
    try:
        set_secret(CLIENT_SECRET_KEY, config["client_secret"])
    except Exception:
        delete_secret(CLIENT_ID_KEY)
        raise
    return config["client_type"]


def configured():
    return has_secret(CLIENT_ID_KEY) and has_secret(CLIENT_SECRET_KEY)


def clear():
    delete_secret(CLIENT_ID_KEY)
    delete_secret(CLIENT_SECRET_KEY)


def main(argv=None):
    parser = argparse.ArgumentParser(description="YouTube OAuth runtime configuration")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    importer = commands.add_parser("import-json")
    importer.add_argument("path")
    commands.add_parser("clear")
    args = parser.parse_args(argv)
    if args.command == "status":
        print("configured" if configured() else "missing")
    elif args.command == "import-json":
        import_json(args.path)
        print("YouTube OAuth client configuration saved.")
    else:
        clear()
        print("YouTube OAuth client configuration cleared.")


if __name__ == "__main__":
    main()
