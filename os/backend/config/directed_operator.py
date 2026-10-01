"""Local, narrowly scoped authorization for directed-request reconciliation."""

import ctypes
import hashlib
import os
import re
import sys
from ctypes import wintypes


PERMISSION = "DIRECTED_UNKNOWN_INTENT_RECONCILIATION"
ALLOWLIST_ENV = "OS_DIRECTED_RECONCILIATION_ALLOWED_SIDS"
_SID = re.compile(r"S-1-(?:\d+-){1,14}\d+\Z", re.IGNORECASE)


def _current_process_sid():
    """Obtain the SID from the Windows process token, never from a request."""
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    token = wintypes.HANDLE()
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.OpenProcessToken.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
        raise PermissionError("PROCESS_TOKEN_UNAVAILABLE")
    try:
        advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        advapi.GetTokenInformation.restype = wintypes.BOOL
        needed = wintypes.DWORD()
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
        if not needed.value:
            raise PermissionError("PROCESS_SID_UNAVAILABLE")
        buffer = ctypes.create_string_buffer(needed.value)
        if not advapi.GetTokenInformation(token, 1, buffer, needed, ctypes.byref(needed)):
            raise PermissionError("PROCESS_SID_UNAVAILABLE")
        sid_pointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
        sid_text = wintypes.LPWSTR()
        advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
        advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
        if not advapi.ConvertSidToStringSidW(sid_pointer, ctypes.byref(sid_text)):
            raise PermissionError("PROCESS_SID_UNAVAILABLE")
        try:
            return sid_text.value
        finally:
            kernel.LocalFree(ctypes.cast(sid_text, ctypes.c_void_p))
    finally:
        kernel.CloseHandle(token)


def authorize_directed_reconciliation(*, sid_provider=None, environ=None, platform_name=None):
    """Return a non-secret actor ID or deny. Injection is for isolated tests."""
    if (platform_name if platform_name is not None else sys.platform) != "win32":
        raise PermissionError("LOCAL_OPERATOR_WINDOWS_ONLY")
    config = (environ if environ is not None else os.environ).get(ALLOWLIST_ENV, "")
    entries = [item.strip().upper() for item in config.split(",")]
    if not entries or any(not _SID.fullmatch(item) for item in entries):
        raise PermissionError("RECONCILIATION_ALLOWLIST_INVALID_OR_MISSING")
    try:
        sid = (sid_provider or _current_process_sid)()
    except Exception as exc:
        raise PermissionError("PROCESS_SID_UNAVAILABLE") from exc
    if not isinstance(sid, str) or not _SID.fullmatch(sid.strip()):
        raise PermissionError("PROCESS_SID_UNAVAILABLE")
    normalized = sid.strip().upper()
    if normalized not in entries:
        raise PermissionError("RECONCILIATION_OPERATOR_NOT_ALLOWED")
    digest = hashlib.sha256(("remote-pay-guide:directed-reconciliation:v1:" + normalized).encode()).hexdigest()
    return "windows-sid-sha256:" + digest
