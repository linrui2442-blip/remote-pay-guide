from googleapiclient.discovery import build

from assets.manager import create_video_asset
from oauth.manager import get_token, update_token
from oauth.providers.youtube import YouTubeOAuthProvider
from publish.manager import create_publish_task, get_publish_tasks, update_publish_status
from publish.models import PublishTask


NETWORK_TIMEOUT_ERRNOS = {60, 110, 10060}


class YouTubeContentSync:
    """Import existing videos from an authorized YouTube account into the OS.

    This does not publish or modify anything on YouTube. It only reads the
    channel uploads playlist and creates local Video Asset / Publish Center
    records so existing videos can enter the Analytics -> Data Center loop.
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
                    "www.googleapis.com. If Google works in the browser through a VPN/proxy, "
                    "the backend process must use the same proxy/VPN route."
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
        self.service = build(
            "youtube",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )
        return self.service

    @staticmethod
    def _video_url(video_id):
        return f"https://www.youtube.com/watch?v={video_id}"

    def _channel(self, service):
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
            response = self._execute(
                service.playlistItems().list(
                    part="snippet,contentDetails",
                    playlistId=playlist_id,
                    maxResults=min(50, max_results - len(items)),
                    pageToken=page_token,
                )
            )
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
            response = self._execute(
                service.videos().list(
                    part="snippet,status",
                    id=",".join(batch),
                )
            )
            for item in response.get("items") or []:
                details[item.get("id")] = item
        return details

    def sync(self, account_id, max_results=50):
        max_results = max(1, min(int(max_results or 50), 200))
        service = self._service(account_id)
        channel = self._channel(service)
        playlist_items = self._playlist_items(
            service,
            channel["uploads_playlist_id"],
            max_results,
        )

        video_ids = [
            item.get("contentDetails", {}).get("videoId")
            or item.get("snippet", {}).get("resourceId", {}).get("videoId")
            for item in playlist_items
        ]
        video_ids = [video_id for video_id in video_ids if video_id]
        details = self._video_details(service, video_ids)

        existing_tasks = {
            task.get("platform_video_id")
            for task in get_publish_tasks()
            if str(task.get("platform") or "").lower() == "youtube"
            and task.get("account_id") == account_id
            and task.get("platform_video_id")
        }

        imported = []
        existing = []
        for item in playlist_items:
            snippet = item.get("snippet", {})
            video_id = (
                item.get("contentDetails", {}).get("videoId")
                or snippet.get("resourceId", {}).get("videoId")
            )
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
                existing.append(video_id)
                continue

            task = create_publish_task(
                PublishTask(
                    asset_id=asset_id,
                    video_id=video_id,
                    platform="youtube",
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

        return {
            "platform": "youtube",
            "account_id": account_id,
            "channel_id": channel.get("channel_id"),
            "channel_title": channel.get("channel_title"),
            "found": len(video_ids),
            "imported": len(imported),
            "already_present": len(existing),
            "imported_video_ids": imported,
        }
