import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests


DEFAULT_CONNECT_TIMEOUT = 5
DEFAULT_READ_TIMEOUT = 30
DEFAULT_MAX_BYTES = 500 * 1024 * 1024
DEFAULT_MAX_REDIRECTS = 3
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm"}


@dataclass
class PreparedPublishAsset:
    file_path: str
    temporary: bool = False

    def cleanup(self):
        if self.temporary and self.file_path:
            try:
                os.remove(self.file_path)
            except FileNotFoundError:
                pass


class AssetResolutionError(RuntimeError):
    pass


class AssetResolver:
    """Prepare an already-registered VideoAsset for a publishing adapter."""

    def __init__(
        self,
        connect_timeout=DEFAULT_CONNECT_TIMEOUT,
        read_timeout=DEFAULT_READ_TIMEOUT,
        max_bytes=DEFAULT_MAX_BYTES,
        max_redirects=DEFAULT_MAX_REDIRECTS,
        session=None,
    ):
        self.timeout = (connect_timeout, read_timeout)
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.session = session or requests.Session()

    @staticmethod
    def _validate_url(url):
        parsed = urlparse(url or "")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise AssetResolutionError("asset_url must be an absolute http/https URL")
        return parsed

    @staticmethod
    def _content_type_allowed(content_type, url):
        media_type = (content_type or "").split(";", 1)[0].strip().lower()
        suffix = Path(urlparse(url).path).suffix.lower()
        if media_type.startswith("video/"):
            return True
        if suffix in VIDEO_SUFFIXES and media_type in {"", "application/octet-stream"}:
            return True
        return False

    def _request_with_redirect_limit(self, url):
        current_url = url
        for redirect_count in range(self.max_redirects + 1):
            self._validate_url(current_url)
            response = self.session.get(
                current_url,
                stream=True,
                timeout=self.timeout,
                allow_redirects=False,
                headers={"User-Agent": "RemotePayGuideOS-PublishWorker/1.0"},
            )
            if response.status_code in {301, 302, 303, 307, 308}:
                if redirect_count >= self.max_redirects:
                    response.close()
                    raise AssetResolutionError("asset download exceeded redirect limit")
                location = response.headers.get("Location")
                response.close()
                if not location:
                    raise AssetResolutionError("asset redirect missing Location header")
                current_url = urljoin(current_url, location)
                continue
            return response, current_url
        raise AssetResolutionError("asset download exceeded redirect limit")

    def _download_registered_url(self, asset, url):
        if not asset.get("asset_id"):
            raise AssetResolutionError("remote download requires a registered asset_id")

        response = None
        temp_path = None
        try:
            response, final_url = self._request_with_redirect_limit(url)
            if response.status_code != 200:
                raise AssetResolutionError(
                    f"asset download returned HTTP {response.status_code}"
                )

            content_type = response.headers.get("Content-Type", "")
            if not self._content_type_allowed(content_type, final_url):
                raise AssetResolutionError(
                    f"asset download rejected Content-Type: {content_type or 'missing'}"
                )

            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    declared_size = int(content_length)
                except ValueError:
                    declared_size = None
                if declared_size is not None:
                    if declared_size <= 0:
                        raise AssetResolutionError("asset download is empty")
                    if declared_size > self.max_bytes:
                        raise AssetResolutionError("asset download exceeds maximum size")

            suffix = Path(urlparse(final_url).path).suffix.lower()
            if suffix not in VIDEO_SUFFIXES:
                suffix = ".mp4"

            with tempfile.NamedTemporaryFile(
                prefix="remote-pay-guide-publish-",
                suffix=suffix,
                delete=False,
            ) as handle:
                temp_path = handle.name
                total = 0
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > self.max_bytes:
                        raise AssetResolutionError("asset download exceeds maximum size")
                    handle.write(chunk)

            if os.path.getsize(temp_path) <= 0:
                raise AssetResolutionError("asset download is empty")

            return PreparedPublishAsset(file_path=temp_path, temporary=True)
        except requests.RequestException as exc:
            raise AssetResolutionError(f"asset download failed: {exc}") from exc
        except Exception:
            if temp_path:
                try:
                    os.remove(temp_path)
                except FileNotFoundError:
                    pass
            raise
        finally:
            if response is not None:
                response.close()

    def prepare(self, asset):
        if not isinstance(asset, dict):
            raise AssetResolutionError("VideoAsset record is required")

        file_path = asset.get("file_path")
        if file_path:
            path = Path(file_path)
            if path.is_file() and path.stat().st_size > 0:
                return PreparedPublishAsset(file_path=str(path), temporary=False)

        asset_url = asset.get("asset_url")
        if not asset_url:
            location = asset.get("location")
            if isinstance(location, str) and location.startswith(("http://", "https://")):
                asset_url = location

        if not asset_url:
            raise AssetResolutionError("VideoAsset has no usable file_path or asset_url")

        return self._download_registered_url(asset, asset_url)
