import os
import random
import time

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
import httplib2

from integrations.google_transport import build_authorized_httplib2


RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_UPLOAD_RETRIES = 5


def _safe_upload_error(error, status=None):
    """Return a non-sensitive upload diagnostic suitable for persistence."""
    if status is None:
        status = getattr(getattr(error, "resp", None), "status", None)
    errno = getattr(error, "winerror", None) or getattr(error, "errno", None)
    if isinstance(error, HttpError):
        category = "http_error"
    elif isinstance(error, (TimeoutError,)):
        category = "timeout"
    elif isinstance(error, OSError):
        category = "os_error"
    elif isinstance(error, httplib2.HttpLib2Error):
        category = "httplib2_error"
    else:
        category = "transport_error"
    parts = [f"network_error={category}"]
    if status is not None:
        parts.append(f"status={status}")
    if errno is not None:
        parts.append(f"errno={errno}")
    return "; ".join(parts)


class YouTubeAPIClient:
    def __init__(self):
        self.status = "initialized"
        self.credentials = None
        self.service = None

    def initialize(self, credentials=None):
        self.credentials = credentials
        if not self.credentials:
            self.service = None
            self.status = "not_configured"
            return {"platform": "youtube", "status": self.status}

        http = build_authorized_httplib2(self.credentials)
        self.service = build(
            "youtube",
            "v3",
            http=http,
            cache_discovery=False,
        )
        self.status = "ready"
        return {"platform": "youtube", "status": "ready"}

    @staticmethod
    def _validate_video_path(video_path):
        if not video_path:
            raise ValueError("video_path is required")
        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"video file not found: {video_path}")
        if os.path.getsize(video_path) <= 0:
            raise ValueError("video file is empty")

    @staticmethod
    def _backoff_seconds(retry_number):
        return min(30.0, (2 ** retry_number) + random.random())

    def upload_video(
        self,
        video_path,
        title,
        description,
        tags=None,
        privacy_status="private",
    ):
        if not self.service:
            return {
                "platform": "youtube",
                "status": "failed",
                "error": "YouTube API client is not configured",
            }

        try:
            self._validate_video_path(video_path)
            snippet = {
                "title": title,
                "description": description or "",
            }
            if tags:
                snippet["tags"] = list(tags)

            media = MediaFileUpload(video_path, resumable=True)
            request = self.service.videos().insert(
                part="snippet,status",
                body={
                    "snippet": snippet,
                    "status": {"privacyStatus": privacy_status or "private"},
                },
                media_body=media,
            )

            response = None
            retry_count = 0
            last_diagnostic = None
            while response is None:
                try:
                    _, response = request.next_chunk()
                    retry_count = 0
                except HttpError as error:
                    status_code = getattr(error.resp, "status", None)
                    last_diagnostic = _safe_upload_error(error, status_code)
                    if status_code not in RETRIABLE_STATUS_CODES:
                        raise
                    retry_count += 1
                    if retry_count > MAX_UPLOAD_RETRIES:
                        raise RuntimeError(
                            "YouTube resumable upload exceeded retry limit: "
                            f"{last_diagnostic}"
                        ) from error
                    time.sleep(self._backoff_seconds(retry_count))
                except (httplib2.HttpLib2Error, OSError) as error:
                    last_diagnostic = _safe_upload_error(error)
                    retry_count += 1
                    if retry_count > MAX_UPLOAD_RETRIES:
                        raise RuntimeError(
                            "YouTube resumable upload exceeded retry limit: "
                            f"{last_diagnostic}"
                        ) from error
                    time.sleep(self._backoff_seconds(retry_count))

            video_id = response.get("id") if isinstance(response, dict) else None
            if not video_id:
                raise RuntimeError("YouTube upload completed without a video id")

            return {
                "platform": "youtube",
                "status": "published",
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
        except Exception as error:
            return {
                "platform": "youtube",
                "status": "failed",
                "error": (
                    f"YouTube upload failed: {_safe_upload_error(error)}"
                    if isinstance(error, (HttpError, OSError, httplib2.HttpLib2Error, TimeoutError))
                    else "YouTube upload failed: transport_error"
                ),
            }

    def get_video_status(self, video_id):
        if not self.service:
            return {"video_id": video_id, "status": "not_configured"}
        return {"video_id": video_id, "status": "processing"}

    def delete_video(self, video_id):
        if not self.service:
            return {"status": "not_configured"}
        return {"status": "ready_for_delete"}
