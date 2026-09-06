import requests

from assets.manager import create_video_asset
from data.growth import get_intent_events, record_intent
from data.models import IntentEvent
from integrations.google_transport import build_authorized_session
from oauth.manager import get_token, update_token
from oauth.providers.youtube import YouTubeOAuthProvider
from publish.manager import create_publish_task, get_publish_tasks, update_publish_status
from publish.models import PublishTask


NETWORK_TIMEOUT_ERRNOS = {60, 110, 10060}


class YouTubeDataAPIRequestsClient:
    """Minimal official YouTube Data API v3 client using requests transport.

    Remote Pay Guide OS owns its proxy preference, so this client applies that
    proxy directly to a Google-authorized requests session instead of relying
    on library-specific proxy discovery.
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

    def comment_threads_list(self, **params):
        return self._get("commentThreads", params)


class YouTubeContentSync:
    """Import existing YouTube content and audience feedback into the OS.

    This does not publish, download, back up, or modify anything on YouTube.
    It reads metadata and top-level comments from the official YouTube Data API
    and stores only external asset records plus Data Center intent signals.
    """

    def __init__(self, service=None):
        self.service = service

    @staticmethod
    def _execute(request):
        try:
            return request.execute(num_retries=2)
        except TypeError:
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

    def _comment_threads(self, service, video_id, max_results):
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": min(100, max_results),
            "order": "time",
            "textFormat": "plainText",
        }
        try:
            if isinstance(service, YouTubeDataAPIRequestsClient):
                response = service.comment_threads_list(**params)
            else:
                response = self._execute(service.commentThreads().list(**params))
        except RuntimeError as exc:
            message = str(exc).lower()
            if "commentsdisabled" in message or "disabled comments" in message or "comments are disabled" in message:
                return []
            raise
        return (response.get("items") or [])[:max_results]

    @staticmethod
    def _comment_payload(thread):
        top = thread.get("snippet", {}).get("topLevelComment", {})
        snippet = top.get("snippet", {})
        comment_id = top.get("id") or thread.get("id")
        text = snippet.get("textOriginal") or snippet.get("textDisplay") or ""
        return {
            "comment_id": comment_id,
            "text": str(text).strip(),
            "like_count": int(snippet.get("likeCount") or 0),
            "reply_count": int(thread.get("snippet", {}).get("totalReplyCount") or 0),
            "published_at": snippet.get("publishedAt"),
            "updated_at": snippet.get("updatedAt"),
        }

    def _sync_feedback(self, service, video_id, title, max_comments):
        existing_comment_ids = {
            str((event.get("metadata") or {}).get("comment_id"))
            for event in get_intent_events(video_id)
            if event.get("source") == "youtube_comment"
            and (event.get("metadata") or {}).get("comment_id")
        }

        imported = 0
        existing = 0
        samples = []
        for thread in self._comment_threads(service, video_id, max_comments):
            payload = self._comment_payload(thread)
            comment_id = payload.get("comment_id")
            text = payload.get("text") or ""
            if not comment_id or not text:
                continue

            samples.append(text[:500])
            if str(comment_id) in existing_comment_ids:
                existing += 1
                continue

            record_intent(
                IntentEvent(
                    content_id=video_id,
                    video_id=video_id,
                    source="youtube_comment",
                    event_type="content_feedback",
                    event_value={"text": text},
                    metadata={
                        "platform": "youtube",
                        "comment_id": comment_id,
                        "video_title": title,
                        "like_count": payload.get("like_count", 0),
                        "reply_count": payload.get("reply_count", 0),
                        "updated_at": payload.get("updated_at"),
                        "synced_from": "youtube_data_api_v3_commentThreads",
                    },
                    occurred_at=payload.get("published_at"),
                )
            )
            imported += 1
            existing_comment_ids.add(str(comment_id))

        return {
            "found": imported + existing,
            "imported": imported,
            "already_present": existing,
            "samples": samples[:5],
        }

    def sync(self, account_id, max_results=50, max_comments_per_video=20):
        max_results = max(1, min(int(max_results or 50), 200))
        max_comments_per_video = max(0, min(int(max_comments_per_video or 0), 100))
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
        feedback_found = 0
        feedback_imported = 0
        feedback_existing = 0
        feedback_samples = []

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
            else:
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

            if max_comments_per_video > 0:
                feedback = self._sync_feedback(
                    service,
                    video_id,
                    title,
                    max_comments=max_comments_per_video,
                )
                feedback_found += feedback["found"]
                feedback_imported += feedback["imported"]
                feedback_existing += feedback["already_present"]
                feedback_samples.extend(feedback["samples"])

        return {
            "platform": "youtube",
            "account_id": account_id,
            "channel_id": channel.get("channel_id"),
            "channel_title": channel.get("channel_title"),
            "found": len(video_ids),
            "imported": len(imported),
            "already_present": len(existing),
            "imported_video_ids": imported,
            "feedback_found": feedback_found,
            "feedback_imported": feedback_imported,
            "feedback_already_present": feedback_existing,
            "feedback_samples": feedback_samples[:10],
        }
