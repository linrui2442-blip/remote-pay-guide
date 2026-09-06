import requests

from assets.manager import create_video_asset
from data.sync_state import (
    get_sync_state,
    mark_sync_failure,
    mark_sync_started,
    mark_sync_success,
)
from integrations.google_transport import build_authorized_session
from oauth.manager import get_token, update_token
from oauth.providers.youtube import YouTubeOAuthProvider
from publish.manager import create_publish_task, get_publish_tasks, update_publish_status
from publish.models import PublishTask


NETWORK_TIMEOUT_ERRNOS = {60, 110, 10060}
SYNC_MODES = {"incremental", "full_refresh"}


class YouTubeDataAPIRequestsClient:
    """Minimal official YouTube Data API v3 client using requests transport.

    googleapiclient uses httplib2 internally, whose proxy behavior can differ
    from requests on Windows. Remote Pay Guide OS owns its proxy preference,
    so this client applies that proxy directly to a Google-authorized requests
    session instead of relying on library-specific environment discovery.
    """

    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self, credentials, session=None):
        self.session = session or build_authorized_session(credentials)

    @staticmethod
    def _error_detail(response):
        try:
            payload = response.json()
            message = payload.get("error", {}).get("message")
            if message:
                return message
        except Exception:
            pass
        return response.text[:300] if getattr(response, "text", None) else "unknown Google API error"

    def _get(self, resource, params):
        url = f"{self.BASE_URL}/{resource}"
        try:
            response = self.session.get(url, params=params, timeout=(10, 30))
            response.raise_for_status()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            raise RuntimeError(
                "Google YouTube API network/proxy request failed. Remote Pay Guide OS "
                "could not reach www.googleapis.com through the configured route. Check "
                "System Settings -> Proxy and confirm the local HTTP/Mixed proxy port is running."
            ) from exc
        except requests.exceptions.RequestException as exc:
            response = getattr(exc, "response", None)
            if response is not None:
                raise RuntimeError(
                    f"Google YouTube API request failed ({response.status_code}): "
                    f"{self._error_detail(response)}"
                ) from exc
            raise RuntimeError(f"Google YouTube API request failed: {exc}") from exc
        return response.json()

    def channels_list(self, **params):
        return self._get("channels", params)

    def playlist_items_list(self, **params):
        return self._get("playlistItems", params)

    def videos_list(self, **params):
        return self._get("videos", params)


