import mimetypes
import os
import random
import time

import requests

from integrations.google_transport import build_authorized_session

UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
CHUNK_SIZE = 8 * 1024 * 1024
RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}
EXPIRED_SESSION_STATUS_CODES = {404, 410}
MAX_UPLOAD_RETRIES = 5


def _safe_upload_error(error, *, stage="upload_chunk", status=None, retries=0):
    response = getattr(error, "response", None)
    status = status if status is not None else getattr(response, "status_code", None)
    errno = getattr(error, "winerror", None) or getattr(error, "errno", None)
    if isinstance(error, requests.Timeout):
        category = "timeout"
    elif isinstance(error, requests.ConnectionError):
        category = "connection"
    elif isinstance(error, requests.HTTPError):
        category = "http"
    else:
        category = "other"
    fields = [f"stage={stage}", f"category={category}", f"retries={retries}"]
    if status is not None:
        fields.append(f"status={int(status)}")
    if errno is not None:
        fields.append(f"errno={int(errno)}")
    return "; ".join(fields)


class YouTubeAPIClient:
    def __init__(self):
        self.status = "initialized"
        self.credentials = None
        self.session = None

    def initialize(self, credentials=None):
        self.credentials = credentials
        if not credentials:
            self.session = None
            self.status = "not_configured"
            return {"platform": "youtube", "status": self.status}
        self.session = build_authorized_session(credentials)
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

    @staticmethod
    def _next_offset(response, fallback):
        value = response.headers.get("Range", "")
        return int(value.rsplit("-", 1)[-1]) + 1 if "-" in value else fallback

    def _failure(self, error, stage, retries=0, status=None):
        return {"platform": "youtube", "status": "failed", "error": "YouTube resumable upload failed: " + _safe_upload_error(error, stage=stage, status=status, retries=retries)}

    def upload_video(self, video_path, title, description, tags=None, privacy_status="private"):
        if not self.session:
            return {"platform": "youtube", "status": "failed", "error": "YouTube API client is not configured"}
        try:
            self._validate_video_path(video_path)
            total = os.path.getsize(video_path)
            mime = mimetypes.guess_type(video_path)[0] or "application/octet-stream"
            snippet = {"title": title, "description": description or ""}
            if tags:
                snippet["tags"] = list(tags)
            try:
                init = self.session.post(UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"}, json={"snippet": snippet, "status": {"privacyStatus": privacy_status or "private"}}, headers={"Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Length": str(total), "X-Upload-Content-Type": mime}, timeout=30)
                init.raise_for_status()
            except requests.RequestException as error:
                return self._failure(error, "initialize")
            session_url = init.headers.get("Location")
            if not session_url:
                return self._failure(RuntimeError(), "initialize")
            offset = retries = 0
            with open(video_path, "rb") as media:
                while offset < total:
                    media.seek(offset)
                    chunk = media.read(CHUNK_SIZE)
                    end = offset + len(chunk) - 1
                    try:
                        result = self.session.put(session_url, data=chunk, headers={"Content-Length": str(len(chunk)), "Content-Range": f"bytes {offset}-{end}/{total}", "Content-Type": mime}, timeout=60)
                        if result.status_code == 308:
                            offset = self._next_offset(result, end + 1)
                            retries = 0
                            continue
                        if result.status_code in EXPIRED_SESSION_STATUS_CODES:
                            return {"platform": "youtube", "status": "failed", "error": f"YouTube resumable upload failed: stage=upload_chunk; category=upload_session_expired; retries={retries}; status={result.status_code}"}
                        result.raise_for_status()
                        video_id = (result.json() or {}).get("id")
                        if not video_id:
                            return {"platform": "youtube", "status": "failed", "error": "YouTube upload completed without a video id"}
                        return {"platform": "youtube", "status": "published", "video_id": video_id, "url": f"https://www.youtube.com/watch?v={video_id}"}
                    except requests.HTTPError as error:
                        status = getattr(error.response, "status_code", None)
                        if status not in RETRIABLE_STATUS_CODES:
                            return self._failure(error, "upload_chunk", retries, status)
                    except (requests.Timeout, requests.ConnectionError) as error:
                        try:
                            probe = self.session.put(session_url, data=b"", headers={"Content-Length": "0", "Content-Range": f"bytes */{total}"}, timeout=30)
                            if probe.status_code in EXPIRED_SESSION_STATUS_CODES:
                                return {"platform": "youtube", "status": "failed", "error": f"YouTube resumable upload failed: stage=resume_probe; category=upload_session_expired; retries={retries}; status={probe.status_code}"}
                            if probe.status_code == 308:
                                offset = self._next_offset(probe, offset)
                            else:
                                probe.raise_for_status()
                        except requests.RequestException as probe_error:
                            error = probe_error
                    retries += 1
                    if retries > MAX_UPLOAD_RETRIES:
                        return self._failure(error, "upload_chunk", retries)
                    time.sleep(self._backoff_seconds(retries))
            return {"platform": "youtube", "status": "failed", "error": "YouTube upload completed without a video id"}
        except Exception:
            return self._failure(RuntimeError(), "initialize")

    def get_video_status(self, video_id):
        return {"video_id": video_id, "status": "processing" if self.session else "not_configured"}

    def delete_video(self, video_id):
        return {"status": "ready_for_delete" if self.session else "not_configured"}
