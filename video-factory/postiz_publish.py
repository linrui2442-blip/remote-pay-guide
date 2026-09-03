from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests


PLATFORMS = ("facebook", "instagram", "youtube")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish one polished Remote Pay Guide video through a local Postiz Public API."
    )
    parser.add_argument("--content-id", required=True)
    parser.add_argument("--artifact-root", default="batch-output")
    parser.add_argument("--posting-pack", default="content/posting-pack-01.md")
    parser.add_argument("--schedule-at", default="")
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("POSTIZ_API_BASE_URL", "http://localhost:4007/api/public/v1"),
    )
    parser.add_argument("--state-dir", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def default_state_dir() -> Path:
    configured = os.getenv("POSTIZ_STATE_DIR")
    if configured:
        return Path(configured)
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "RemotePayGuide" / "publish-state"
    return Path.home() / ".remote-pay-guide" / "publish-state"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def section_number(content_id: str) -> str:
    match = re.fullmatch(r"short(\d+)", content_id)
    if not match:
        raise SystemExit(f"Unsupported content id: {content_id}")
    return str(int(match.group(1)))


def parse_posting_pack(path: Path, content_id: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    number = section_number(content_id)
    pattern = re.compile(
        rf"^## Post {re.escape(number)}\s*$\n(?P<body>.*?)(?=^## Post \d+\s*$|^---\s*$)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        raise SystemExit(f"Could not find posting-pack section for {content_id}")

    body = match.group("body")

    def field(name: str) -> str:
        field_match = re.search(rf"^\*\*{re.escape(name)}:\*\*\s*(.+)$", body, re.MULTILINE)
        if not field_match:
            raise SystemExit(f"Missing {name} for {content_id} in {path}")
        return field_match.group(1).strip()

    source = field("Source").strip("`")
    title = field("Title")
    caption = field("Caption")
    tags_text = field("Tags")
    tags = [item for item in tags_text.split() if item.startswith("#")]
    return {
        "source": source,
        "title": title,
        "caption": caption,
        "tags": tags,
    }


def normalize_schedule(value: str, existing: str | None) -> str:
    if existing:
        return existing
    if not value:
        dt = datetime.now(timezone.utc) + timedelta(minutes=20)
    else:
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise SystemExit(f"Invalid --schedule-at value: {value}") from exc
        if dt.tzinfo is None:
            raise SystemExit("--schedule-at must include a timezone offset or Z")
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


class PostizClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": api_key}

    def integrations(self) -> list[dict[str, Any]]:
        response = requests.get(
            f"{self.base_url}/integrations",
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise RuntimeError("Postiz integrations response was not a list")
        return data

    def upload(self, video: Path) -> dict[str, Any]:
        with video.open("rb") as handle:
            response = requests.post(
                f"{self.base_url}/upload",
                headers=self.headers,
                files={"file": (video.name, handle, "video/mp4")},
                timeout=300,
            )
        response.raise_for_status()
        data = response.json()
        if not data.get("id") or not data.get("path"):
            raise RuntimeError("Postiz upload response did not include id/path")
        return {"id": data["id"], "path": data["path"]}

    def create_post(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        response = requests.post(
            f"{self.base_url}/posts",
            headers={**self.headers, "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list) or not data:
            raise RuntimeError("Postiz create-post response was empty or invalid")
        return data


def resolve_integrations(
    integrations: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    resolved: dict[str, dict[str, Any]] = {}
    for platform in PLATFORMS:
        override = os.getenv(f"POSTIZ_{platform.upper()}_ID", "").strip()
        enabled = [
            item
            for item in integrations
            if item.get("identifier") == platform and not item.get("disabled", False)
        ]
        if override:
            matches = [item for item in enabled if item.get("id") == override]
            if len(matches) != 1:
                raise RuntimeError(
                    f"POSTIZ_{platform.upper()}_ID does not match an enabled {platform} integration"
                )
            resolved[platform] = matches[0]
            continue
        if len(enabled) != 1:
            names = [f"{item.get('name')} ({item.get('id')})" for item in enabled]
            raise RuntimeError(
                f"Expected exactly one enabled {platform} integration, found {len(enabled)}: {names}. "
                f"Set POSTIZ_{platform.upper()}_ID if needed."
            )
        resolved[platform] = enabled[0]
    return resolved


def provider_settings(platform: str, post: dict[str, Any]) -> dict[str, Any]:
    if platform == "facebook":
        return {
            "__type": "facebook",
            "url": "https://linrui2442-blip.github.io/remote-pay-guide/" + post["source"],
        }
    if platform == "instagram":
        return {
            "__type": "instagram",
            "post_type": "post",
            "is_trial_reel": False,
            "collaborators": [],
        }
    if platform == "youtube":
        youtube_tags = [
            {"value": tag.lstrip("#"), "label": tag.lstrip("#")}
            for tag in post["tags"]
        ]
        return {
            "__type": "youtube",
            "title": post["title"][:100],
            "type": "public",
            "selfDeclaredMadeForKids": "no",
            "thumbnail": None,
            "tags": youtube_tags,
        }
    raise ValueError(f"Unsupported platform: {platform}")


def build_payload(
    platform: str,
    integration_id: str,
    media: dict[str, Any],
    post: dict[str, Any],
    scheduled_at: str,
) -> dict[str, Any]:
    body = post["caption"]
    if post["tags"]:
        body += "\n\n" + " ".join(post["tags"])
    return {
        "type": "schedule",
        "date": scheduled_at,
        "shortLink": False,
        "tags": [],
        "posts": [
            {
                "integration": {"id": integration_id},
                "value": [{"content": body, "image": [media]}],
                "settings": provider_settings(platform, post),
            }
        ],
    }


def main() -> None:
    args = parse_args()
    artifact_root = Path(args.artifact_root)
    content_dir = artifact_root / args.content_id
    metadata_path = content_dir / "metadata.json"
    if not metadata_path.exists():
        raise SystemExit(f"Missing metadata: {metadata_path}")

    metadata = load_json(metadata_path)
    if metadata.get("content_id") != args.content_id:
        raise SystemExit("metadata content_id does not match --content-id")
    if metadata.get("status") != "succeeded":
        raise SystemExit(f"{args.content_id} metadata.status is not succeeded")

    output_name = metadata.get("output")
    if not output_name:
        raise SystemExit(f"{args.content_id} metadata has no output field")
    video = content_dir / str(output_name)
    if not video.exists() or video.stat().st_size <= 0:
        raise SystemExit(f"Missing or empty polished video: {video}")

    posting_pack = parse_posting_pack(Path(args.posting_pack), args.content_id)
    state_dir = Path(args.state_dir) if args.state_dir else default_state_dir()
    state_path = state_dir / f"{args.content_id}.json"
    state: dict[str, Any] = load_json(state_path) if state_path.exists() else {}
    if state and state.get("content_id") != args.content_id:
        raise SystemExit(f"State file content_id mismatch: {state_path}")

    scheduled_at = normalize_schedule(args.schedule_at, state.get("scheduled_at"))
    state.setdefault("content_id", args.content_id)
    state.setdefault("scheduled_at", scheduled_at)
    state.setdefault("platforms", {})
    save_state(state_path, state)

    api_key = os.getenv("POSTIZ_API_KEY", "").strip()
    if not api_key and not args.dry_run:
        raise SystemExit("Missing POSTIZ_API_KEY environment variable")

    if args.dry_run:
        print(
            json.dumps(
                {
                    "content_id": args.content_id,
                    "video": str(video),
                    "scheduled_at": scheduled_at,
                    "state_path": str(state_path),
                    "title": posting_pack["title"],
                    "platforms": list(PLATFORMS),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    client = PostizClient(args.api_base_url, api_key)
    integrations = resolve_integrations(client.integrations())

    media = state.get("media")
    if not media:
        media = client.upload(video)
        state["media"] = media
        save_state(state_path, state)

    any_failure = False
    for platform in PLATFORMS:
        platform_state = state["platforms"].get(platform, {})
        if platform_state.get("status") == "succeeded":
            print(
                f"SKIP {args.content_id}:{platform} already succeeded "
                f"(postId={platform_state.get('postiz_post_id')})"
            )
            continue

        integration = integrations[platform]
        payload = build_payload(
            platform,
            str(integration["id"]),
            media,
            posting_pack,
            scheduled_at,
        )
        attempt = int(platform_state.get("attempt", 0)) + 1
        try:
            result = client.create_post(payload)
            first = result[0]
            state["platforms"][platform] = {
                "status": "succeeded",
                "attempt": attempt,
                "integration_id": integration["id"],
                "postiz_post_id": first.get("postId"),
                "scheduled_at": scheduled_at,
            }
            print(
                f"SUCCESS {args.content_id}:{platform} -> "
                f"{first.get('postId', '<no-post-id>')}"
            )
        except Exception as exc:
            any_failure = True
            state["platforms"][platform] = {
                "status": "failed",
                "attempt": attempt,
                "integration_id": integration.get("id"),
                "scheduled_at": scheduled_at,
                "error": f"{type(exc).__name__}: {exc}",
            }
            print(f"FAILED {args.content_id}:{platform}: {type(exc).__name__}: {exc}")
        finally:
            save_state(state_path, state)

    print(f"Publish state: {state_path}")
    if any_failure:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
