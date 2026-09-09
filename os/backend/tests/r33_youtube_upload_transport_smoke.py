"""Network-free checks for the official YouTube requests upload transport."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import requests

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from integrations import google_transport
from publish.adapters.youtube_api import YouTubeAPIClient, _safe_upload_error

class Response:
    def __init__(self, status=200, headers=None, payload=None):
        self.status_code, self.headers, self.payload = status, headers or {}, payload or {}
    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError("Authorization: Bearer SECRET_TOKEN upload_id=SECRET_UPLOAD")
            error.response = self
            raise error
    def json(self): return self.payload

class Session:
    def __init__(self, puts, init_headers=None):
        self.puts, self.posts, self.calls = list(puts), 0, []
        self.init_headers = {"Location": "https://upload.invalid/?upload_id=SECRET_UPLOAD"} if init_headers is None else init_headers
    def post(self, url, **kwargs):
        self.posts += 1; self.init = (url, kwargs)
        return Response(headers=self.init_headers)
    def put(self, url, **kwargs):
        self.calls.append((url, kwargs)); item = self.puts.pop(0)
        if isinstance(item, Exception): raise item
        return item

def client(session):
    value = YouTubeAPIClient(); value.session = session; return value

def main():
    original = google_transport.get_active_proxy_map
    try:
        google_transport.get_active_proxy_map = lambda: {"https": "http://127.0.0.1:12345"}
        made = google_transport.build_authorized_session(object(), session_factory=lambda _: type("S", (), {"proxies": {}})())
        assert made.proxies["https"].endswith(":12345")
    finally: google_transport.get_active_proxy_map = original
    with TemporaryDirectory() as temp:
        path = Path(temp) / "video.mp4"; path.write_bytes(b"a" * (9 * 1024 * 1024))
        s = Session([Response(308, {"Range": "bytes=0-1048575"}), Response(payload={"id": "test_video_id"})])
        with patch("publish.adapters.youtube_api.time.sleep"):
            result = client(s).upload_video(str(path), "title", "description", ["tag"])
        assert result["video_id"] == "test_video_id" and s.posts == 1
        assert s.init[1]["params"] == {"uploadType": "resumable", "part": "snippet,status"}
        assert s.init[1]["json"]["status"]["privacyStatus"] == "private"
        assert s.calls[1][1]["headers"]["Content-Range"].startswith("bytes 1048576-")
        timeout = requests.Timeout("Authorization: Bearer SECRET_TOKEN access_token=SECRET_ACCESS")
        s = Session([timeout, Response(308, {"Range": "bytes=0-1048575"}), Response(payload={"id": "test_video_id"})])
        with patch("publish.adapters.youtube_api.time.sleep"):
            assert client(s).upload_video(str(path), "t", "d")["status"] == "published"
        assert s.posts == 1 and s.calls[1][1]["headers"]["Content-Range"].startswith("bytes */")
        for completion_status in (200, 201):
            s = Session([timeout, Response(completion_status, payload={"id": "probe_completed_video"})])
            with patch("publish.adapters.youtube_api.time.sleep"):
                probe_result = client(s).upload_video(str(path), "t", "d")
            assert probe_result["status"] == "published" and probe_result["video_id"] == "probe_completed_video"
            assert s.posts == 1 and len(s.calls) == 2
            assert s.calls[1][1]["headers"]["Content-Range"] == f"bytes */{path.stat().st_size}"
        s = Session([timeout, Response(200, payload={})])
        with patch("publish.adapters.youtube_api.time.sleep"):
            probe_missing_id = client(s).upload_video(str(path), "t", "d")
        assert probe_missing_id["error"] == "YouTube upload completed without a video id"
        assert s.posts == 1 and len(s.calls) == 2
        for status in (400, 401, 403, 404, 410):
            s = Session([Response(status)])
            error = client(s).upload_video(str(path), "t", "d")["error"]
            assert s.posts == 1 and len(s.calls) == 1 and "SECRET_UPLOAD" not in error
        for status in (429, 500, 502, 503, 504):
            s = Session([Response(status), Response(payload={"id": "test_video_id"})])
            with patch("publish.adapters.youtube_api.time.sleep"):
                assert client(s).upload_video(str(path), "t", "d")["status"] == "published"
            assert s.posts == 1 and len(s.calls) == 2
            assert all(call[0] == s.calls[0][0] for call in s.calls)
        s = Session([], init_headers={})
        missing_location = client(s).upload_video(str(path), "t", "d")
        assert missing_location["status"] == "failed" and "stage=initialize" in missing_location["error"]
        assert s.posts == 1 and not s.calls
        s = Session([Response(payload={})])
        missing_id = client(s).upload_video(str(path), "t", "d")
        assert missing_id["error"] == "YouTube upload completed without a video id"
        assert s.posts == 1 and len(s.calls) == 1
        safe = _safe_upload_error(timeout, stage="resume_probe", retries=5)
        assert "stage=resume_probe" in safe and "retries=5" in safe
        for secret in ("SECRET_TOKEN", "SECRET_ACCESS", "SECRET_UPLOAD", "upload_id", "https://"):
            assert secret not in safe
    print("YouTube requests resumable transport smoke test passed")

if __name__ == "__main__": main()
