"""Current-user protected local secret storage outside the repository."""

from __future__ import annotations

import ctypes
import os
import re
import tempfile
from pathlib import Path


_SECRET_NAME = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
_CRYPTPROTECT_UI_FORBIDDEN = 0x01


class SecureStoreError(RuntimeError):
    pass


class SecureStoreUnavailableError(SecureStoreError):
    pass


class SecureStoreCorruptError(SecureStoreError):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_ulong),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class DPAPICurrentUserProtector:
    """Protect values with Windows DPAPI for the current user."""

    def __init__(self):
        if os.name != "nt":
            raise SecureStoreUnavailableError(
                "Windows CurrentUser secure storage is unavailable"
            )
        self._crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._crypt32.CryptProtectData.argtypes = [
            ctypes.POINTER(_DataBlob),
            ctypes.c_wchar_p,
            ctypes.POINTER(_DataBlob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(_DataBlob),
        ]
        self._crypt32.CryptProtectData.restype = ctypes.c_int
        self._crypt32.CryptUnprotectData.argtypes = [
            ctypes.POINTER(_DataBlob),
            ctypes.POINTER(ctypes.c_wchar_p),
            ctypes.POINTER(_DataBlob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(_DataBlob),
        ]
        self._crypt32.CryptUnprotectData.restype = ctypes.c_int
        self._kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        self._kernel32.LocalFree.restype = ctypes.c_void_p

    @staticmethod
    def _blob(data: bytes):
        buffer = ctypes.create_string_buffer(data)
        blob = _DataBlob(
            len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
        )
        return blob, buffer

    def _result_bytes(self, output: _DataBlob) -> bytes:
        try:
            return ctypes.string_at(output.pbData, output.cbData)
        finally:
            if output.pbData:
                self._kernel32.LocalFree(ctypes.cast(output.pbData, ctypes.c_void_p))

    def protect(self, value: bytes) -> bytes:
        source, source_buffer = self._blob(value)
        output = _DataBlob()
        ok = self._crypt32.CryptProtectData(
            ctypes.byref(source),
            "Remote Pay Guide local secret",
            None,
            None,
            None,
            _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(output),
        )
        del source_buffer
        if not ok:
            raise SecureStoreError(
                f"Windows DPAPI protect failed ({ctypes.get_last_error()})"
            )
        return self._result_bytes(output)

    def unprotect(self, value: bytes) -> bytes:
        source, source_buffer = self._blob(value)
        output = _DataBlob()
        ok = self._crypt32.CryptUnprotectData(
            ctypes.byref(source),
            None,
            None,
            None,
            None,
            _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(output),
        )
        del source_buffer
        if not ok:
            raise SecureStoreCorruptError(
                f"Windows DPAPI unprotect failed ({ctypes.get_last_error()})"
            )
        return self._result_bytes(output)


def default_secure_store_root() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if not local_app_data:
        raise SecureStoreUnavailableError("LOCALAPPDATA is unavailable")
    return Path(local_app_data) / "RemotePayGuide" / "secure"


class LocalSecretStore:
    def __init__(self, root=None, protector=None):
        self.root = Path(root) if root is not None else default_secure_store_root()
        self.protector = protector or DPAPICurrentUserProtector()

    @staticmethod
    def _validate_name(name: str) -> str:
        normalized = str(name or "").strip().lower()
        if not _SECRET_NAME.fullmatch(normalized):
            raise ValueError("invalid secret name")
        return normalized

    def _path(self, name: str) -> Path:
        return self.root / f"{self._validate_name(name)}.bin"

    def get_secret(self, name: str):
        path = self._path(name)
        if not path.exists():
            return None
        try:
            encrypted = path.read_bytes()
            if not encrypted:
                raise SecureStoreCorruptError("encrypted secret payload is empty")
            return self.protector.unprotect(encrypted).decode("utf-8")
        except SecureStoreError:
            raise
        except (OSError, UnicodeError, ValueError) as exc:
            raise SecureStoreCorruptError(
                "encrypted secret payload is invalid"
            ) from exc

    def set_secret(self, name: str, value: str):
        if not isinstance(value, str) or not value:
            raise ValueError("secret value is required")
        path = self._path(name)
        encrypted = self.protector.protect(value.encode("utf-8"))
        self.root.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(encrypted)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def delete_secret(self, name: str):
        self._path(name).unlink(missing_ok=True)

    def has_secret(self, name: str) -> bool:
        return self.get_secret(name) is not None


def _store():
    return LocalSecretStore()


def get_secret(name):
    return _store().get_secret(name)


def set_secret(name, value):
    return _store().set_secret(name, value)


def delete_secret(name):
    return _store().delete_secret(name)


def has_secret(name):
    return _store().has_secret(name)