class YouTubeContentSync:
    """Import existing videos from an authorized YouTube account into the OS.

    This does not publish, download, back up, or modify anything on YouTube. It
    only reads metadata from the official API and creates local external Video
    Asset / Publish Center records so existing videos can enter the Analytics
    -> Data Center loop. The default window is the latest 10 published videos;
    older records already known to the OS are retained locally as history.

    Incremental mode stores the newest observed platform video id as the account
    checkpoint. A later sync only hydrates items that appeared before that
    checkpoint inside the active tracking window. Full refresh remains available
    for repair/reconciliation without changing the active-window policy.
    """

    def __init__(self, service=None):
        self.service = service

    @staticmethod
    def _execute(request):
        try:
            return request.execute(num_retries=2)
        except TypeError:
            # Test doubles and a few lightweight request wrappers do not expose
            # googleapiclient's optional num_retries argument.
            return request.execute()
        except OSError as exc:
            error_code = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
            if error_code in NETWORK_TIMEOUT_ERRNOS:
                raise RuntimeError(
                    "Google YouTube API network timeout. The OS backend could not reach "
                    "www.googleapis.com through its configured network route."
                ) from exc
            raise

    def _service(self, account_id):
        if self.service is not None:
            return self.service

        token = get_token(account_id)
        if not token:
            raise RuntimeError(f"YouTube OAuth credential not found for account_id {account_id}")

        provider = YouTubeOAuthProvider(scope_profile="full")
        valid_token, refreshed = provider.ensure_valid_token(token)
        if refreshed:
            update_token(account_id, {"provider": "youtube", **valid_token})

        credentials = provider.build_google_credentials(valid_token)
        self.service = YouTubeDataAPIRequestsClient(credentials)
        return self.service

    @staticmethod
    def _video_url(video_id):
        return f"https://www.youtube.com/watch?v={video_id}"

    @staticmethod
    def _playlist_video_id(item):
        snippet = item.get("snippet", {})
        return (
            item.get("contentDetails", {}).get("videoId")
            or snippet.get("resourceId", {}).get("videoId")
        )

    def _channel(self, service):
        if isinstance(service, YouTubeDataAPIRequestsClient):
            response = service.channels_list(
                part="snippet,contentDetails",
                mine="true",
            )
        else:
            response = self._execute(
                service.channels().list(
                    part="snippet,contentDetails",
                    mine=True,
                )
            )
        items = response.get("items") or []
        if not items:
            raise RuntimeError("No YouTube channel was returned for the authorized account")
        channel = items[0]
        uploads = (
            channel.get("contentDetails", {})
            .get("relatedPlaylists", {})
            .get("uploads")
        )
        if not uploads:
            raise RuntimeError("Authorized YouTube channel has no uploads playlist")
        return {
            "channel_id": channel.get("id"),
            "channel_title": channel.get("snippet", {}).get("title"),
            "uploads_playlist_id": uploads,
        }

    def _playlist_items(self, service, playlist_id, max_results):
        items = []
        page_token = None
        while len(items) < max_results:
            params = {
                "part": "snippet,contentDetails",
                "playlistId": playlist_id,
                "maxResults": min(50, max_results - len(items)),
            }
            if page_token:
                params["pageToken"] = page_token

            if isinstance(service, YouTubeDataAPIRequestsClient):
                response = service.playlist_items_list(**params)
            else:
                response = self._execute(service.playlistItems().list(**params))

            items.extend(response.get("items") or [])
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return items[:max_results]

    def _video_details(self, service, video_ids):
        details = {}
        for index in range(0, len(video_ids), 50):
            batch = video_ids[index:index + 50]
            if not batch:
                continue
            params = {
                "part": "snippet,status",
                "id": ",".join(batch),
            }
            if isinstance(service, YouTubeDataAPIRequestsClient):
                response = service.videos_list(**params)
            else:
                response = self._execute(service.videos().list(**params))
            for item in response.get("items") or []:
                details[item.get("id")] = item
        return details

    @staticmethod
    def _items_after_checkpoint(playlist_items, previous_cursor, sync_mode):
        if sync_mode == "full_refresh" or not previous_cursor:
            return playlist_items

        for index, item in enumerate(playlist_items):
            if YouTubeContentSync._playlist_video_id(item) == previous_cursor:
                return playlist_items[:index]

        # The checkpoint fell outside the bounded active window. Reconcile the
        # entire current window rather than assuming continuity we cannot prove.
        return playlist_items

    def sync(self, account_id, max_results=10, sync_mode="incremental"):
        max_results = max(1, min(int(max_results or 10), 200))
        normalized_mode = str(sync_mode or "incremental").strip().lower()
        if normalized_mode not in SYNC_MODES:
            raise ValueError(f"unsupported content sync mode: {sync_mode}")

        platform = "youtube"
        state = get_sync_state(account_id, platform)
        previous_cursor = state.get("content_cursor")
        mark_sync_started(account_id, platform, "content")

        try:
            service = self._service(account_id)
            channel = self._channel(service)
            playlist_items = self._playlist_items(
                service,
                channel["uploads_playlist_id"],
                max_results,
            )

            video_ids = [
                self._playlist_video_id(item)
                for item in playlist_items
            ]
            video_ids = [video_id for video_id in video_ids if video_id]
            new_cursor = video_ids[0] if video_ids else previous_cursor

            existing_tasks = {
                task.get("platform_video_id")
                for task in get_publish_tasks()
                if str(task.get("platform") or "").lower() == platform
                and task.get("account_id") == account_id
                and task.get("platform_video_id")
            }
            already_present = len(
                [video_id for video_id in video_ids if video_id in existing_tasks]
            )

            items_to_process = self._items_after_checkpoint(
                playlist_items,
                previous_cursor,
                normalized_mode,
            )
            process_video_ids = [
                self._playlist_video_id(item)
                for item in items_to_process
            ]
            process_video_ids = [video_id for video_id in process_video_ids if video_id]
            details = self._video_details(service, process_video_ids)

            imported = []
            refreshed = []
            for item in items_to_process:
                snippet = item.get("snippet", {})
                video_id = self._playlist_video_id(item)
                if not video_id:
                    continue

                detail = details.get(video_id, {})
                detail_snippet = detail.get("snippet", {})
                status = detail.get("status", {})
                title = detail_snippet.get("title") or snippet.get("title") or video_id
                published_at = detail_snippet.get("publishedAt") or snippet.get("publishedAt")
                privacy = status.get("privacyStatus") or "private"
                if privacy not in {"private", "unlisted", "public"}:
                    privacy = "private"

                asset_id = f"youtube_{account_id}_{video_id}"
                url = self._video_url(video_id)
                create_video_asset(
                    {
                        "asset_id": asset_id,
                        "video_id": video_id,
                        "source_provider": "youtube",
                        "storage_type": "external",
                        "asset_url": url,
                        "status": "published",
                        "metadata": {
                            "account_id": account_id,
                            "channel_id": channel.get("channel_id"),
                            "channel_title": channel.get("channel_title"),
                            "title": title,
                            "published_at": published_at,
                            "privacy_status": privacy,
                            "synced_from": "youtube_data_api_v3",
                        },
                        "source": "youtube",
                        "location": url,
                    }
                )

                if video_id in existing_tasks:
                    refreshed.append(video_id)
                    continue

                task = create_publish_task(
                    PublishTask(
                        asset_id=asset_id,
                        video_id=video_id,
                        platform=platform,
                        account_id=account_id,
                        status="published",
                        title=title,
                        privacy_status=privacy,
                    )
                )
                update_publish_status(
                    task["id"],
                    "published",
                    platform_video_id=video_id,
                    published_url=url,
                )
                imported.append(video_id)
                existing_tasks.add(video_id)

            sync_state = mark_sync_success(
                account_id,
                platform,
                "content",
                cursor=new_cursor,
            )
            return {
                "platform": platform,
                "account_id": account_id,
                "channel_id": channel.get("channel_id"),
                "channel_title": channel.get("channel_title"),
                "tracking_window": max_results,
                "sync_mode": normalized_mode,
                "previous_cursor": previous_cursor,
                "content_cursor": new_cursor,
                "found": len(video_ids),
                "processed": len(process_video_ids),
                "imported": len(imported),
                "already_present": already_present,
                "refreshed": len(refreshed),
                "unchanged": max(0, len(video_ids) - len(process_video_ids)),
                "imported_video_ids": imported,
                "sync_state": sync_state,
            }
        except Exception as exc:
            mark_sync_failure(account_id, platform, "content", exc)
            raise
