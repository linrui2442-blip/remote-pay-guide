"""Read-only, DNS-pinned remote media inspection. No publishing dependencies."""
from contextlib import contextmanager
from dataclasses import dataclass
import http.client
import ipaddress
import json
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tempfile
import time
from urllib.parse import urljoin, urlsplit

MIN_BYTES = 32 * 1024
MAX_BYTES = 500 * 1024 * 1024
MAX_REDIRECTS = 3
MAX_DOWNLOAD_SECONDS = 600
VIDEO_SUFFIXES = {'.mp4', '.mov', '.m4v', '.webm'}


class MediaFailure(ValueError):
    def __init__(self, decision, reason):
        super().__init__(reason)  # Only server-owned codes, never URLs/headers.
        self.decision = decision
        self.reason = reason


def validate_url(url, resolver=socket.getaddrinfo):
    if not isinstance(url, str) or not url:
        raise MediaFailure('BLOCK', 'MISSING_ASSET_URL')
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower().rstrip('.')
        if (parsed.scheme != 'https' or not host or parsed.username is not None
                or parsed.password is not None or parsed.port not in (None, 443)
                or parsed.fragment or '\\' in url or any(ord(c) <= 32 or ord(c) == 127 for c in url)
                or host == 'localhost' or host.endswith(('.localhost', '.local', '.internal'))
                or '%' in host):
            raise ValueError()
        host = host.encode('idna').decode('ascii')
    except (ValueError, UnicodeError):
        raise MediaFailure('BLOCK', 'UNSAFE_ASSET_URL') from None
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        addresses = [str(literal)]
    else:
        try:
            addresses = list({answer[4][0] for answer in resolver(host, 443, type=socket.SOCK_STREAM)})
        except (OSError, ValueError):
            raise MediaFailure('REVIEW', 'DNS_UNAVAILABLE') from None
    if not addresses:
        raise MediaFailure('REVIEW', 'DNS_UNAVAILABLE')
    try:
        if any(not ipaddress.ip_address(ip).is_global or ipaddress.ip_address(ip).is_multicast
               or ipaddress.ip_address(ip).is_reserved for ip in addresses):
            raise ValueError()
    except ValueError:
        raise MediaFailure('BLOCK', 'NON_PUBLIC_ADDRESS') from None
    return host, addresses


