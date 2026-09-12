"""Read-only Instagram Professional Account content synchronization."""

import re
from datetime import datetime, timezone

import requests

from accounts.manager import get_account
from assets.manager import create_video_asset
from data.sync_state import (
    get_sync_state,
    mark_sync_failure,
    mark_sync_started,
    mark_sync_success,
)
from oauth.manager import get_token
from oauth.meta_bindings import get_binding
from oauth.providers.meta import MetaOAuthProvider
from publish.manager import create_publish_task, get_publish_tasks, update_publish_status
from publish.models import PublishTask


SYNC_MODES = {"incremental", "full_refresh"}
MEDIA_FIELDS = "id,caption,media_type,media_product_type,permalink,timestamp,media_url,thumbnail_url"


class InstagramGraphReadClient:
    BASE_URL = "https://graph.facebook.com/v26.0"

    def __init__(self, transport=None):
        self.transport = transport or requests

    def list_media(self, instagram_user_id, page_token, *, limit=25):
        params = {"fields": MEDIA_FIELDS, "limit": min(25, max(1, int(limit)))}
        response = self.transport.get(
            f"{self.BASE_URL}/{instagram_user_id}/media",
            params=params,
            headers={"Authorization": f"Bearer {page_token}"},
            timeout=30,
        )
        if not getattr(response, "ok", False):
            detail = {}
            try:
                detail = (response.json() or {}).get("error") or {}
            except Exception:
                pass
            raise RuntimeError(
                f"Meta Instagram media read failed ({getattr(response, 'status_code', 'unknown')}): "
                f"{detail.get('message') or 'provider request failed'}"
            )
        return response.json() or {}


class InstagramContentSync:
    """Bounded, metadata-only import of Instagram Reels."""

    def __init__(self, transport=None, page_token_resolver=None):
        self.transport = transport
        self.page_token_resolver = page_token_resolver or self._resolve_page_token

    @staticmethod
    def _safe_error(error, secrets=()):
        text = str(error)
        for secret in secrets:
            if secret:
                text = text.replace(str(secret), "[REDACTED]")
        return re.sub(r"(?i)(Bearer|OAuth)\s+[^\s,;]+", "[REDACTED_CREDENTIAL]", text)

    @staticmethod
    def _resolve_page_token(account_id, page_id, user_token, transport=None):
        return MetaOAuthProvider(platform="instagram").resolve_page_access_token(
            account_id, page_id, access_token=user_token, transport=transport
        )

    def _validate_local(self, account_id):
        account = get_account(account_id)
        binding = get_binding(account_id)
        token = get_token(account_id)
        missing = []
        if not account or str(account.get("platform", "")).lower() != "instagram":
            missing.append("instagram_account")
        if not binding or not binding.get("page_id") or not binding.get("instagram_user_id"):
            missing.append("instagram_binding")
        if not token or token.get("provider") not in {"instagram", "meta", "facebook"} or not token.get("access_token"):
            missing.append("meta_user_credential")
        if token and token.get("expires_at"):
            try:
                expiry = datetime.fromisoformat(str(token["expires_at"]).replace("Z", "+00:00"))
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry <= datetime.now(timezone.utc):
                    missing.append("expired_credential")
            except ValueError:
                missing.append("invalid_credential_expiry")
        if missing:
            raise RuntimeError("Instagram content sync readiness failed: " + ", ".join(missing))
        return account, binding, token

    @staticmethod
    def _reels(items):
        return [item for item in items if str(item.get("media_product_type") or "").upper() == "REELS"]

    def _read_bounded(self, user_id, page_token, max_results):
        client = InstagramGraphReadClient(self.transport)
        items, after = [], None
        # One bounded page is sufficient for the active window and prevents an
        # accidental scan of an account's complete history.
        payload = client.list_media(user_id, page_token, limit=max_results)
        items.extend(payload.get("data") or [])
        paging = payload.get("paging") or {}
        after = (paging.get("cursors") or {}).get("after")
        return items[:max_results], after

    def sync(self, account_id, max_results=10, sync_mode="incremental"):
        max_results = min(25, max(1, int(max_results or 10)))
        mode = str(sync_mode or "incremental").strip().lower()
        if mode not in SYNC_MODES:
            raise ValueError(f"unsupported content sync mode: {sync_mode}")
        state = get_sync_state(account_id, "instagram")
        previous_cursor = state.get("content_cursor")
        mark_sync_started(account_id, "instagram", "content")
        account = binding = token = None
        try:
            account, binding, token = self._validate_local(account_id)
            page_token = self.page_token_resolver(account_id, binding["page_id"], token["access_token"], self.transport)
            items, _ = self._read_bounded(binding["instagram_user_id"], page_token, max_results)
            reels = self._reels(items)
            newest = str(items[0].get("id")) if items and items[0].get("id") else previous_cursor
            if mode == "incremental" and previous_cursor:
                for index, item in enumerate(items):
                    if str(item.get("id")) == str(previous_cursor):
                        reels = self._reels(items[:index])
                        break
            existing = {
                task.get("platform_video_id") for task in get_publish_tasks()
                if str(task.get("platform") or "").lower() == "instagram"
                and task.get("account_id") == account_id and task.get("platform_video_id")
            }
            imported, refreshed = [], []
            for item in reels:
                media_id = str(item.get("id") or "")
                permalink = item.get("permalink")
                if not media_id or not permalink:
                    continue
                asset_id = f"instagram_{account_id}_{media_id}"
                create_video_asset({
                    "asset_id": asset_id, "video_id": media_id,
                    "source_provider": "instagram", "storage_type": "external",
                    "asset_url": permalink, "location": permalink, "status": "published",
                    "metadata": {"account_id": account_id, "instagram_user_id": binding["instagram_user_id"],
                                  "caption": item.get("caption"), "timestamp": item.get("timestamp"),
                                  "media_type": item.get("media_type"), "media_product_type": item.get("media_product_type"),
                                  "synced_from": "instagram_graph_media"},
                    "source": "instagram",
                })
                if media_id in existing:
                    refreshed.append(media_id)
                    continue
                task = create_publish_task(PublishTask(asset_id=asset_id, video_id=media_id,
                    platform="instagram", account_id=account_id, status="published",
                    title=(item.get("caption") or media_id)[:200], privacy_status="public"))
                update_publish_status(task["id"], "published", platform_video_id=media_id, published_url=permalink)
                existing.add(media_id)
                imported.append(media_id)
            sync_state = mark_sync_success(account_id, "instagram", "content", cursor=newest)
            return {"platform": "instagram", "account_id": account_id, "sync_mode": mode,
                    "tracking_window": max_results, "found": len(items), "reels": len(reels),
                    "imported": len(imported), "refreshed": len(refreshed),
                    "skipped": len(items) - len(reels), "previous_cursor": previous_cursor,
                    "content_cursor": newest, "sync_state": sync_state}
        except Exception as exc:
            safe = self._safe_error(exc, [token.get("access_token")] if token else [])
            mark_sync_failure(account_id, "instagram", "content", safe)
            raise RuntimeError(safe) from None
