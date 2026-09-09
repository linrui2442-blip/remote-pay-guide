import os
import random
import time

import mimetypes
import requests

from integrations.google_transport import build_authorized_session


RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_UPLOAD_RETRIES = 5


def _safe_upload_error(error, status=None):
    """Return a non-sensitive upload diagnostic suitable for persistence."""
    if status is None:
        status = getattr(getattr(error, "response", None), "status_code", None) or getattr(getattr(error, "resp", None), "status", None)
    errno = getattr(error, "winerror", None) or getattr(error, "errno", None)
    if isinstance(error, requests.Timeout):
        category = "timeout"
    elif isinstance(error, requests.ConnectionError):
        category = "connection_error"
    elif isinstance(error, requests.HTTPError):
        category = "http_error"
    elif isinstance(error, OSError):
        category = "os_error"
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
        self.session = None

    def initialize(self, credentials=None):
        self.credentials = credentials
        if not self.credentials:
            self.session = None
            self.status = "not_configured"
            return {"platform": "youtube", "status": self.status}

        self.session = build_authorized_session(self.credentials)
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
        if not self.session:
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

            total = os.path.getsize(video_path)
            mime_type = mimetypes.guess_type(video_path)[0] or "application/octet-stream"
            init = self.session.post("https://www.googleapis.com/upload/youtube/v3/videos", params={"uploadType": "resumable", "part": "snippet,status"}, json={"snippet": snippet, "status": {"privacyStatus": privacy_status or "private"}}, headers={"Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Length": str(total), "X-Upload-Content-Type": mime_type}, timeout=30)
            init.raise_for_status()
            session_url = init.headers.get("Location")
            if not session_url:
                raise RuntimeError("YouTube upload initialization returned no session")
            response = None
            offset = 0
            retry_count = 0
            last_diagnostic = None
            while response is None:
                try:
                    with open(video_path, "rb") as media:
                        media.seek(offset)
                        chunk = media.read(8 * 1024 * 1024)
                    end = offset + len(chunk) - 1
                    result = self.session.put(session_url, data=chunk, headers={"Content-Length": str(len(chunk)), "Content-Range": f"bytes {offset}-{end}/{total}", "Content-Type": mime_type}, timeout=60)
                    if result.status_code == 308:
                        range_header = result.headers.get("Range", "")
                        offset = int(range_header.rsplit("-", 1)[-1]) + 1 if "-" in range_header else end + 1
                        continue
                    result.raise_for_status()
                    response = result.json()
                    retry_count = 0
                except requests.HTTPError as error:
                    status_code = getattr(error.response, "status_code", None)
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
                except (requests.Timeout, requests.ConnectionError, OSError) as error:
                    last_diagnostic = _safe_upload_error(error)
                    # Ask the existing session for the committed offset before retrying.
                    try:
                        probe = self.session.put(session_url, data=b"", headers={"Content-Length": "0", "Content-Range": f"bytes */{total}"}, timeout=30)
                        if probe.status_code == 308 and "-" in probe.headers.get("Range", ""):
                            offset = int(probe.headers["Range"].rsplit("-", 1)[-1]) + 1
                    except requests.RequestException:
                        pass
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
                    if isinstance(error, (requests.RequestException, OSError, TimeoutError))
                    else "YouTube upload failed: transport_error"
                ),
            }

    def get_video_status(self, video_id):
        if not self.session:
            return {"video_id": video_id, "status": "not_configured"}
        return {"video_id": video_id, "status": "processing"}

    def delete_video(self, video_id):
        if not self.session:
            return {"status": "not_configured"}
        return {"status": "ready_for_delete"}