class _PinnedConnection(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host, 443, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        # Do not resolve the hostname a second time: prevent DNS rebinding.
        ip = ipaddress.ip_address(self.address)
        sock = socket.socket(socket.AF_INET6 if ip.version == 6 else socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(self.timeout)
            sock.connect((self.address, 443))
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


class _Response:
    def __init__(self, conn, response):
        self.conn, self.response = conn, response
        self.status_code = response.status
        self.headers = {k.lower(): v for k, v in response.getheaders()}

    def iter_content(self, chunk_size):
        while True:
            chunk = self.response.read(chunk_size)
            if not chunk:
                break
            yield chunk

    def close(self):
        self.response.close()
        self.conn.close()


class PinnedSession:
    """GET only. No cookies, credentials, proxies, redirects or decompression."""
    def get(self, url, *, host, addresses, timeout, allow_redirects=False):
        if allow_redirects:
            raise ValueError('automatic redirects forbidden')
        conn = _PinnedConnection(host, addresses[0], timeout[0])
        try:
            parsed = urlsplit(url)
            target = parsed.path or '/'
            if parsed.query:
                target += '?' + parsed.query
            conn.connect()
            conn.sock.settimeout(timeout[1])
            conn.request('GET', target, headers={'Accept-Encoding': 'identity',
                                               'User-Agent': 'RemotePayGuideOS-Quality/1.0'})
            return _Response(conn, conn.getresponse())
        except BaseException:
            conn.close()
            raise


@dataclass
class DownloadedMedia:
    path: Path
    content_type: str
    size: int
    host: str


class RemoteMedia:
    def __init__(self, *, session=None, resolver=socket.getaddrinfo):
        self.session = session or PinnedSession()
        self.resolver = resolver

    @contextmanager
    def download(self, url, *, storage_type):
        response = None
        try:
            current = url
            for hop in range(MAX_REDIRECTS + 1):
                host, addresses = validate_url(current, self.resolver)
                response = self.session.get(current, host=host, addresses=addresses,
                                            timeout=(5, 30), allow_redirects=False)
                headers = {k.lower(): v for k, v in response.headers.items()}
                if response.status_code in (301, 302, 303, 307, 308):
                    location = headers.get('location')
                    response.close()
                    response = None
                    if hop == MAX_REDIRECTS or not location:
                        raise MediaFailure('BLOCK', 'REDIRECT_LIMIT_OR_MISSING_LOCATION')
                    # Validate before urljoin can strip embedded control chars.
                    if '\\' in location or any(ord(c) <= 32 or ord(c) == 127 for c in location):
                        raise MediaFailure('BLOCK', 'UNSAFE_REDIRECT')
                    current = urljoin(current, location)
                    continue
                break
            status = response.status_code
            if status >= 500 or status in (408, 429):
                raise MediaFailure('REVIEW', 'REMOTE_TEMPORARILY_UNAVAILABLE')
            if status != 200:
                raise MediaFailure('BLOCK', 'REMOTE_HTTP_REJECTED')
            mime = headers.get('content-type', '').split(';', 1)[0].strip().lower()
            suffix = Path(urlsplit(current).path).suffix.lower()
            if not (mime.startswith('video/') or (mime == 'application/octet-stream'
                    and storage_type == 'github_pages' and suffix in VIDEO_SUFFIXES)):
                raise MediaFailure('BLOCK', 'CONTENT_TYPE_REJECTED')
            if headers.get('content-encoding', 'identity').lower() not in ('', 'identity'):
                raise MediaFailure('BLOCK', 'ENCODED_BODY_REJECTED')
            declared = headers.get('content-length')
            if declared is not None:
                try:
                    declared = int(declared)
                except (ValueError, TypeError):
                    raise MediaFailure('BLOCK', 'INVALID_CONTENT_LENGTH') from None
                if declared < MIN_BYTES:
                    raise MediaFailure('BLOCK', 'MEDIA_TOO_SMALL')
                if declared > MAX_BYTES:
                    raise MediaFailure('BLOCK', 'MEDIA_TOO_LARGE')
            # Reject a TEMP configuration pointing inside the repository.
            repo = Path(__file__).resolve().parents[3]
            if Path(tempfile.gettempdir()).resolve().is_relative_to(repo):
                raise MediaFailure('REVIEW', 'EXTERNAL_TEMP_REQUIRED')
            with tempfile.TemporaryDirectory(prefix='rpg-quality-') as folder:
                path = Path(folder) / ('media' + (suffix if suffix in VIDEO_SUFFIXES else '.bin'))
                total, started = 0, time.monotonic()
                with path.open('wb') as handle:
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if time.monotonic() - started > MAX_DOWNLOAD_SECONDS:
                            raise MediaFailure('REVIEW', 'DOWNLOAD_TIMEOUT')
                        total += len(chunk)
                        if total > MAX_BYTES:
                            raise MediaFailure('BLOCK', 'MEDIA_TOO_LARGE')
                        handle.write(chunk)
                if total < MIN_BYTES:
                    raise MediaFailure('BLOCK', 'MEDIA_TOO_SMALL')
                if declared is not None and declared != total:
                    raise MediaFailure('REVIEW', 'INCOMPLETE_DOWNLOAD')
                yield DownloadedMedia(path, mime, total, host)
        except MediaFailure:
            raise
        except (OSError, TimeoutError, http.client.HTTPException):
            raise MediaFailure('REVIEW', 'REMOTE_FETCH_UNAVAILABLE') from None
        finally:
            if response is not None:
                response.close()


class MediaProbe:
    def inspect(self, path):
        executable = shutil.which('ffprobe')
        if not executable:
            raise MediaFailure('REVIEW', 'FFPROBE_UNAVAILABLE')
        try:
            # Restrict protocols: an untrusted container must not cause ffprobe
            # to fetch a playlist or another remote resource.
            result = subprocess.run([executable, '-v', 'error', '-protocol_whitelist', 'file',
                                     '-format_whitelist', 'mov,matroska,webm',
                                     '-show_entries', 'format=format_name,duration:stream=codec_type,codec_name,width,height',
                                     '-of', 'json', str(path)], shell=False, capture_output=True,
                                    text=True, timeout=30)
            if result.returncode:
                raise MediaFailure('BLOCK', 'MALFORMED_MEDIA')
            data = json.loads(result.stdout)
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except FileNotFoundError:
            raise MediaFailure('REVIEW', 'FFPROBE_UNAVAILABLE') from None
        except subprocess.TimeoutExpired:
            raise MediaFailure('REVIEW', 'PROBE_TIMEOUT') from None
        except (ValueError, OSError):
            raise MediaFailure('BLOCK', 'MALFORMED_MEDIA') from None
